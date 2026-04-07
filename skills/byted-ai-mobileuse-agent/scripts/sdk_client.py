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
from typing import Any, Dict, Optional, Tuple


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
        configuration.ak = self.access_key or os.environ.get("VOLC_ACCESSKEY")
        configuration.sk = self.secret_key or os.environ.get("VOLC_SECRETKEY")
        configuration.region = os.environ.get("VOLC_REGION", self.region)

        api = volcenginesdkcore.UniversalApi(volcenginesdkcore.ApiClient(configuration))
        self._sdk = volcenginesdkcore
        self._api = api
        return self._sdk, self._api

    def call(self, *, method: str, action: str, body: Dict[str, Any]) -> Dict[str, Any]:
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


def extract_result_payload(resp: Any) -> Dict[str, Any]:
    if not isinstance(resp, dict):
        return {}
    if isinstance(resp.get("Result"), dict):
        return resp["Result"]
    if any(k in resp for k in ("RunId", "RunName", "ThreadId")):
        return resp
    return {}


def error_envelope(*, err: Exception, raw_response: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "ok": False,
        "error": {"type": type(err).__name__, "message": str(err)},
        "raw_response": raw_response or {},
    }
