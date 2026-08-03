# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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
"""Minimal Volcengine SMS client with a customer-safe output boundary.

The complete API contract lives in ``references/actions.md``.  This module
prefers the official ``ve volcsms`` command surface, then falls back to the
existing customer credential and ArkClaw paths when the CLI is unavailable
before dispatch. It never accepts credentials as command-line arguments or
parses Volcengine CLI configuration files directly.
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import hmac
import io
import json
import os
import re
import subprocess
import socket
import time
import warnings
from dataclasses import dataclass
from functools import reduce
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)
from urllib import error, parse, request

DEFAULT_ENDPOINT = "https://sms.volcengineapi.com"
DEFAULT_SERVICE = "volcSMS"
DEFAULT_REGION = "cn-north-1"
SMS_API_VERSION = "2026-01-01"
VE_CLI_SERVICE = "volcsms"
DEFAULT_TIMEOUT = 15.0
MAX_READ_RETRIES = 2
RETRYABLE_BUSINESS_ERROR_CODES = frozenset({"1015", "1999"})
LIVE_VALIDATION_ACTIONS = frozenset(
    {
        "ListSubAccountForAgent",
        "GetSubAccountDetail",
        "GetSignatureIdentificationList",
        "ListSignatureForAgent",
        "ListSmsTemplateForAgent",
        "ListSecondTemplate",
        "ListSmsSendLogForAgent",
        "ListTotalSendCountStatForAgent",
        "GetBatchTaskDetail",
        "GetBatchTaskList",
    }
)

Params = Union[Mapping[str, Any], Sequence[Tuple[str, Any]]]
CliRunner = Callable[
    [Sequence[str], Mapping[str, str], float],
    subprocess.CompletedProcess,
]


@dataclass(frozen=True)
class ActionSpec:
    version: str
    method: str
    read_only: bool
    reconciliation_action: Optional[str]
    result_fields: frozenset
    idempotency_field: Optional[str] = None


_COMMON_PAGE_FIELDS = {
    "List",
    "list",
    "Items",
    "items",
    "Total",
    "total",
    "Page",
    "page",
    "PageSize",
    "pageSize",
    "PageIndex",
    "pageIndex",
}
_MESSAGE_GROUP_FIELDS = {
    "SubAccount",
    "SubAccountName",
    "ChannelType",
    "ChannelTypes",
    "Status",
    "CreatedAt",
}
_MESSAGE_GROUP_DETAIL_FIELDS = {
    "subAccountId",
    "subAccountName",
    "status",
    "channelTypeToIndustryConfig",
    "channelType",
    "channelTypeCn",
    "industry",
    "industryCn",
}
_QUALIFICATION_FIELDS = {
    "id",
    "purpose",
    "materialName",
    "businessCertificateName",
    "effectSignatures",
    "auditStatus",
    "auditOpinion",
    "auditedAt",
    "usable",
    "isOrder",
}
_SIGNATURE_FIELDS = {
    "Signature",
    "Description",
    "Source",
    "Domain",
    "Scene",
    "ProjectName",
    "AppIcp",
    "Trademark",
    "Status",
    "StatusDescription",
    "SubAccounts",
    "ChannelTypes",
    "ChannelType",
    "Purpose",
    "IdentificationId",
    "IdentificationID",
    "usable",
    "Usable",
    "CreatedAt",
    "UpdatedAt",
}
_TEMPLATE_FIELDS = {
    "TemplateId",
    "templateId",
    "SecondTemplateId",
    "secondTemplateId",
    "TemplateName",
    "templateName",
    "Name",
    "name",
    "Content",
    "content",
    "TemplateParams",
    "templateParams",
    "ParamName",
    "ChannelType",
    "channelType",
    "Signature",
    "signature",
    "Signatures",
    "signatures",
    "SubAccounts",
    "subAccounts",
    "Status",
    "status",
    "StatusDescription",
    "statusDescription",
    "Description",
    "description",
    "Project",
    "project",
    "CreatedAt",
    "createdAt",
    "UpdatedAt",
    "updatedAt",
    "Area",
    "area",
    "ShortUrlConfig",
    "shortUrlConfig",
}
_TEMPLATE_PARAM_FIELDS = {"name", "Name", "ParamName"}
_TEMPLATE_SCALAR_LIST_FIELDS = {
    "Signatures",
    "signatures",
    "SubAccounts",
    "subAccounts",
}
_SHORT_URL_CONFIG_FIELDS = {
    "isEnabled",
    "belong",
    "isNeedClickDetails",
    "uaCheckStrategy",
}
_SIGNATURE_APPLICATION_FIELDS = {
    "applyId",
    "status",
    "reason",
}
_TEMPLATE_APPLICATION_FIELDS = {
    "templateId",
    "status",
    "statusDescription",
    "auditOpinion",
}
_SEND_RESULT_FIELDS = {
    "MessageId",
    "MessageIds",
}
_SEND_LOG_FIELDS = {
    "MessageId",
    "ErrorCode",
    "SendTime",
    "ReceiptTime",
    "TemplateId",
    "Signature",
    "SubAccount",
    "Count",
}
_STAT_FIELDS = {
    "TotalSendCount",
    "TotalAllSendCount",
    "TotalSendSuccessCount",
    "TotalReceiptSuccessCount",
    "TotalReceiptFailureCount",
}
_UPLOAD_FIELDS = {"file", "url"}
_TEMPLATE_DEMO_FIELDS = {
    "fileName",
    "value",
    "contentType",
    "size",
}
_TEMPLATE_DEMO_CSV_MEDIA_TYPES = frozenset(
    {
        "application/octet-stream",
        "application/csv",
        "application/vnd.ms-excel",
        "text/comma-separated-values",
        "text/csv",
    }
)
_BATCH_TASK_FIELDS = {
    "taskId",
    "subAccount",
    "taskName",
    "signature",
    "templateId",
    "templateName",
    "channelType",
    "scheduled",
    "sendTime",
    "fileUrl",
    "status",
    "totalCount",
}
_BATCH_CREATE_FIELDS = {"taskId", "dupCount", "totalCount"}


def _fields(*groups: Iterable[str]) -> frozenset:
    result: Set[str] = set(_COMMON_PAGE_FIELDS)
    for group in groups:
        result.update(group)
    return frozenset(result)


ACTION_REGISTRY: Dict[str, ActionSpec] = {
    "ListSubAccountForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "ListSubAccountForAgent",
        _fields(_MESSAGE_GROUP_FIELDS),
    ),
    "GetSubAccountDetail": ActionSpec(
        SMS_API_VERSION,
        "GET",
        True,
        "GetSubAccountDetail",
        frozenset(_MESSAGE_GROUP_DETAIL_FIELDS),
    ),
    "GetSignatureIdentificationList": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "GetSignatureIdentificationList",
        _fields(_QUALIFICATION_FIELDS),
    ),
    "ListSignatureForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "ListSignatureForAgent",
        _fields(_SIGNATURE_FIELDS),
    ),
    "ListSmsTemplateForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "ListSmsTemplateForAgent",
        _fields(_TEMPLATE_FIELDS),
    ),
    "ListSecondTemplate": ActionSpec(
        SMS_API_VERSION,
        "GET",
        True,
        "ListSecondTemplate",
        _fields(_TEMPLATE_FIELDS),
    ),
    "ApplySmsSignatureV2": ActionSpec(
        SMS_API_VERSION,
        "POST",
        False,
        "ListSignatureForAgent",
        frozenset(_SIGNATURE_APPLICATION_FIELDS),
    ),
    "ApplySmsTemplateV2": ActionSpec(
        SMS_API_VERSION,
        "POST",
        False,
        "ListSmsTemplateForAgent",
        frozenset(_TEMPLATE_APPLICATION_FIELDS),
    ),
    "SendSmsForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        False,
        "ListSmsSendLogForAgent",
        frozenset(_SEND_RESULT_FIELDS),
    ),
    "ListSmsSendLogForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "ListSmsSendLogForAgent",
        _fields(_SEND_LOG_FIELDS),
    ),
    "ListTotalSendCountStatForAgent": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "ListTotalSendCountStatForAgent",
        _fields(_STAT_FIELDS),
    ),
    "GetUploadTosURL": ActionSpec(
        SMS_API_VERSION,
        "GET",
        False,
        None,
        frozenset(_UPLOAD_FIELDS),
    ),
    "TemplateUploadDemo": ActionSpec(
        SMS_API_VERSION,
        "POST",
        True,
        "TemplateUploadDemo",
        frozenset(_TEMPLATE_DEMO_FIELDS),
    ),
    "SetBatchTask": ActionSpec(
        SMS_API_VERSION,
        "POST",
        False,
        "GetBatchTaskDetail",
        frozenset(_BATCH_CREATE_FIELDS),
    ),
    "GetBatchTaskDetail": ActionSpec(
        SMS_API_VERSION,
        "GET",
        True,
        "GetBatchTaskDetail",
        frozenset(_BATCH_TASK_FIELDS),
    ),
    "GetBatchTaskList": ActionSpec(
        SMS_API_VERSION,
        "GET",
        True,
        "GetBatchTaskList",
        _fields(_BATCH_TASK_FIELDS),
    ),
    "ConsentBatchTask": ActionSpec(
        SMS_API_VERSION,
        "POST",
        False,
        "GetBatchTaskDetail",
        frozenset(),
    ),
    "DeleteBatchTask": ActionSpec(
        SMS_API_VERSION,
        "POST",
        False,
        "GetBatchTaskDetail",
        frozenset(),
    ),
}


@dataclass(frozen=True)
class SignedRequest:
    url: str
    method: str
    headers: Mapping[str, str]
    body: bytes
    canonical_query: str
    canonical_request: str
    string_to_sign: str
    authorization: str

    def to_urllib_request(self) -> request.Request:
        return request.Request(
            self.url,
            data=self.body if self.method != "GET" else None,
            headers=dict(self.headers),
            method=self.method,
        )


@dataclass(frozen=True)
class TransportResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class RequestNotSentError(OSError):
    """The transport failed before it could transmit the request."""


class ResponseLostError(OSError):
    """The request may have reached the service but no response was observed."""


class CredentialResolutionError(RuntimeError):
    """No complete supported authentication configuration could be resolved."""


@dataclass(frozen=True)
class ResolvedCredentials:
    access_key: str
    secret_key: str
    session_token: str = ""


def _validated_credential_value(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise CredentialResolutionError(
            "Credential resolution returned invalid credential fields."
        )
    value = value.strip()
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CredentialResolutionError(
            "Credential resolution returned invalid credential fields."
        )
    return value


def _credential_value(credentials: Any, name: str) -> str:
    try:
        value = (
            credentials.get(name)
            if isinstance(credentials, Mapping)
            else getattr(credentials, name, None)
        )
    except Exception as exc:
        raise CredentialResolutionError(
            "The Volcengine CLI credential provider returned unreadable credentials."
        ) from exc
    return _validated_credential_value(value)


class VolcengineCredentialResolver:
    """Reuse one official ve provider instance while resolving fresh credentials."""

    def __init__(
        self,
        env: Mapping[str, str],
        *,
        credential_provider_factory: Optional[Callable[..., Any]] = None,
    ) -> None:
        self._env = env
        self._credential_provider_factory = credential_provider_factory
        self._credential_provider: Any = None

    def resolve(self) -> ResolvedCredentials:
        if self._credential_provider is None:
            provider_factory = self._credential_provider_factory
            if provider_factory is None:
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        from volcenginesdkcore.auth.providers.cli_config_provider import (
                            CLIConfigCredentialProvider,
                        )
                except Exception as exc:
                    raise CredentialResolutionError(
                        "The official Volcengine CLI credential provider is unavailable."
                    ) from exc
                provider_factory = CLIConfigCredentialProvider

            try:
                self._credential_provider = provider_factory(
                    profile_name=str(self._env.get("VOLCENGINE_PROFILE") or "").strip()
                    or None,
                    config_path=None,
                )
            except Exception as exc:
                raise CredentialResolutionError(
                    "Volcengine CLI credential provider initialization failed."
                ) from exc

        try:
            credentials = self._credential_provider.get_credentials()
        except Exception as exc:
            raise CredentialResolutionError(
                "Volcengine CLI credential resolution failed."
            ) from exc

        resolved_access_key = _credential_value(credentials, "ak")
        resolved_secret_key = _credential_value(credentials, "sk")
        if not resolved_access_key or not resolved_secret_key:
            raise CredentialResolutionError(
                "The Volcengine CLI credential provider returned incomplete credentials."
            )
        return ResolvedCredentials(
            access_key=resolved_access_key,
            secret_key=resolved_secret_key,
            session_token=_credential_value(credentials, "session_token"),
        )


def _resolve_environment_credentials(
    env: Mapping[str, str],
) -> Optional[ResolvedCredentials]:
    access_key = _validated_credential_value(env.get("VOLCENGINE_ACCESS_KEY"))
    secret_key = _validated_credential_value(env.get("VOLCENGINE_SECRET_KEY"))
    if not access_key or not secret_key:
        return None
    return ResolvedCredentials(
        access_key=access_key,
        secret_key=secret_key,
        session_token=_validated_credential_value(
            env.get("VOLCENGINE_SESSION_TOKEN")
        ),
    )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hmac(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()


def _query_items(params: Params) -> List[Tuple[str, str]]:
    source = params.items() if isinstance(params, Mapping) else params
    items: List[Tuple[str, str]] = []
    for key, value in source:
        values = value if isinstance(value, (list, tuple)) else (value,)
        for item in values:
            if item is None:
                continue
            if isinstance(item, bool):
                text = "true" if item else "false"
            else:
                text = str(item)
            items.append((str(key), text))
    return items


def _encode_query(items: Iterable[Tuple[str, str]]) -> str:
    encoded = [
        (
            parse.quote(key, safe="-_.~"),
            parse.quote(value, safe="-_.~"),
        )
        for key, value in items
    ]
    encoded.sort()
    return "&".join("{}={}".format(key, value) for key, value in encoded)


def _signing_key(secret_key: str, date: str, region: str, service: str) -> bytes:
    key_date = _hmac(secret_key.encode("utf-8"), date)
    key_region = _hmac(key_date, region)
    key_service = _hmac(key_region, service)
    return _hmac(key_service, "request")


def _compact_json(params: Params) -> bytes:
    if not isinstance(params, Mapping):
        raise ValueError("POST parameters must be a JSON object")
    return json.dumps(
        params,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def build_ve_cli_command(
    action: str,
    spec: ActionSpec,
    params: Params,
    env: Mapping[str, str],
) -> List[str]:
    """Build one shell-free ``ve volcsms`` invocation."""
    command = ["ve", VE_CLI_SERVICE, action]
    if spec.method.upper() == "POST":
        command.extend(["--body", _compact_json(params).decode("utf-8")])
    else:
        for key, value in _query_items(params):
            command.extend(["--{}".format(key), value])

    profile = _validated_credential_value(env.get("VOLCENGINE_PROFILE"))
    if profile:
        command.extend(["---profile", profile])
    region = _validated_credential_value(env.get("VOLCENGINE_REGION"))
    command.extend(["---region", region or DEFAULT_REGION])
    return command


def _subprocess_cli_runner(
    command: Sequence[str],
    env: Mapping[str, str],
    timeout: float,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(command),
        env=dict(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def build_arkclaw_request(
    spec: ActionSpec,
    params: Params,
    api_base: str,
    api_key: str,
    *,
    action: Optional[str] = None,
    service: str = DEFAULT_SERVICE,
) -> SignedRequest:
    """Build an unsigned SkillHub request authenticated by ArkClaw Bearer."""
    if action is None:
        matches = [name for name, value in ACTION_REGISTRY.items() if value is spec]
        if len(matches) != 1:
            raise ValueError("action is required for an unregistered ActionSpec")
        action = matches[0]

    normalized_base = _validated_credential_value(api_base)
    normalized_key = _validated_credential_value(api_key)
    if not normalized_base or not normalized_key:
        raise CredentialResolutionError(
            "ARK_SKILL_API_BASE and ARK_SKILL_API_KEY must both be set."
        )
    if "://" not in normalized_base:
        normalized_base = "https://{}".format(normalized_base)
    parsed_base = parse.urlsplit(normalized_base.rstrip("/"))
    if (
        parsed_base.scheme not in {"http", "https"}
        or not parsed_base.netloc
        or parsed_base.username is not None
        or parsed_base.password is not None
        or parsed_base.query
        or parsed_base.fragment
    ):
        raise CredentialResolutionError(
            "ARK_SKILL_API_BASE must be an absolute HTTP(S) gateway URL "
            "without credentials, query parameters, or fragments."
        )

    method = spec.method.upper()
    query_items = [("Action", action), ("Version", spec.version)]
    if method == "GET":
        query_items.extend(_query_items(params))
        body = b""
    else:
        body = _compact_json(params)
    canonical_query = _encode_query(query_items)
    path = parsed_base.path or "/"
    base_url = parse.urlunsplit(
        (parsed_base.scheme, parsed_base.netloc, path, "", "")
    )
    authorization = "Bearer {}".format(normalized_key)
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json; charset=utf-8",
        "ServiceName": service,
    }
    return SignedRequest(
        url="{}?{}".format(base_url, canonical_query),
        method=method,
        headers=headers,
        body=body,
        canonical_query=canonical_query,
        canonical_request="",
        string_to_sign="",
        authorization=authorization,
    )


def build_signed_request(
    spec: ActionSpec,
    params: Params,
    access_key: str,
    secret_key: str,
    now: datetime.datetime,
    *,
    action: Optional[str] = None,
    endpoint: str = DEFAULT_ENDPOINT,
    region: str = DEFAULT_REGION,
    service: str = DEFAULT_SERVICE,
    session_token: str = "",
) -> SignedRequest:
    """Build a V4-signed request and expose its canonical values for tests."""
    if action is None:
        matches = [name for name, value in ACTION_REGISTRY.items() if value is spec]
        if len(matches) != 1:
            raise ValueError("action is required for an unregistered ActionSpec")
        action = matches[0]

    parsed_endpoint = parse.urlsplit(endpoint.rstrip("/"))
    if parsed_endpoint.scheme != "https" or not parsed_endpoint.netloc:
        raise ValueError("VOLCENGINE_SMS_ENDPOINT must be an absolute HTTPS URL")
    path = parsed_endpoint.path or "/"
    path = parse.quote(parse.unquote(path), safe="/-_.~")
    method = spec.method.upper()
    if method == "GET":
        body = b""
        query_items = [("Action", action), ("Version", spec.version)]
        query_items.extend(_query_items(params))
    else:
        body = _compact_json(params)
        query_items = [("Action", action), ("Version", spec.version)]
    canonical_query = _encode_query(query_items)

    utc_now = now.astimezone(datetime.timezone.utc)
    x_date = utc_now.strftime("%Y%m%dT%H%M%SZ")
    short_date = x_date[:8]
    body_hash = _sha256(body)
    canonical_headers: Dict[str, str] = {
        "host": parsed_endpoint.netloc,
        "x-content-sha256": body_hash,
        "x-date": x_date,
    }
    if method != "GET":
        canonical_headers["content-type"] = "application/json"
    if session_token:
        canonical_headers["x-security-token"] = session_token
    signed_header_names = ";".join(sorted(canonical_headers))
    canonical_header_text = "".join(
        "{}:{}\n".format(name, canonical_headers[name].strip())
        for name in sorted(canonical_headers)
    )
    canonical_request = "\n".join(
        [
            method,
            path,
            canonical_query,
            canonical_header_text,
            signed_header_names,
            body_hash,
        ]
    )
    scope = "{}/{}/{}/request".format(short_date, region, service)
    string_to_sign = "\n".join(
        ["HMAC-SHA256", x_date, scope, _sha256(canonical_request.encode("utf-8"))]
    )
    signature = hmac.new(
        _signing_key(secret_key, short_date, region, service),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    authorization = (
        "HMAC-SHA256 Credential={}/{}, SignedHeaders={}, Signature={}"
    ).format(access_key, scope, signed_header_names, signature)
    headers = {
        "Host": parsed_endpoint.netloc,
        "X-Date": x_date,
        "X-Content-Sha256": body_hash,
        "Authorization": authorization,
    }
    if method != "GET":
        headers["Content-Type"] = "application/json"
    if session_token:
        headers["X-Security-Token"] = session_token
    base_url = parse.urlunsplit(
        (parsed_endpoint.scheme, parsed_endpoint.netloc, path, "", "")
    )
    return SignedRequest(
        url="{}?{}".format(base_url, canonical_query),
        method=method,
        headers=headers,
        body=body,
        canonical_query=canonical_query,
        canonical_request=canonical_request,
        string_to_sign=string_to_sign,
        authorization=authorization,
    )


def _urllib_transport(req: request.Request, timeout: float) -> TransportResponse:
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return TransportResponse(
                int(response.getcode()),
                dict(response.headers.items()),
                response.read(),
            )
    except error.HTTPError as exc:
        return TransportResponse(
            int(exc.code),
            dict(exc.headers.items()) if exc.headers else {},
            exc.read() if hasattr(exc, "read") else b"",
        )
    except (socket.timeout, TimeoutError) as exc:
        raise ResponseLostError(str(exc)) from exc
    except error.URLError as exc:
        # urllib does not expose a reliable "zero request bytes written" signal.
        # Keep failures ambiguous for mutations; reads can safely retry them.
        raise ResponseLostError(str(exc.reason)) from exc
    except (ConnectionError, OSError) as exc:
        raise ResponseLostError(str(exc)) from exc


_PHONE_RE = re.compile(r"(?<!\d)(?:\+?86)?(1[3-9]\d)(\d{4})(\d{4})(?!\d)")
_URL_RE = re.compile(r"https?://[^\s\"'<>]+")
_AUTH_RE = re.compile(r"(?i)\bAuthorization\s*[:=]\s*[^\r\n]+")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/\-=]+")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_VE_SAFE_FALLBACK_PATTERNS = (
    "credentials not configured",
    "no valid providers in chain",
    "region not set",
    "unknown command",
    "unknown flag",
    "flag provided but not defined",
    "unsupport action",
    "unsupported action",
    "executable file not found",
    "no such file or directory",
    "must set value",
    "is not support command",
    "is not a valid flag",
)
_SENSITIVE_KEYS = {
    "authorization",
    "accesskey",
    "access_key",
    "secretkey",
    "secret_key",
    "ak",
    "sk",
    "token",
    "sessiontoken",
    "xsecuritytoken",
    "identitycard",
    "identitycardnumber",
    "uploadfilelist",
    "materialurl",
    "callbackurl",
}


def _completed_bytes(value: Any) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    return str(value).encode("utf-8", errors="replace")


def _extract_json_object(value: bytes) -> Optional[Mapping[str, Any]]:
    """Extract the first JSON object from CLI stdout or stderr."""
    text = _ANSI_RE.sub("", value.decode("utf-8", errors="replace"))
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping):
            return payload
    return None


def _ve_failure_is_safe_to_fallback(value: bytes) -> bool:
    text = _ANSI_RE.sub("", value.decode("utf-8", errors="replace")).lower()
    profile_not_found = "profile \"" in text and "\" not found" in text
    config_permission_error = ".volcengine/" in text and (
        "operation not permitted" in text or "permission denied" in text
    )
    return profile_not_found or config_permission_error or any(
        pattern in text for pattern in _VE_SAFE_FALLBACK_PATTERNS
    )


def _sanitize_text(
    value: str,
    secrets: Sequence[str],
    *,
    strip_url_query: bool = True,
) -> str:
    safe = reduce(
        lambda redacted, literal: (
            redacted.replace(literal, "[REDACTED]") if literal else redacted
        ),
        secrets,
        value,
    )
    safe = _AUTH_RE.sub("Authorization: [REDACTED]", safe)
    safe = _BEARER_RE.sub("Bearer [REDACTED]", safe)
    safe = _PHONE_RE.sub(
        lambda match: "{}****{}".format(match.group(1), match.group(3)), safe
    )

    def strip_url(match: re.Match) -> str:
        raw = match.group(0)
        parsed = parse.urlsplit(raw)
        return parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))

    if strip_url_query:
        safe = _URL_RE.sub(strip_url, safe)
    if len(safe) > 1024:
        safe = safe[:1021] + "..."
    return safe


def sanitize_output(value: Any, *, secrets: Sequence[str] = ()) -> Any:
    """Recursively remove credential-bearing keys and redact sensitive strings."""
    if isinstance(value, Mapping):
        cleaned: Dict[str, Any] = {}
        for key, item in value.items():
            canonical_key = str(key).replace("-", "").replace("_", "").lower()
            if canonical_key in _SENSITIVE_KEYS:
                continue
            cleaned[str(key)] = sanitize_output(item, secrets=secrets)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [sanitize_output(item, secrets=secrets) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value, secrets)
    return value


def _filter_result(
    value: Any,
    allowed_fields: frozenset,
    secrets: Sequence[str],
    *,
    preserve_presigned_url: bool = False,
) -> Any:
    if isinstance(value, Mapping):
        output: Dict[str, Any] = {}
        for key, item in value.items():
            if key not in allowed_fields:
                continue
            if (
                preserve_presigned_url
                and str(key).lower() == "url"
                and isinstance(item, str)
            ):
                output[str(key)] = _sanitize_text(item, secrets, strip_url_query=False)
            else:
                output[str(key)] = _filter_result(
                    item,
                    allowed_fields,
                    secrets,
                    preserve_presigned_url=preserve_presigned_url,
                )
        return output
    if isinstance(value, (list, tuple)):
        return [
            _filter_result(
                item,
                allowed_fields,
                secrets,
                preserve_presigned_url=preserve_presigned_url,
            )
            for item in value
        ]
    return sanitize_output(value, secrets=secrets)


def _filter_template_result(value: Any, secrets: Sequence[str]) -> Any:
    """Filter template results with allowlists scoped to each published path."""
    if not isinstance(value, Mapping):
        return {}

    def filter_nested(item: Any, allowed: Set[str]) -> Any:
        if isinstance(item, Mapping):
            return {
                str(key): sanitize_output(nested, secrets=secrets)
                for key, nested in item.items()
                if key in allowed
                and not isinstance(nested, (Mapping, list, tuple, set))
            }
        if isinstance(item, (list, tuple)):
            return [filter_nested(nested, allowed) for nested in item]
        return sanitize_output(item, secrets=secrets)

    def filter_item(item: Any) -> Any:
        if not isinstance(item, Mapping):
            return sanitize_output(item, secrets=secrets)
        output: Dict[str, Any] = {}
        for key, nested in item.items():
            if key not in _TEMPLATE_FIELDS:
                continue
            if key in {"TemplateParams", "templateParams"}:
                output[str(key)] = filter_nested(nested, _TEMPLATE_PARAM_FIELDS)
            elif key in {"ShortUrlConfig", "shortUrlConfig"}:
                output[str(key)] = filter_nested(
                    nested, _SHORT_URL_CONFIG_FIELDS
                )
            elif key in _TEMPLATE_SCALAR_LIST_FIELDS:
                values = nested if isinstance(nested, (list, tuple)) else ()
                output[str(key)] = [
                    sanitize_output(value, secrets=secrets)
                    for value in values
                    if not isinstance(value, (Mapping, list, tuple, set))
                ]
            elif isinstance(nested, (Mapping, list, tuple, set)):
                # No other template field has a published container contract.
                continue
            else:
                output[str(key)] = sanitize_output(nested, secrets=secrets)
        return output

    output: Dict[str, Any] = {}
    for key, item in value.items():
        if key in {"List", "list", "Items", "items"}:
            values = item if isinstance(item, (list, tuple)) else ()
            output[str(key)] = [
                filter_item(nested) for nested in values if isinstance(nested, Mapping)
            ]
        elif key in _COMMON_PAGE_FIELDS and not isinstance(
            item, (Mapping, list, tuple, set)
        ):
            output[str(key)] = sanitize_output(item, secrets=secrets)
        elif key in _TEMPLATE_FIELDS:
            filtered = filter_item({key: item})
            if key in filtered:
                output[str(key)] = filtered[key]
    return output


def _filter_message_group_detail(value: Any, secrets: Sequence[str]) -> Any:
    """Filter GetSubAccountDetail with field allowlists scoped by JSON path."""
    if not isinstance(value, Mapping):
        return {}

    def is_scalar(item: Any) -> bool:
        return not isinstance(item, (Mapping, list, tuple, set))

    output: Dict[str, Any] = {}
    for key in ("subAccountId", "subAccountName", "status"):
        if key in value and is_scalar(value[key]):
            output[key] = sanitize_output(value[key], secrets=secrets)

    mapping_key = "channelTypeToIndustryConfig"
    if mapping_key in value:
        raw_mappings = value[mapping_key]
        mappings = raw_mappings if isinstance(raw_mappings, (list, tuple)) else ()
        output[mapping_key] = [
            {
                key: sanitize_output(item[key], secrets=secrets)
                for key in ("channelType", "channelTypeCn", "industry", "industryCn")
                if key in item and is_scalar(item[key])
            }
            for item in mappings
            if isinstance(item, Mapping)
        ]
    return output


def _header(headers: Mapping[str, str], name: str) -> Optional[str]:
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return None


def _request_id(payload: Any, headers: Mapping[str, str]) -> Optional[str]:
    if isinstance(payload, Mapping):
        metadata = payload.get("ResponseMetadata")
        if isinstance(metadata, Mapping):
            value = metadata.get("RequestId") or metadata.get("RequestID")
            if value is not None:
                return str(value)
    return _header(headers, "X-Tt-Logid") or _header(headers, "X-Request-Id")


def _business_error_code(response: TransportResponse) -> str:
    try:
        payload = json.loads(response.body.decode("utf-8")) if response.body else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ""
    metadata = payload.get("ResponseMetadata") if isinstance(payload, Mapping) else None
    error_value = (
        metadata.get("Error")
        if isinstance(metadata, Mapping)
        and isinstance(metadata.get("Error"), Mapping)
        else None
    )
    return str(error_value.get("Code") or "") if error_value is not None else ""


def _filename_from_content_disposition(value: Optional[str]) -> str:
    if not value:
        return ""
    for part in value.split(";"):
        key, separator, raw = part.strip().partition("=")
        if not separator or key.lower() not in {"filename", "filename*"}:
            continue
        encoded = raw.strip().strip('"')
        if key.lower() == "filename*" and "''" in encoded:
            encoded = encoded.split("''", 1)[1]
        decoded = parse.unquote(encoded).replace("\\", "/").rsplit("/", 1)[-1]
        if decoded:
            return decoded
    return ""


def _error_envelope(
    action: str,
    code: str,
    message: str,
    *,
    request_id: Optional[str] = None,
    retryable: bool = False,
    outcome_unknown: bool = False,
    secrets: Sequence[str] = (),
) -> Dict[str, Any]:
    return {
        "success": False,
        "action": action,
        "request_id": _sanitize_text(request_id, secrets) if request_id else None,
        "result": None,
        "error": {
            "code": code,
            "message": _sanitize_text(message, secrets),
            "retryable": retryable,
            "outcome_unknown": outcome_unknown,
        },
    }


def _normalize_template_demo_csv(
    action: str,
    spec: ActionSpec,
    response: TransportResponse,
    secrets: Sequence[str],
) -> Dict[str, Any]:
    request_id = _request_id({}, response.headers)
    content_type = _header(response.headers, "Content-Type") or ""
    media_type = content_type.partition(";")[0].strip().lower()
    if not response.body:
        return _error_envelope(
            action,
            "invalid_response",
            "TemplateUploadDemo returned an empty response body",
            request_id=request_id,
            secrets=secrets,
        )
    if media_type not in _TEMPLATE_DEMO_CSV_MEDIA_TYPES:
        return _error_envelope(
            action,
            "invalid_response",
            "TemplateUploadDemo response was not an expected CSV file",
            request_id=request_id,
            secrets=secrets,
        )
    try:
        value = response.body.decode("utf-8-sig")
    except UnicodeDecodeError:
        return _error_envelope(
            action,
            "invalid_response",
            "TemplateUploadDemo CSV was not valid UTF-8",
            request_id=request_id,
            secrets=secrets,
        )
    try:
        first_row = next(csv.reader(io.StringIO(value, newline=""), strict=True))
    except (csv.Error, StopIteration):
        first_row = []
    if not first_row or first_row[0] != "phone":
        return _error_envelope(
            action,
            "invalid_response",
            "TemplateUploadDemo CSV must use phone as its first column",
            request_id=request_id,
            secrets=secrets,
        )

    demo = {
        "fileName": _filename_from_content_disposition(
            _header(response.headers, "Content-Disposition")
        )
        or "TemplateUploadDemo.csv",
        "value": value,
        "contentType": content_type,
        "size": len(response.body),
    }
    return {
        "success": True,
        "action": action,
        "request_id": _sanitize_text(request_id, secrets) if request_id else None,
        "result": _filter_result(demo, spec.result_fields, secrets),
        "error": None,
    }


class SmsApiClient:
    def __init__(
        self,
        *,
        env: Optional[Mapping[str, str]] = None,
        clock: Optional[Callable[[], datetime.datetime]] = None,
        transport: Optional[
            Callable[[request.Request, float], TransportResponse]
        ] = None,
        sleeper: Optional[Callable[[float], None]] = None,
        credential_provider_factory: Optional[Callable[..., Any]] = None,
        cli_runner: Optional[CliRunner] = None,
        prefer_ve_cli: Optional[bool] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._env = dict(os.environ if env is None else env)
        self._clock = clock or (lambda: datetime.datetime.now(datetime.timezone.utc))
        self._transport = transport or _urllib_transport
        self._sleeper = sleeper or time.sleep
        self._credential_resolver = VolcengineCredentialResolver(
            self._env,
            credential_provider_factory=credential_provider_factory,
        )
        self._cli_runner = cli_runner or _subprocess_cli_runner
        if prefer_ve_cli is None:
            self._prefer_ve_cli = cli_runner is not None or (
                transport is None and credential_provider_factory is None
            )
        else:
            self._prefer_ve_cli = prefer_ve_cli
        self._timeout = timeout
        self._idempotency_payloads: MutableMapping[Tuple[str, str], str] = {}

    def _call_via_ve(
        self,
        action: str,
        spec: ActionSpec,
        params: Params,
        secrets: Sequence[str],
        *,
        preserve_presigned_url: bool,
    ) -> Optional[Dict[str, Any]]:
        """Use ``ve volcsms`` first; return ``None`` only for a safe fallback."""
        if not self._prefer_ve_cli:
            return None
        try:
            command = build_ve_cli_command(action, spec, params, self._env)
        except CredentialResolutionError as exc:
            return _error_envelope(
                action,
                "credential_error",
                str(exc),
                secrets=secrets,
            )
        except (TypeError, ValueError) as exc:
            return _error_envelope(
                action,
                "invalid_request",
                str(exc),
                secrets=secrets,
            )

        cli_env = dict(self._env)
        cli_env.pop("ARK_SKILL_API_BASE", None)
        cli_env.pop("ARK_SKILL_API_KEY", None)
        cli_env.setdefault("VOLCENGINE_REGION", DEFAULT_REGION)
        try:
            completed = self._cli_runner(command, cli_env, self._timeout)
        except (FileNotFoundError, PermissionError):
            return None
        except subprocess.TimeoutExpired:
            if spec.read_only:
                return _error_envelope(
                    action,
                    "network_error",
                    "Volcengine CLI timed out",
                    retryable=True,
                    secrets=secrets,
                )
            return _error_envelope(
                action,
                "outcome_unknown",
                "The request may have been accepted but the Volcengine CLI timed out",
                outcome_unknown=True,
                secrets=secrets,
            )
        except OSError:
            # Process creation failed before a child could dispatch the request.
            return None
        except Exception:
            if spec.read_only:
                return _error_envelope(
                    action,
                    "cli_error",
                    "Volcengine CLI execution failed before a valid response",
                    retryable=False,
                    secrets=secrets,
                )
            return _error_envelope(
                action,
                "outcome_unknown",
                "The Volcengine CLI result is unknown",
                outcome_unknown=True,
                secrets=secrets,
            )

        stdout = _completed_bytes(getattr(completed, "stdout", b""))
        stderr = _completed_bytes(getattr(completed, "stderr", b""))
        payload = _extract_json_object(stdout) or _extract_json_object(stderr)
        if payload is not None:
            response = TransportResponse(
                200,
                {},
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8"),
            )
            return self._normalize(
                action,
                spec,
                response,
                secrets,
                preserve_presigned_url=(
                    preserve_presigned_url and action == "GetUploadTosURL"
                ),
            )

        return_code = int(getattr(completed, "returncode", 1))
        if return_code == 0:
            if action == "TemplateUploadDemo" and stdout:
                return _normalize_template_demo_csv(
                    action,
                    spec,
                    TransportResponse(
                        200,
                        {"Content-Type": "application/octet-stream"},
                        stdout,
                    ),
                    secrets,
                )
            return _error_envelope(
                action,
                "invalid_response",
                "Volcengine CLI returned no valid JSON response",
                secrets=secrets,
            )

        failure_output = stderr + b"\n" + stdout
        if _ve_failure_is_safe_to_fallback(failure_output) or spec.read_only:
            return None
        return _error_envelope(
            action,
            "outcome_unknown",
            "The request may have been accepted but the Volcengine CLI "
            "returned no valid response",
            outcome_unknown=True,
            secrets=secrets,
        )

    def call_live_read_only(
        self, action: str, params: Params
    ) -> Dict[str, Any]:
        """Dispatch a live smoke request only after a hard mutation-proof gate."""
        if action not in LIVE_VALIDATION_ACTIONS:
            return _error_envelope(
                action,
                "live_validation_action_denied",
                "Action is not allowed by the read-only live validation policy",
            )
        return self.call(action, params)

    def call(
        self,
        action: str,
        params: Params,
        *,
        idempotency_key: Optional[str] = None,
        preserve_presigned_url: bool = False,
    ) -> Dict[str, Any]:
        spec = ACTION_REGISTRY.get(action)
        if spec is None:
            return _error_envelope(
                action, "unknown_action", "Action is not in the external contract"
            )

        environment_secrets = tuple(
            value
            for value in (
                self._env.get("ARK_SKILL_API_KEY"),
                self._env.get("VOLCENGINE_ACCESS_KEY"),
                self._env.get("VOLCENGINE_SECRET_KEY"),
                self._env.get("VOLCENGINE_SESSION_TOKEN"),
            )
            if isinstance(value, str) and value
        )
        raw_ark_base = self._env.get("ARK_SKILL_API_BASE")
        raw_ark_key = self._env.get("ARK_SKILL_API_KEY")
        ark_base = ""
        ark_key = ""

        if idempotency_key is not None:
            if spec.idempotency_field is None:
                return _error_envelope(
                    action,
                    "idempotency_not_supported",
                    "This Action has no contracted idempotency field",
                    secrets=environment_secrets,
                )
            payload_hash = _sha256(_compact_json(params))
            identity = (action, idempotency_key)
            previous = self._idempotency_payloads.get(identity)
            if previous is not None and previous != payload_hash:
                return _error_envelope(
                    action,
                    "idempotency_conflict",
                    "The idempotency key was already bound to a different request",
                    secrets=environment_secrets,
                )
            self._idempotency_payloads[identity] = payload_hash

        cli_result = self._call_via_ve(
            action,
            spec,
            params,
            environment_secrets,
            preserve_presigned_url=preserve_presigned_url,
        )
        if cli_result is not None:
            return cli_result

        try:
            try:
                credentials = self._credential_resolver.resolve()
            except CredentialResolutionError:
                credentials = _resolve_environment_credentials(self._env)
                if credentials is None:
                    ark_base = _validated_credential_value(raw_ark_base)
                    ark_key = _validated_credential_value(raw_ark_key)
                    if bool(ark_base) != bool(ark_key):
                        raise CredentialResolutionError(
                            "ARK_SKILL_API_BASE and ARK_SKILL_API_KEY must both be set."
                        )
                    if not ark_base:
                        raise CredentialResolutionError(
                            "No usable authentication configuration. Run ve login, "
                            "set a complete VOLCENGINE_ACCESS_KEY and "
                            "VOLCENGINE_SECRET_KEY pair, or inject both "
                            "ARK_SKILL_API_BASE and ARK_SKILL_API_KEY."
                        )
        except CredentialResolutionError as exc:
            return _error_envelope(
                action,
                "credential_error",
                str(exc),
                secrets=environment_secrets,
            )
        resolved_secrets = (
            ()
            if credentials is None
            else (
                credentials.access_key,
                credentials.secret_key,
                credentials.session_token,
            )
        )
        secrets = environment_secrets + tuple(
            value for value in resolved_secrets if value
        )

        try:
            if ark_base and ark_key:
                outbound_request = build_arkclaw_request(
                    spec,
                    params,
                    ark_base,
                    ark_key,
                    action=action,
                )
            else:
                assert credentials is not None
                outbound_request = build_signed_request(
                    spec,
                    params,
                    credentials.access_key,
                    credentials.secret_key,
                    self._clock(),
                    action=action,
                    endpoint=DEFAULT_ENDPOINT,
                    session_token=credentials.session_token,
                )
        except CredentialResolutionError as exc:
            return _error_envelope(
                action,
                "credential_error",
                str(exc),
                secrets=secrets,
            )
        except (TypeError, ValueError) as exc:
            return _error_envelope(action, "invalid_request", str(exc), secrets=secrets)

        attempts = 1 + (MAX_READ_RETRIES if spec.read_only else 0)
        for attempt in range(attempts):
            try:
                transport_response = self._transport(
                    outbound_request.to_urllib_request(), self._timeout
                )
            except RequestNotSentError as exc:
                if spec.read_only and attempt + 1 < attempts:
                    self._sleeper(0.5 * (2**attempt))
                    continue
                return _error_envelope(
                    action,
                    "network_error",
                    str(exc),
                    retryable=spec.read_only,
                    secrets=secrets,
                )
            except ResponseLostError as exc:
                if spec.read_only and attempt + 1 < attempts:
                    self._sleeper(0.5 * (2**attempt))
                    continue
                if not spec.read_only:
                    return _error_envelope(
                        action,
                        "outcome_unknown",
                        "The request may have been accepted but its response was lost",
                        outcome_unknown=True,
                        secrets=secrets,
                    )
                return _error_envelope(
                    action,
                    "network_error",
                    str(exc),
                    retryable=True,
                    secrets=secrets,
                )
            except Exception as exc:  # Transport plugins must not leak tracebacks.
                return _error_envelope(
                    action, "transport_error", str(exc), secrets=secrets
                )

            retryable_status = (
                transport_response.status == 429
                or 500 <= transport_response.status <= 599
            )
            if spec.read_only and retryable_status and attempt + 1 < attempts:
                retry_after = _header(transport_response.headers, "Retry-After")
                delay = 0.5 * (2**attempt)
                if retry_after:
                    try:
                        delay = max(0.0, min(float(retry_after), 10.0))
                    except ValueError:
                        pass
                self._sleeper(delay)
                continue
            business_error_code = _business_error_code(transport_response)
            if (
                spec.read_only
                and business_error_code in RETRYABLE_BUSINESS_ERROR_CODES
                and attempt + 1 < attempts
            ):
                self._sleeper(0.5 * (2**attempt))
                continue
            return self._normalize(
                action,
                spec,
                transport_response,
                secrets,
                preserve_presigned_url=(
                    preserve_presigned_url and action == "GetUploadTosURL"
                ),
            )

        return _error_envelope(  # Defensive: the loop always returns.
            action, "internal_error", "No transport result", secrets=secrets
        )

    @staticmethod
    def _normalize(
        action: str,
        spec: ActionSpec,
        response: TransportResponse,
        secrets: Sequence[str],
        *,
        preserve_presigned_url: bool = False,
    ) -> Dict[str, Any]:
        if (
            action == "TemplateUploadDemo"
            and 200 <= response.status < 300
            and not response.body
        ):
            return _normalize_template_demo_csv(action, spec, response, secrets)
        try:
            payload = json.loads(response.body.decode("utf-8")) if response.body else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            if action == "TemplateUploadDemo" and 200 <= response.status < 300:
                return _normalize_template_demo_csv(action, spec, response, secrets)
            if 200 <= response.status < 300:
                return _error_envelope(
                    action,
                    "invalid_response",
                    "Service response was not valid JSON",
                    request_id=_request_id({}, response.headers),
                    secrets=secrets,
                )
            return _error_envelope(
                action,
                "http_{}".format(response.status),
                "HTTP {} returned a non-JSON response".format(response.status),
                request_id=_request_id({}, response.headers),
                retryable=spec.read_only
                and (response.status == 429 or 500 <= response.status <= 599),
                secrets=secrets,
            )

        request_id = _request_id(payload, response.headers)
        metadata = (
            payload.get("ResponseMetadata") if isinstance(payload, Mapping) else None
        )
        business_error = (
            metadata.get("Error")
            if isinstance(metadata, Mapping)
            and isinstance(metadata.get("Error"), Mapping)
            else None
        )
        if business_error is not None:
            business_code = str(
                business_error.get("Code") or "service_error"
            )
            return _error_envelope(
                action,
                business_code,
                "Service returned error {}".format(
                    business_code
                ),
                request_id=request_id,
                retryable=spec.read_only
                and (
                    response.status == 429
                    or 500 <= response.status <= 599
                    or business_code in RETRYABLE_BUSINESS_ERROR_CODES
                ),
                secrets=secrets,
            )
        if not 200 <= response.status < 300:
            return _error_envelope(
                action,
                "http_{}".format(response.status),
                "HTTP {}".format(response.status),
                request_id=request_id,
                retryable=spec.read_only
                and (response.status == 429 or 500 <= response.status <= 599),
                secrets=secrets,
            )
        if not isinstance(payload, Mapping):
            return _error_envelope(
                action,
                "invalid_response",
                "Service response root must be a JSON object",
                request_id=request_id,
                secrets=secrets,
            )
        if action == "GetSubAccountDetail":
            result = _filter_message_group_detail(payload.get("Result"), secrets)
        elif action in {"ListSmsTemplateForAgent", "ListSecondTemplate"}:
            result = _filter_template_result(payload.get("Result"), secrets)
        else:
            result = _filter_result(
                payload.get("Result"),
                spec.result_fields,
                secrets,
                preserve_presigned_url=preserve_presigned_url,
            )
        return {
            "success": True,
            "action": action,
            "request_id": _sanitize_text(request_id, secrets) if request_id else None,
            "result": result,
            "error": None,
        }


def emit_json(value: Any, *, secrets: Sequence[str] = ()) -> str:
    """Return stable JSON suitable for stdout/stderr without leaking secrets."""
    return json.dumps(
        sanitize_output(value, secrets=secrets),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
