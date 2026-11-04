"""RuntimeTemplate HTTP client with TOP signing."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode

import requests

API_VERSION = "2025-10-30"
RETRYABLE_STATUS_CODES = {429, 503}


class AgentKitHttpError(RuntimeError):
    """保留服务端诊断字段的 RuntimeTemplate 请求错误。"""

    def __init__(
        self,
        action: str,
        code: str,
        message: str,
        *,
        status_code: int,
        request_id: str = "",
    ) -> None:
        details = [f"HTTP {status_code}", code, message]
        if request_id:
            details.append(f"RequestId={request_id}")
        super().__init__(f"{action} failed: " + ": ".join(filter(None, details)))
        self.action = action
        self.code = code
        self.message = message
        self.status_code = status_code
        self.request_id = request_id


@dataclass(frozen=True)
class Endpoint:
    provider: str
    region: str
    host: str
    service: str
    version: str
    scheme: str


@dataclass(frozen=True)
class Credentials:
    access_key: str
    secret_key: str
    session_token: str = ""


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def _positive_int_env(name: str, default: int) -> int:
    raw = _env(name)
    try:
        value = int(raw) if raw else default
    except ValueError:
        raise RuntimeError(f"{name} must be an integer") from None
    if value <= 0:
        raise RuntimeError(f"{name} must be greater than zero")
    return value


def resolve_provider() -> str:
    provider = (_env("AGENTKIT_CLOUD_PROVIDER") or "volcengine").lower()
    if provider not in {"volcengine", "byteplus"}:
        raise RuntimeError("AGENTKIT_CLOUD_PROVIDER must be volcengine or byteplus")
    return provider


def resolve_endpoint() -> Endpoint:
    provider = resolve_provider()
    if provider == "byteplus":
        region = (
            _env("BYTEPLUS_AGENTKIT_REGION")
            or _env("AGENTKIT_REGION")
            or "ap-southeast-1"
        )
        return Endpoint(
            provider,
            region,
            _env("BYTEPLUS_AGENTKIT_HOST") or f"agentkit.{region}.byteplusapi.com",
            _env("BYTEPLUS_AGENTKIT_SERVICE") or "agentkit",
            _env("BYTEPLUS_AGENTKIT_API_VERSION") or API_VERSION,
            _env("BYTEPLUS_AGENTKIT_SCHEME") or "https",
        )
    region = (
        _env("VOLCENGINE_AGENTKIT_REGION")
        or _env("AGENTKIT_REGION")
        or _env("VOLCENGINE_REGION")
        or "cn-beijing"
    )
    return Endpoint(
        provider,
        region,
        _env("VOLCENGINE_AGENTKIT_HOST") or "open.volcengineapi.com",
        _env("VOLCENGINE_AGENTKIT_SERVICE") or "agentkit",
        _env("VOLCENGINE_AGENTKIT_API_VERSION") or API_VERSION,
        _env("VOLCENGINE_AGENTKIT_SCHEME") or "https",
    )


def resolve_credentials() -> Credentials:
    provider = resolve_provider()
    if provider == "byteplus":
        access_key = _env("BYTEPLUS_AGENTKIT_ACCESS_KEY") or _env("BYTEPLUS_ACCESS_KEY")
        secret_key = _env("BYTEPLUS_AGENTKIT_SECRET_KEY") or _env("BYTEPLUS_SECRET_KEY")
        token = _env("BYTEPLUS_AGENTKIT_SESSION_TOKEN") or _env(
            "BYTEPLUS_SESSION_TOKEN"
        )
    else:
        access_key = _env("VOLCENGINE_AGENTKIT_ACCESS_KEY") or _env(
            "VOLCENGINE_ACCESS_KEY"
        )
        secret_key = _env("VOLCENGINE_AGENTKIT_SECRET_KEY") or _env(
            "VOLCENGINE_SECRET_KEY"
        )
        token = _env("VOLCENGINE_AGENTKIT_SESSION_TOKEN") or _env(
            "VOLCENGINE_SESSION_TOKEN"
        )
    if not access_key or not secret_key:
        prefix = "BYTEPLUS" if provider == "byteplus" else "VOLCENGINE"
        raise RuntimeError(f"set {prefix}_ACCESS_KEY and {prefix}_SECRET_KEY")
    return Credentials(access_key, secret_key, token)


def _canonical_query(query: dict[str, Any]) -> str:
    pairs = []
    for key, value in sorted(query.items()):
        values = value if isinstance(value, list) else [value]
        for item in values:
            pairs.append(
                f"{quote(str(key), safe='-_.~')}={quote(str(item), safe='-_.~')}"
            )
    return "&".join(pairs)


def _hmac(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode(), hashlib.sha256).digest()


def sign_headers(
    method: str,
    host: str,
    query: dict[str, Any],
    body: bytes,
    *,
    credentials: Credentials,
    service: str,
    region: str,
    now: dt.datetime | None = None,
) -> dict[str, str]:
    """按 Volcengine/BytePlus TOP HMAC-SHA256 规范生成请求头。"""
    current = now or dt.datetime.now(dt.timezone.utc)
    x_date = current.strftime("%Y%m%dT%H%M%SZ")
    short_date = x_date[:8]
    payload_hash = hashlib.sha256(body).hexdigest()
    signed = {
        "content-type": "application/json",
        "host": host,
        "x-content-sha256": payload_hash,
        "x-date": x_date,
    }
    if credentials.session_token:
        signed["x-security-token"] = credentials.session_token
    signed_names = ";".join(sorted(signed))
    canonical_headers = "".join(f"{key}:{signed[key]}\n" for key in sorted(signed))
    canonical_request = "\n".join(
        [
            method,
            "/",
            _canonical_query(query),
            canonical_headers,
            signed_names,
            payload_hash,
        ]
    )
    scope = f"{short_date}/{region}/{service}/request"
    string_to_sign = "\n".join(
        [
            "HMAC-SHA256",
            x_date,
            scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ]
    )
    key = _hmac(
        _hmac(
            _hmac(
                _hmac(credentials.secret_key.encode(), short_date),
                region,
            ),
            service,
        ),
        "request",
    )
    signature = hmac.new(key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Host": host,
        "X-Date": x_date,
        "X-Content-Sha256": payload_hash,
        "Authorization": (
            f"HMAC-SHA256 Credential={credentials.access_key}/{scope}, "
            f"SignedHeaders={signed_names}, Signature={signature}"
        ),
    }
    if credentials.session_token:
        headers["X-Security-Token"] = credentials.session_token
    return headers


def request_url(action: str) -> str:
    endpoint = resolve_endpoint()
    query = urlencode({"Action": action, "Version": endpoint.version})
    return f"{endpoint.scheme}://{endpoint.host}/?{query}"


def endpoint_scope() -> str:
    endpoint = resolve_endpoint()
    return (
        f"{endpoint.scheme}://{endpoint.host}/"
        f"?Version={endpoint.version}&Region={endpoint.region}"
    )


def _response_json(action: str, response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        raise AgentKitHttpError(
            action,
            "InvalidResponse",
            "response is not JSON",
            status_code=response.status_code,
        ) from None
    if not isinstance(payload, dict):
        raise AgentKitHttpError(
            action,
            "InvalidResponse",
            "response JSON must be an object",
            status_code=response.status_code,
        )
    metadata = payload.get("ResponseMetadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    error = metadata.get("Error")
    error = error if isinstance(error, dict) else {}
    if response.status_code >= 400 or error:
        raise AgentKitHttpError(
            action,
            str(error.get("Code") or "HttpError"),
            str(error.get("Message") or response.reason),
            status_code=response.status_code,
            request_id=str(metadata.get("RequestId") or ""),
        )
    result = payload.get("Result", payload)
    if not isinstance(result, dict):
        raise AgentKitHttpError(
            action,
            "InvalidResponse",
            "Result must be an object",
            status_code=response.status_code,
            request_id=str(metadata.get("RequestId") or ""),
        )
    return result


class RuntimeTemplateHttpClient:
    """调用 RuntimeTemplate 五个公开 Action 的轻量 HTTP 客户端。"""

    def __init__(self, workspace_id: str | None = None) -> None:
        self.workspace_id = (
            workspace_id
            if workspace_id is not None
            else os.getenv(
                "HARNESS_INFRA_WORKSPACE_ID", os.getenv("AGENTKIT_WORKSPACE_ID", "")
            )
        ).strip()
        self.timeout = _positive_int_env("AGENTKIT_HTTP_TIMEOUT_SECONDS", 30)
        self.retries = _positive_int_env("AGENTKIT_HTTP_ATTEMPTS", 3)

    def call(self, action: str, body: dict[str, Any]) -> dict[str, Any]:
        if action in {
            "CreateRuntimeTemplate",
            "GetRuntimeTemplate",
            "ListRuntimeTemplates",
        }:
            selected = body.get(
                "WorkspaceId", body.get("workspace_id", self.workspace_id)
            )
            if not isinstance(selected, str):
                raise TypeError("WorkspaceId must be a string")
            selectors = [
                body[key].strip()
                for key in ("WorkspaceId", "workspace_id")
                if key in body and isinstance(body[key], str)
            ]
            if any(
                not isinstance(body[key], str)
                for key in ("WorkspaceId", "workspace_id")
                if key in body
            ):
                raise TypeError("WorkspaceId must be a string")
            if self.workspace_id:
                selectors.append(self.workspace_id)
            if len(set(selectors)) > 1:
                raise ValueError("WorkspaceId selectors must match")
            body = {key: value for key, value in body.items() if key != "workspace_id"}
            if selected:
                body["WorkspaceId"] = selected.strip()
        encoded = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
        endpoint = resolve_endpoint()
        query = {"Action": action, "Version": endpoint.version}
        url = f"{endpoint.scheme}://{endpoint.host}/?{_canonical_query(query)}"
        headers = sign_headers(
            "POST",
            endpoint.host,
            query,
            encoded,
            credentials=resolve_credentials(),
            service=endpoint.service,
            region=endpoint.region,
        )
        for attempt in range(self.retries):
            try:
                response = requests.post(
                    url,
                    data=encoded,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=False,
                )
            except requests.RequestException as exc:
                if attempt + 1 == self.retries:
                    raise RuntimeError(
                        f"{action} network error after {self.retries} attempts: "
                        f"{type(exc).__name__}"
                    ) from None
                time.sleep(min(4.0, 0.5 * 2**attempt))
                continue
            if (
                response.status_code in RETRYABLE_STATUS_CODES
                and attempt + 1 < self.retries
            ):
                time.sleep(min(4.0, 0.5 * 2**attempt))
                continue
            return _response_json(action, response)
        raise AssertionError("unreachable")
