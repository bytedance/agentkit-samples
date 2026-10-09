"""HTTP client for EnvironmentResource Actions, with TOP signing or direct HTTP."""

from __future__ import annotations

import datetime as _datetime
import hashlib
import hmac
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode, urlsplit

import requests


API_VERSION = "2025-10-30"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_HTTP_RETRIES = 2
RETRYABLE_STATUS_CODES = {429, 503}
PROVIDERS = {"volcengine", "byteplus"}


class AgentKitHttpError(RuntimeError):
    """OpenAPI or direct HTTP failure, retaining diagnostic fields."""

    def __init__(
        self,
        action: str,
        code: str,
        message: str,
        *,
        status_code: int,
        request_id: str = "",
        biz_code: int | None = None,
        reason: str = "",
    ) -> None:
        details = [f"HTTP {status_code}", code, message]
        if biz_code is not None:
            details.append(f"bizCode={biz_code}")
        if reason and reason != code:
            details.append(f"reason={reason}")
        if request_id:
            details.append(f"RequestId={request_id}")
        super().__init__(f"Failed to {action}: " + ": ".join(filter(None, details)))
        self.action = action
        self.code = code
        self.message = message
        self.status_code = status_code
        self.request_id = request_id
        self.biz_code = biz_code
        self.reason = reason


@dataclass(frozen=True)
class EndpointConfig:
    provider: str
    region: str
    host: str
    service: str
    api_version: str
    scheme: str = "https"


