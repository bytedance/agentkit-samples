"""Harness Infra 控制面 TOP 与数据面 REST 客户端。"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode, urlsplit

import requests

API_VERSION = "2025-10-30"
WORKSPACE_ACTIONS = {
    "CreateHarness",
    "GetHarness",
    "ListHarnesses",
    "ListHarnessVersions",
    "CreateEnvironment",
    "GetEnvironment",
    "ListEnvironments",
    "CreateEnvironmentResource",
    "GetEnvironmentResource",
    "ListEnvironmentResources",
    "CreateRuntimeTemplate",
    "GetRuntimeTemplate",
    "ListRuntimeTemplates",
    "CreateHarnessSkill",
    "CreateHarnessSkillVersion",
    "GetHarnessSkill",
    "ListHarnessSkills",
    "ListHarnessSkillVersions",
}


def workspace_body(
    action: str, body: dict[str, Any], workspace_id: str = ""
) -> dict[str, Any]:
    """在签名前解析选择器；不修改调用者对象，拒绝空值类型和拼写冲突。"""
    if action not in WORKSPACE_ACTIONS:
        return body
    values = ([workspace_id] if workspace_id else []) + [
        body[key] for key in ("WorkspaceId", "workspace_id") if key in body
    ]
    if any(not isinstance(value, str) for value in values):
        raise TypeError("WorkspaceId must be a string")
    values = [value.strip() for value in values]
    if len(set(values)) > 1:
        raise ValueError("WorkspaceId selectors must match the configured workspace")
    if not values:
        return body
    return {
        **{key: value for key, value in body.items() if key != "workspace_id"},
        "WorkspaceId": values[0],
    }


RETRYABLE_STATUS_CODES = {429, 503}


class HarnessInfraError(RuntimeError):
    """保留公开错误码和 RequestId，但不包含请求凭据或响应正文。"""

    def __init__(
        self,
        operation: str,
        code: str,
        message: str,
        *,
        status_code: int,
        request_id: str = "",
    ) -> None:
        details = [f"HTTP {status_code}", code, message]
        if request_id:
            details.append(f"RequestId={request_id}")
        super().__init__(
            f"{operation} failed: " + ": ".join(item for item in details if item)
        )
        self.operation = operation
        self.code = code
        self.status_code = status_code
        self.request_id = request_id


@dataclass(frozen=True)
class ControlConfig:
    """控制面签名及请求入口配置。"""

    access_key: str
    secret_key: str
    region: str
    service: str
    host: str
    scheme: str = "https"
    session_token: str = ""
    api_version: str = API_VERSION
    workspace_id: str = ""


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def _integer_env(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value < minimum:
        raise RuntimeError(f"{name} must be at least {minimum}")
    return value


def control_config_from_env() -> ControlConfig:
    """从专用变量读取配置，并兼容 samples 已有 Volcengine 变量。"""

    access_key = _env(
        "HARNESS_INFRA_ACCESS_KEY",
        "VOLCENGINE_AGENTKIT_ACCESS_KEY",
        "VOLCENGINE_ACCESS_KEY",
    )
    secret_key = _env(
        "HARNESS_INFRA_SECRET_KEY",
        "VOLCENGINE_AGENTKIT_SECRET_KEY",
        "VOLCENGINE_SECRET_KEY",
    )
    if not access_key or not secret_key:
        raise RuntimeError(
            "set HARNESS_INFRA_ACCESS_KEY/HARNESS_INFRA_SECRET_KEY "
            "or VOLCENGINE_ACCESS_KEY/VOLCENGINE_SECRET_KEY"
        )
    return ControlConfig(
        workspace_id=_env("HARNESS_INFRA_WORKSPACE_ID", "AGENTKIT_WORKSPACE_ID"),
        access_key=access_key,
        secret_key=secret_key,
        session_token=_env(
            "HARNESS_INFRA_SESSION_TOKEN",
            "VOLCENGINE_AGENTKIT_SESSION_TOKEN",
            "VOLCENGINE_SESSION_TOKEN",
        ),
        region=_env(
            "HARNESS_INFRA_REGION",
            "VOLCENGINE_AGENTKIT_REGION",
            "VOLCENGINE_REGION",
            default="cn-beijing",
        ),
        service=_env(
            "HARNESS_INFRA_SERVICE",
            "VOLCENGINE_AGENTKIT_SERVICE",
            default="agentkit",
        ),
        host=_env(
            "HARNESS_INFRA_CONTROL_HOST",
            "VOLCENGINE_AGENTKIT_HOST",
            default="open.volcengineapi.com",
        ),
        scheme=_env(
            "HARNESS_INFRA_CONTROL_SCHEME",
            "VOLCENGINE_AGENTKIT_SCHEME",
            default="https",
        ),
        api_version=_env(
            "HARNESS_INFRA_API_VERSION",
            "VOLCENGINE_AGENTKIT_API_VERSION",
            default=API_VERSION,
        ),
    )


def _hmac_sha256(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()


def _canonical_query(query: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in sorted(query.items()):
        values = value if isinstance(value, list) else [value]
        for item in values:
            parts.append(
                f"{quote(str(key), safe='-_.~')}={quote(str(item), safe='-_.~')}"
            )
    return "&".join(parts)


def sign_headers(
    method: str,
    host: str,
    query: dict[str, Any],
    body: bytes,
    *,
    config: ControlConfig,
    path: str = "/",
) -> dict[str, str]:
    """按 Volcengine HMAC-SHA256 规范生成控制面请求头。"""

    now = dt.datetime.now(dt.UTC)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    date = timestamp[:8]
    payload_hash = hashlib.sha256(body).hexdigest()
    signed = {
        "content-type": "application/json",
        "host": host,
        "x-content-sha256": payload_hash,
        "x-date": timestamp,
    }
    if config.session_token:
        signed["x-security-token"] = config.session_token
    signed_names = ";".join(sorted(signed))
    canonical_headers = "".join(f"{name}:{signed[name]}\n" for name in sorted(signed))
    canonical_request = "\n".join(
        [
            method.upper(),
            path,
            _canonical_query(query),
            canonical_headers,
            signed_names,
            payload_hash,
        ]
    )
    scope = f"{date}/{config.region}/{config.service}/request"
    string_to_sign = "\n".join(
        [
            "HMAC-SHA256",
            timestamp,
            scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signing_key = _hmac_sha256(
        _hmac_sha256(
            _hmac_sha256(
                _hmac_sha256(config.secret_key.encode("utf-8"), date),
                config.region,
            ),
            config.service,
        ),
        "request",
    )
    signature = hmac.new(
        signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Host": host,
        "X-Date": timestamp,
        "X-Content-Sha256": payload_hash,
        "Authorization": (
            f"HMAC-SHA256 Credential={config.access_key}/{scope}, "
            f"SignedHeaders={signed_names}, Signature={signature}"
        ),
    }
    if config.session_token:
        headers["X-Security-Token"] = config.session_token
    return headers


def _decode_json(
    operation: str, response: requests.Response, *, top_envelope: bool
) -> dict[str, Any]:
    """解码公开错误，拒绝把任意 HTTP 2xx 正文当成成功。"""

    try:
        payload = response.json()
    except ValueError:
        request_id = response.headers.get("request-id", "")
        raise HarnessInfraError(
            operation,
            "InvalidResponse",
            "non-JSON response",
            status_code=response.status_code,
            request_id=request_id,
        ) from None
    if not isinstance(payload, dict):
        raise HarnessInfraError(
            operation,
            "InvalidResponse",
            "response must be a JSON object",
            status_code=response.status_code,
        )
    metadata = payload.get("ResponseMetadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    error = metadata.get("Error")
    error = error if isinstance(error, dict) else {}
    request_id = str(
        metadata.get("RequestId")
        or payload.get("request_id")
        or response.headers.get("request-id")
        or ""
    )
    if error or not 200 <= response.status_code < 300:
        data_error = payload.get("error")
        data_error = data_error if isinstance(data_error, dict) else {}
        code = str(
            error.get("Code")
            or data_error.get("type")
            or payload.get("code")
            or "HTTPError"
        )
        message = str(
            error.get("Message")
            or data_error.get("message")
            or payload.get("message")
            or ""
        )
        raise HarnessInfraError(
            operation,
            code,
            message,
            status_code=response.status_code,
            request_id=request_id,
        )
    if top_envelope:
        result = payload.get("Result")
        if not isinstance(result, dict):
            raise HarnessInfraError(
                operation,
                "InvalidResponse",
                "TOP response is missing object Result",
                status_code=response.status_code,
                request_id=request_id,
            )
        return result
    return payload


class TopClient:
    """使用账号 AK/SK 调用 Harness Infra 控制面 Action。"""

    def __init__(self, config: ControlConfig | None = None) -> None:
        self.config = config or control_config_from_env()
        if self.config.scheme not in {"http", "https"}:
            raise RuntimeError("control scheme must be http or https")
        self.timeout = _integer_env("HARNESS_INFRA_HTTP_TIMEOUT_SECONDS", 60, minimum=1)
        self.retries = _integer_env("HARNESS_INFRA_HTTP_RETRIES", 2, minimum=0)

    @property
    def scope(self) -> str:
        return (
            f"{self.config.scheme}://{self.config.host}/"
            f"{self.config.region}/{self.config.service}/{self.config.api_version}"
            + (
                f"/workspace/{self.config.workspace_id}"
                if self.config.workspace_id
                else ""
            )
        )

    def call(self, action: str, body: dict[str, Any]) -> dict[str, Any]:
        """发送一个 PascalCase 控制面请求并返回 Result。"""

        query = {"Action": action, "Version": self.config.api_version}
        body = workspace_body(action, body, self.config.workspace_id)
        url = f"{self.config.scheme}://{self.config.host}/?" + urlencode(query)
        payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        for attempt in range(self.retries + 1):
            headers = sign_headers(
                "POST", self.config.host, query, payload, config=self.config
            )
            try:
                response = requests.post(
                    url,
                    data=payload,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=False,
                )
            except requests.RequestException:
                if attempt < self.retries:
                    time.sleep(min(8.0, 0.5 * (2**attempt)))
                    continue
                raise RuntimeError(
                    f"{action}: network error; retry with the same token and body"
                ) from None
            if (
                response.status_code in RETRYABLE_STATUS_CODES
                and attempt < self.retries
            ):
                time.sleep(min(8.0, 0.5 * (2**attempt)))
                continue
            return _decode_json(action, response, top_envelope=True)
        raise AssertionError("unreachable")


class DataPlaneClient:
    """使用首次返回的 Environment Key 调用 Endpoint 数据面 REST。"""

    def __init__(self, base_url: str, api_key: str) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeError(
                "Endpoint BaseUrl must be HTTP(S) without credentials, query or fragment"
            )
        if not api_key:
            raise RuntimeError("Environment API Key is empty")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = _integer_env("HARNESS_INFRA_DATA_TIMEOUT_SECONDS", 60, minimum=1)

    def call(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """调用一个数据面路径，保留 Endpoint 的路径前缀。"""

        url = f"{self.base_url}/{path.lstrip('/')}"
        request_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
        }
        request_headers.update(headers or {})
        payload = (
            json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if body is not None
            else None
        )
        try:
            response = requests.request(
                method,
                url,
                params=params,
                data=payload,
                headers=request_headers,
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException:
            raise RuntimeError(f"{method} {path}: data-plane network error") from None
        return _decode_json(f"{method} {path}", response, top_envelope=False)
