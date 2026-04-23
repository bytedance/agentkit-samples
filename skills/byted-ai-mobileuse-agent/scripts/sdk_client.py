# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple


def _as_non_empty_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _env(name: str) -> Optional[str]:
    return _as_non_empty_str(os.getenv(name))


def read_env_ark_proxy() -> Tuple[Optional[str], Optional[str]]:
    return _env("ARK_SKILL_API_BASE"), _env("ARK_SKILL_API_KEY")


def read_env_aksk() -> Tuple[str, str]:
    ak = (
        _env("VOLC_ACCESSKEY")
        or _env("VOLC_ACCESS_KEY_ID")
        or _env("VOLCSTACK_ACCESS_KEY_ID")
        or _env("VOLCENGINE_ACCESS_KEY")
    )
    sk = (
        _env("VOLC_SECRETKEY")
        or _env("VOLC_SECRET_ACCESS_KEY")
        or _env("VOLCSTACK_SECRET_ACCESS_KEY")
        or _env("VOLCENGINE_SECRET_KEY")
    )
    if not ak or not sk:
        raise RuntimeError(
            "缺少鉴权环境变量: VOLC_ACCESSKEY/VOLC_SECRETKEY "
            "(兼容: VOLC_ACCESS_KEY_ID/VOLC_SECRET_ACCESS_KEY, VOLCSTACK_ACCESS_KEY_ID/VOLCSTACK_SECRET_ACCESS_KEY; 可替代: VOLCENGINE_ACCESS_KEY/VOLCENGINE_SECRET_KEY)"
        )
    return ak, sk


def has_ark_proxy_env() -> bool:
    api_base, api_key = read_env_ark_proxy()
    return bool(api_base and api_key)


class UniversalClient:
    def __init__(
        self,
        *,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        service: str = "ipaas",
        version: str = "2023-08-01",
        region: str = "cn-north-1",
    ) -> None:
        self.access_key = access_key
        self.secret_key = secret_key
        self.service = service
        self.version = version
        self.region = region
        self._sdk: Any = None
        self._api: Any = None

    def _init_sdk(self) -> Tuple[Any, Any]:
        if self._sdk is not None and self._api is not None:
            return self._sdk, self._api

        import volcenginesdkcore

        configuration = volcenginesdkcore.Configuration()
        host = os.environ.get("VOLC_HOST")
        if host:
            configuration.host = host
        ak = (
            _as_non_empty_str(self.access_key)
            or _env("VOLC_ACCESSKEY")
            or _env("VOLC_ACCESS_KEY_ID")
            or _env("VOLCSTACK_ACCESS_KEY_ID")
            or _env("VOLCENGINE_ACCESS_KEY")
        )
        sk = (
            _as_non_empty_str(self.secret_key)
            or _env("VOLC_SECRETKEY")
            or _env("VOLC_SECRET_ACCESS_KEY")
            or _env("VOLCSTACK_SECRET_ACCESS_KEY")
            or _env("VOLCENGINE_SECRET_KEY")
        )
        if not ak or not sk:
            ak, sk = read_env_aksk()
        configuration.ak = ak
        configuration.sk = sk
        configuration.region = os.environ.get("VOLC_REGION", self.region)

        api = volcenginesdkcore.UniversalApi(volcenginesdkcore.ApiClient(configuration))
        self._sdk = volcenginesdkcore
        self._api = api
        return self._sdk, self._api

    def call(self, *, method: str, action: str, body: Dict[str, Any]) -> Dict[str, Any]:
        api_base, api_key = read_env_ark_proxy()
        if api_base and api_key:
            return self._call_via_ark_proxy(
                method=method,
                action=action,
                body=body,
                api_base=api_base,
                api_key=api_key,
            )

        sdk, api = self._init_sdk()
        request_body = sdk.Flatten(body).flat()
        info = sdk.UniversalInfo(
            method=method,
            action=action,
            service=self.service,
            version=self.version,
            content_type="application/json",
        )
        resp = api.do_call(info, request_body)
        if isinstance(resp, dict):
            return resp
        return {"Result": resp}

    def _call_via_ark_proxy(
        self,
        *,
        method: str,
        action: str,
        body: Dict[str, Any],
        api_base: str,
        api_key: str,
    ) -> Dict[str, Any]:
        url = f"{api_base.rstrip('/')}/?Action={urllib.parse.quote(action)}&Version={urllib.parse.quote(self.version)}"
        headers = {
            "ServiceName": self.service,
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

        resolved_method = (method or "POST").upper()
        if resolved_method == "GET":
            if body:
                query = urllib.parse.urlencode(body, doseq=True)
                url = f"{url}&{query}"
            data = None
        else:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body or {}, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(
            url, data=data, headers=headers, method=resolved_method
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = resp.read()
            try:
                parsed = json.loads(resp_body.decode("utf-8"))
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                return parsed
            return {"Result": parsed}
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8")
            except Exception:
                detail = ""
            raise RuntimeError(f"HTTP 错误: {e.code} {e.reason} {detail}".strip())
        except urllib.error.URLError as e:
            raise RuntimeError(f"网络错误: {e.reason}")


def extract_result_payload(resp: Any) -> Dict[str, Any]:
    if not isinstance(resp, dict):
        return {}
    if isinstance(resp.get("Result"), dict):
        return resp["Result"]
    if any(k in resp for k in ("RunId", "RunName", "ThreadId")):
        return resp
    return {}


def error_envelope(
    *, err: Exception, raw_response: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    return {
        "ok": False,
        "error": {"type": type(err).__name__, "message": str(err)},
        "raw_response": raw_response or {},
    }