@dataclass(frozen=True)
class Credentials:
    access_key: str
    secret_key: str
    session_token: str = ""


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def _int_env(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


def _positive_int_env(name: str, default: int) -> int:
    value = _int_env(name, default)
    if value <= 0:
        raise RuntimeError(f"{name} must be greater than zero")
    return value


def _non_negative_int_env(name: str, default: int) -> int:
    value = _int_env(name, default)
    if value < 0:
        raise RuntimeError(f"{name} must be greater than or equal to zero")
    return value


def resolve_provider() -> str:
    provider = (_env("AGENTKIT_CLOUD_PROVIDER") or _env("CLOUD_PROVIDER")).lower()
    if not provider:
        provider = "volcengine"
    if provider not in PROVIDERS:
        allowed = ", ".join(sorted(PROVIDERS))
        raise RuntimeError(f"AGENTKIT_CLOUD_PROVIDER must be one of: {allowed}")
    return provider


def resolve_endpoint(provider: str | None = None) -> EndpointConfig:
    provider = provider or resolve_provider()
    if provider == "byteplus":
        region = (
            _env("BYTEPLUS_AGENTKIT_REGION")
            or _env("AGENTKIT_REGION")
            or _env("BYTEPLUS_REGION")
            or "ap-southeast-1"
        )
        host = _env("BYTEPLUS_AGENTKIT_HOST") or f"agentkit.{region}.byteplusapi.com"
        service = _env("BYTEPLUS_AGENTKIT_SERVICE") or "agentkit"
        version = _env("BYTEPLUS_AGENTKIT_API_VERSION") or API_VERSION
        scheme = _env("BYTEPLUS_AGENTKIT_SCHEME") or "https"
        return EndpointConfig(provider, region, host, service, version, scheme)

    region = (
        _env("VOLCENGINE_AGENTKIT_REGION")
        or _env("AGENTKIT_REGION")
        or _env("VOLCENGINE_REGION")
        or _env("VOLC_REGION")
        or _env("REGION")
        or "cn-beijing"
    )
    host = _env("VOLCENGINE_AGENTKIT_HOST") or _env("VOLC_AGENTKIT_HOST")
    if not host:
        host = "open.volcengineapi.com"
    service = _env("VOLCENGINE_AGENTKIT_SERVICE") or _env("VOLC_AGENTKIT_SERVICE")
    service = service or "agentkit"
    version = (
        _env("VOLCENGINE_AGENTKIT_API_VERSION")
        or _env("VOLC_AGENTKIT_API_VERSION")
        or API_VERSION
    )
    scheme = _env("VOLCENGINE_AGENTKIT_SCHEME") or _env("VOLC_AGENTKIT_SCHEME")
    scheme = scheme or "https"
    return EndpointConfig(provider, region, host, service, version, scheme)


def resolve_credentials(provider: str | None = None) -> Credentials:
    provider = provider or resolve_provider()
    if provider == "byteplus":
        ak = _env("BYTEPLUS_AGENTKIT_ACCESS_KEY") or _env("BYTEPLUS_ACCESS_KEY")
        sk = _env("BYTEPLUS_AGENTKIT_SECRET_KEY") or _env("BYTEPLUS_SECRET_KEY")
        token = _env("BYTEPLUS_AGENTKIT_SESSION_TOKEN") or _env(
            "BYTEPLUS_SESSION_TOKEN"
        )
        if not ak or not sk:
            raise RuntimeError(
                "BytePlus credentials not found; set BYTEPLUS_ACCESS_KEY and "
                "BYTEPLUS_SECRET_KEY"
            )
        return Credentials(ak, sk, token)

    ak = (
        _env("VOLCENGINE_AGENTKIT_ACCESS_KEY")
        or _env("VOLC_AGENTKIT_ACCESSKEY")
        or _env("VOLCENGINE_ACCESS_KEY")
        or _env("VOLC_ACCESSKEY")
    )
    sk = (
        _env("VOLCENGINE_AGENTKIT_SECRET_KEY")
        or _env("VOLC_AGENTKIT_SECRETKEY")
        or _env("VOLCENGINE_SECRET_KEY")
        or _env("VOLC_SECRETKEY")
    )
    token = (
        _env("VOLCENGINE_AGENTKIT_SESSION_TOKEN")
        or _env("VOLC_AGENTKIT_SESSIONTOKEN")
        or _env("VOLCENGINE_SESSION_TOKEN")
        or _env("VOLC_SESSIONTOKEN")
    )
    if not ak or not sk:
        raise RuntimeError(
            "Volcengine credentials not found; set VOLCENGINE_ACCESS_KEY and "
            "VOLCENGINE_SECRET_KEY"
        )
    return Credentials(ak, sk, token)


def _hmac_sha256(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _canonical_query(query: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in sorted(query.items()):
        if isinstance(value, list):
            for item in value:
                parts.append(
                    f"{quote(str(key), safe='-_.~')}={quote(str(item), safe='-_.~')}"
                )
        else:
            parts.append(
                f"{quote(str(key), safe='-_.~')}={quote(str(value), safe='-_.~')}"
            )
    return "&".join(parts)


def sign_headers(
    method: str,
    host: str,
    query: dict[str, Any],
    body: bytes,
    *,
    access_key: str,
    secret_key: str,
    service: str,
    region: str,
    session_token: str = "",
    content_type: str = "application/json",
    path: str = "/",
) -> dict[str, str]:
    now = _datetime.datetime.now(_datetime.timezone.utc)
    x_date = now.strftime("%Y%m%dT%H%M%SZ")
    short_date = x_date[:8]
    payload_hash = hashlib.sha256(body).hexdigest()

    signed = {
        "content-type": content_type,
        "host": host,
        "x-content-sha256": payload_hash,
        "x-date": x_date,
    }
    if session_token:
        signed["x-security-token"] = session_token

    signed_headers = ";".join(sorted(signed))
    canonical_headers = "".join(f"{key}:{signed[key]}\n" for key in sorted(signed))
    canonical_request = "\n".join(
        [
            method.upper(),
            path,
            _canonical_query(query),
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )

    credential_scope = f"{short_date}/{region}/{service}/request"
    string_to_sign = "\n".join(
        [
            "HMAC-SHA256",
            x_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signing_key = _hmac_sha256(
        _hmac_sha256(
            _hmac_sha256(
                _hmac_sha256(secret_key.encode("utf-8"), short_date),
                region,
            ),
            service,
        ),
        "request",
    )
    signature = hmac.new(
        signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    headers = {
        "Accept": "application/json",
        "Content-Type": content_type,
        "Host": host,
        "X-Date": x_date,
        "X-Content-Sha256": payload_hash,
        "Authorization": (
            f"HMAC-SHA256 Credential={access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
    }
    if session_token:
        headers["X-Security-Token"] = session_token
    return headers


def _backoff_seconds(attempt: int) -> float:
    return min(8.0, 0.5 * (2**attempt))


def _retry_after_seconds(response: requests.Response) -> float | None:
    raw = response.headers.get("Retry-After", "").strip()
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None


def direct_base_url() -> str:
    value = _env("MA_RESOURCE_BASE_URL").rstrip("/")
    if value:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeError(
                "MA_RESOURCE_BASE_URL must be an HTTP(S) URL without credentials, query or fragment"
            )
    return value


def request_url(action: str) -> str:
    """Resolve routing without loading credentials, including for --dry-run."""
    direct = direct_base_url()
    if direct:
        return f"{direct}/{action}"
    endpoint = resolve_endpoint()
    query = urlencode({"Action": action, "Version": endpoint.api_version})
    return f"{endpoint.scheme}://{endpoint.host}/?{query}"


def endpoint_scope() -> str:
    """Bind the local resource ID cache to its configured API endpoint."""
    direct = direct_base_url()
    if direct:
        return direct
    endpoint = resolve_endpoint()
    return f"{endpoint.scheme}://{endpoint.host}/{endpoint.provider}/{endpoint.region}/{endpoint.service}/{endpoint.api_version}"


def response_json(action: str, response: requests.Response) -> dict[str, Any]:
    """Decode shared IAM/AgentKit errors without printing arbitrary bodies."""
    try:
        result = response.json()
    except ValueError:
        request_id = response.headers.get("request-id", "")
        raise RuntimeError(
            f"{action}: non-JSON HTTP {response.status_code} response"
            + (f"; RequestId={request_id}" if request_id else "")
        ) from None
    if not isinstance(result, dict):
        raise RuntimeError(f"{action}: response must be a JSON object")
    metadata = result.get("ResponseMetadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    request_id = str(
        metadata.get("RequestId")
        or result.get("RequestId")
        or response.headers.get("request-id")
        or ""
    )
    error = metadata.get("Error")
    if isinstance(error, dict) and error:
        raise AgentKitHttpError(
            action,
            str(error.get("Code") or ""),
            str(error.get("Message") or ""),
            status_code=response.status_code,
            request_id=request_id,
        )
    if not 200 <= response.status_code < 300:
        reason = result.get("reason")
        reason = reason if isinstance(reason, str) else ""
        message = result.get("message")
        biz_code = result.get("bizCode")
        raise AgentKitHttpError(
            action,
            reason or "HTTPError",
            message if isinstance(message, str) else "",
            status_code=response.status_code,
            request_id=request_id,
            biz_code=biz_code if type(biz_code) is int else None,
            reason=reason,
        )
    return result


def _snake_case(value: str) -> str:
    value = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).lower()


def normalize_resource_response(value: Any) -> Any:
    """Normalize TOP PascalCase fields to the scripts' snake_case contract.

    The TOP list uses EnvironmentResources instead of data. Opaque maps in
    the specification belong to the caller and must retain their exact keys.
    This applies to responses only; request bodies and IAM are unchanged.
    """
    if isinstance(value, list):
        return [normalize_resource_response(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key == "EnvironmentResources":
            field = "data"
        elif key == "RequestId":
            field = key
        else:
            field = _snake_case(key)
        normalized = (
            item
            if field in {"env_vars", "resources", "networking", "agentkit"}
            else normalize_resource_response(item)
        )
        if isinstance(normalized, str) and field in {
            "status",
            "step",
            "type",
            "resource_mode",
            "profile",
            "provider",
            "ownership",
            "runtime_type",
        }:
            normalized = _snake_case(normalized)
        if field in result and result[field] != normalized:
            raise RuntimeError(f"conflicting response fields for {field}")
        result[field] = normalized
    return result


class EnvironmentResourceHttpClient:
    """TOP uses AK/SK; direct HTTP uses an account-scoped API key."""

    def __init__(self) -> None:
        self.direct = direct_base_url()
        self.endpoint = None if self.direct else resolve_endpoint()
        self.credentials = (
            resolve_credentials(self.endpoint.provider) if self.endpoint else None
        )
        self.api_key = _env("MA_RESOURCE_API_KEY") if self.direct else ""
        if self.direct and not self.api_key:
            raise RuntimeError("set MA_RESOURCE_API_KEY to an account-scoped API key")
        self.timeout = _positive_int_env(
            "AGENTKIT_HTTP_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS
        )
        self.retries = _non_negative_int_env(
            "AGENTKIT_HTTP_RETRIES", DEFAULT_HTTP_RETRIES
        )

    def call(self, action: str, body: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        url = request_url(action)
        for attempt in range(self.retries + 1):
            if self.endpoint and self.credentials:
                headers = sign_headers(
                    "POST",
                    self.endpoint.host,
                    {"Action": action, "Version": self.endpoint.api_version},
                    payload,
                    access_key=self.credentials.access_key,
                    secret_key=self.credentials.secret_key,
                    service=self.endpoint.service,
                    region=self.endpoint.region,
                    session_token=self.credentials.session_token,
                )
            else:
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                }
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    data=payload,
                    timeout=self.timeout,
                    allow_redirects=False,
                )
            except requests.ConnectionError:
                if attempt < self.retries:
                    time.sleep(_backoff_seconds(attempt))
                    continue
                raise RuntimeError(
                    f"{action}: connection failed; retry with the SAME client_token and body"
                ) from None
            except requests.RequestException:
                raise RuntimeError(
                    f"{action}: network error; retry with the SAME client_token and body"
                ) from None
            if (
                response.status_code in RETRYABLE_STATUS_CODES
                and attempt < self.retries
            ):
                time.sleep(_retry_after_seconds(response) or _backoff_seconds(attempt))
                continue
            break

        result = response_json(action, response)
        # A signed TOP route can forward the backend's plain resource JSON.
        # Transport/authentication does not determine the response envelope.
        raw_value = result.get("Result") if "Result" in result else result
        value = normalize_resource_response(raw_value)
        if isinstance(value, dict):
            if action == "ListEnvironmentResources":
                valid = (
                    isinstance(value.get("data"), list)
                    and all(
                        isinstance(item, dict)
                        and isinstance(item.get("resource_id"), str)
                        and bool(item["resource_id"])
                        for item in value["data"]
                    )
                    and (
                        value.get("next_page") is None
                        or isinstance(value["next_page"], str)
                    )
                )
            else:
                valid = (
                    isinstance(value.get("resource_id"), str)
                    and bool(value["resource_id"])
                    and isinstance(value.get("status"), str)
                    and bool(value["status"])
                )
            if valid:
                return value
        # Report shape only: arbitrary response values may contain secrets.
        metadata = result.get("ResponseMetadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        request_id = (
            metadata.get("RequestId")
            or result.get("RequestId")
            or response.headers.get("request-id")
        )
        advice = (
            "The request may already be accepted; query List/Get before resubmitting."
            if action
            in {
                "CreateEnvironmentResource",
                "UpdateEnvironmentResource",
                "DeleteEnvironmentResource",
            }
            else "Check the response fields and endpoint API contract."
        )
        raise RuntimeError(
            f"{action}: unexpected HTTP {response.status_code} response; "
            f"top-level fields={sorted(result)}; "
            f"Result type={type(result.get('Result')).__name__}; "
            f"Result fields={sorted(raw_value) if isinstance(raw_value, dict) else []}; "
            f"RequestId={request_id or '-'}. "
            "Expected a resource object or data[]/EnvironmentResources[] list, plain or inside Result. "
            + advice
        )

    def create_environment_resource(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.call("CreateEnvironmentResource", body)

    def get_environment_resource(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.call("GetEnvironmentResource", body)

    def list_environment_resources(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.call("ListEnvironmentResources", body)

    def update_environment_resource(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.call("UpdateEnvironmentResource", body)

    def delete_environment_resource(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.call("DeleteEnvironmentResource", body)
