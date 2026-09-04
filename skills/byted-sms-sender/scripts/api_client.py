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
customer's V4 AK/SK credentials when the CLI is unavailable before dispatch.
It never accepts credentials as command-line arguments. Browser-login
credentials are read only from the Skill-owned private temporary CLI HOME.
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import hmac
import io
import json
import os
import pathlib
import re
import shutil
import socket
import stat
import subprocess
import tempfile
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

from action_contracts import (
    ACTION_REGISTRY,
    COMMON_PAGE_FIELDS,
    LIVE_VALIDATION_ACTIONS,
    TEMPLATE_DEMO_CSV_MEDIA_TYPES,
    TEMPLATE_FIELDS,
    TEMPLATE_PARAM_FIELDS,
    TEMPLATE_SCALAR_LIST_FIELDS,
    ActionSpec,
)

DEFAULT_ENDPOINT = "https://sms.volcengineapi.com"
DEFAULT_SERVICE = "volcSMS"
DEFAULT_REGION = "cn-north-1"
VE_CLI_SERVICE = "volcsms"
MIN_VE_CLI_VERSION = (1, 1, 0)
MIN_VE_CLI_VERSION_TEXT = "1.1.0"
VE_CLI_INSTALL_ARGV = ("npm", "install", "-g", "@volcengine/cli@1.1.1")
VE_CLI_RELEASE_URL = (
    "https://github.com/volcengine/volcengine-cli/releases/tag/v1.1.1"
)
VE_CLI_CHECKSUMS_URL = (
    "https://github.com/volcengine/volcengine-cli/releases/download/v1.1.1/"
    "volcengine-cli_1.1.1_SHA256SUMS"
)
DEFAULT_TIMEOUT = 15.0
DEFAULT_ENV_PATH = "~/.openclaw/.env"
LOGIN_PROCESS_LEASE_SECONDS = 30 * 60
MAX_READ_RETRIES = 2
MAX_CLI_CACHE_BYTES = 256 * 1024
AUTH_HOME_PREFIX = "volcengine-sms-auth-"
RETRYABLE_BUSINESS_ERROR_CODES = frozenset({"1015", "1999"})

Params = Union[Mapping[str, Any], Sequence[Tuple[str, Any]]]
CliRunner = Callable[
    [Sequence[str], Mapping[str, str], float],
    subprocess.CompletedProcess,
]

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


class IncompleteCredentialsError(CredentialResolutionError):
    """A supported credential source was selected but only partly configured."""


class _TemporaryAuthHomeValidationError(RuntimeError):
    """A newly created auth HOME did not remain inside its trusted temp base."""


class _TemporaryAuthHomeCleanupError(RuntimeError):
    """An empty auth HOME could not be removed after initialization failed."""

    def __init__(self, path: str) -> None:
        super().__init__("Temporary authentication HOME cleanup failed.")
        self.path = path


@dataclass(frozen=True)
class ResolvedCredentials:
    access_key: str
    secret_key: str
    session_token: str = ""


@dataclass(frozen=True)
class VeCallOutcome:
    """A CLI result or the actionable error to restore after direct fallback."""

    result: Optional[Dict[str, Any]]
    fallback_error: Optional[Dict[str, Any]] = None


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


def _safe_cli_json_file(path: pathlib.Path) -> Optional[Mapping[str, Any]]:
    try:
        file_stat = path.lstat()
        if (
            not stat.S_ISREG(file_stat.st_mode)
            or file_stat.st_size > MAX_CLI_CACHE_BYTES
        ):
            return None
        if hasattr(os, "getuid") and file_stat.st_uid != os.getuid():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, Mapping) else None


def _cli_cache_timestamp(value: Any) -> Optional[float]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    try:
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.timestamp()


def _cli_cache_expiry(
    value: Mapping[str, Any], path: pathlib.Path
) -> Optional[float]:
    token = value.get("access_token")
    token = token if isinstance(token, Mapping) else value
    for name in ("expired_time", "expiredTime", "Expiration", "expiration"):
        expiry = _cli_cache_timestamp(token.get(name) or value.get(name))
        if expiry is not None:
            return expiry
    try:
        duration = int(token.get("expires_in") or value.get("expires_in"))
    except (TypeError, ValueError):
        return None
    issued_at = _cli_cache_timestamp(
        token.get("issued_at") or value.get("issued_at")
    )
    if issued_at is None:
        try:
            issued_at = path.stat().st_mtime
        except OSError:
            return None
    return issued_at + duration


def _credentials_from_cli_cache(
    value: Mapping[str, Any], path: pathlib.Path
) -> Optional[ResolvedCredentials]:
    token = value.get("access_token")
    token = token if isinstance(token, Mapping) else value
    try:
        access_key = _validated_credential_value(
            token.get("access_key_id")
            or token.get("AccessKeyId")
            or token.get("accessKeyId")
        )
        secret_key = _validated_credential_value(
            token.get("secret_access_key")
            or token.get("SecretAccessKey")
            or token.get("secretAccessKey")
        )
        session_token = _validated_credential_value(
            token.get("session_token")
            or token.get("SessionToken")
            or token.get("sessionToken")
        )
    except CredentialResolutionError:
        return None
    expiry = _cli_cache_expiry(value, path)
    if expiry is not None and expiry <= time.time() + 30:
        return None
    if not access_key or not secret_key or not session_token:
        return None
    return ResolvedCredentials(access_key, secret_key, session_token)


def _profile_login_session(home: pathlib.Path, profile: str) -> str:
    config = _safe_cli_json_file(home / ".volcengine" / "config.json")
    if config is None:
        return ""
    profiles = config.get("profiles")
    if not isinstance(profiles, Mapping):
        return ""
    selected = profile or str(config.get("current") or "default").strip()
    profile_value = profiles.get(selected)
    if not isinstance(profile_value, Mapping):
        return ""
    return str(
        profile_value.get("login-session")
        or profile_value.get("login_session")
        or ""
    ).strip()


def _resolve_cli_login_cache(
    home_value: str, profile: str = ""
) -> Optional[ResolvedCredentials]:
    home = pathlib.Path(home_value)
    cache_dir = home / ".volcengine" / "login" / "cache"
    if not cache_dir.is_dir():
        return None
    expected_session = _profile_login_session(home, profile)
    candidates = []
    try:
        paths = list(cache_dir.glob("*.json"))
    except OSError:
        return None
    for path in paths:
        value = _safe_cli_json_file(path)
        if value is None:
            continue
        session = str(value.get("login_session") or "").strip()
        if expected_session and session != expected_session:
            continue
        credentials = _credentials_from_cli_cache(value, path)
        if credentials is None:
            continue
        try:
            candidates.append((path.stat().st_mtime, credentials))
        except OSError:
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


class VolcengineCredentialResolver:
    """Reuse one official ve provider instance while resolving fresh credentials."""

    def __init__(
        self,
        env: Mapping[str, str],
        *,
        credential_provider_factory: Optional[Callable[..., Any]] = None,
        cli_home: str = "",
        refresh_cli_cache: Optional[Callable[[], None]] = None,
    ) -> None:
        self._env = env
        self._credential_provider_factory = credential_provider_factory
        self._credential_provider: Any = None
        self._cli_home = cli_home
        self._refresh_cli_cache = refresh_cli_cache

    def resolve(self) -> ResolvedCredentials:
        profile = str(self._env.get("VOLCENGINE_PROFILE") or "").strip()
        if self._cli_home:
            credentials = _resolve_cli_login_cache(self._cli_home, profile)
            if credentials is None and self._refresh_cli_cache is not None:
                self._refresh_cli_cache()
                credentials = _resolve_cli_login_cache(self._cli_home, profile)
            if credentials is not None:
                return credentials
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
                    profile_name=profile or None,
                    config_path=(
                        str(pathlib.Path(self._cli_home) / ".volcengine" / "config.json")
                        if self._cli_home
                        else None
                    ),
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


def _resolve_credential_group(
    env: Mapping[str, str],
    access_key_name: str,
    secret_key_name: str,
    session_token_name: str,
) -> Optional[ResolvedCredentials]:
    access_key = _validated_credential_value(env.get(access_key_name))
    secret_key = _validated_credential_value(env.get(secret_key_name))
    session_token = _validated_credential_value(env.get(session_token_name))
    if not access_key and not secret_key and not session_token:
        return None
    if not access_key or not secret_key:
        raise IncompleteCredentialsError(
            "Incomplete Volcengine credentials. Configure "
            "VOLCENGINE_ACCESS_KEY and VOLCENGINE_SECRET_KEY together."
        )
    return ResolvedCredentials(
        access_key=access_key,
        secret_key=secret_key,
        session_token=session_token,
    )


def _resolve_environment_credentials(
    env: Mapping[str, str],
) -> Optional[ResolvedCredentials]:
    credentials = _resolve_credential_group(
        env,
        "VOLCENGINE_ACCESS_KEY",
        "VOLCENGINE_SECRET_KEY",
        "VOLCENGINE_SESSION_TOKEN",
    )
    if credentials is not None:
        return credentials
    return _resolve_credential_group(
        env,
        "VOLC_ACCESS_KEY",
        "VOLC_SECRET_KEY",
        "VOLC_SESSION_TOKEN",
    )


def _read_env_file(env_path: str) -> Dict[str, str]:
    resolved_path = os.path.expanduser(env_path)
    if not os.path.isfile(resolved_path):
        return {}

    values: Dict[str, str] = {}
    try:
        with open(resolved_path, "r", encoding="utf-8-sig") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export ") :].lstrip()

                key, separator, value = line.partition("=")
                if not separator:
                    continue
                key = key.strip()
                value = value.strip()
                if (
                    len(value) >= 2
                    and value[0] == value[-1]
                    and value[0] in ("'", '"')
                ):
                    value = value[1:-1]
                values[key] = value
    except OSError as exc:
        raise CredentialResolutionError(
            "Unable to read Volcengine credential file: {}".format(resolved_path)
        ) from exc
    return values


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
    command.extend(["---lang", "EN"])
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
_VE_AUTH_REQUIRED_PATTERNS = (
    "credentials not configured",
    "no valid providers in chain",
    "run 've login' to re-authenticate",
    "request parameter refresh_token is invalid",
)
_VE_UNSUPPORTED_PATTERNS = (
    "unknown command",
    "unknown flag",
    "flag provided but not defined",
    "unsupport action",
    "unsupported action",
    "not a supported action",
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
    "ticket",
    "businesscheckticket",
    "operatorcheckticket",
    "responsiblecheckticket",
    "legalcheckticket",
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


def _classify_ve_failure(value: bytes) -> Optional[str]:
    """Classify CLI text only to make read-only failures actionable."""
    text = _ANSI_RE.sub("", value.decode("utf-8", errors="replace")).lower()
    config_permission_error = ".volcengine" in text and (
        "operation not permitted" in text
        or "permission denied" in text
        or "read-only file system" in text
    )
    if config_permission_error:
        return "auth_config_unwritable"
    if "profile \"" in text and "\" not found" in text:
        return "auth_profile_not_found"
    if any(pattern in text for pattern in _VE_AUTH_REQUIRED_PATTERNS):
        return "auth_required"
    if any(pattern in text for pattern in _VE_UNSUPPORTED_PATTERNS):
        return "ve_cli_unsupported"
    return None


_VE_VERSION_RE = re.compile(r"(?<!\d)(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?")


def _parse_ve_version(value: bytes) -> Optional[Tuple[str, Tuple[int, int, int]]]:
    text = _ANSI_RE.sub("", value.decode("utf-8", errors="replace"))
    for line in text.splitlines():
        match = _VE_VERSION_RE.fullmatch(line.strip())
        if match is not None:
            return match.group(0), tuple(int(part) for part in match.groups())
    return None


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
    allowed_fields: Optional[frozenset],
    secrets: Sequence[str],
    *,
    preserve_presigned_url: bool = False,
) -> Any:
    if allowed_fields is None:
        return sanitize_output(value, secrets=secrets)
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
            if key not in TEMPLATE_FIELDS:
                continue
            if key in {"TemplateParams", "templateParams"}:
                output[str(key)] = filter_nested(nested, TEMPLATE_PARAM_FIELDS)
            elif key in {"ShortUrlConfig", "shortUrlConfig"}:
                output[str(key)] = filter_nested(
                    nested, _SHORT_URL_CONFIG_FIELDS
                )
            elif key in TEMPLATE_SCALAR_LIST_FIELDS:
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
        elif key in COMMON_PAGE_FIELDS and not isinstance(
            item, (Mapping, list, tuple, set)
        ):
            output[str(key)] = sanitize_output(item, secrets=secrets)
        elif key in TEMPLATE_FIELDS:
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
    remediation: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    error_value: Dict[str, Any] = {
        "code": code,
        "message": _sanitize_text(message, secrets),
        "retryable": retryable,
        "outcome_unknown": outcome_unknown,
    }
    if remediation:
        error_value["remediation"] = sanitize_output(
            dict(remediation), secrets=secrets
        )
    return {
        "success": False,
        "action": action,
        "request_id": _sanitize_text(request_id, secrets) if request_id else None,
        "result": None,
        "error": error_value,
    }


def _invalid_success_response(
    action: str,
    spec: ActionSpec,
    message: str,
    *,
    request_id: Optional[str],
    secrets: Sequence[str],
) -> Dict[str, Any]:
    """Preserve an ambiguous write outcome when a 2xx body is unusable."""
    if spec.read_only:
        return _error_envelope(
            action,
            "invalid_response",
            message,
            request_id=request_id,
            secrets=secrets,
        )
    return _error_envelope(
        action,
        "outcome_unknown",
        message,
        request_id=request_id,
        outcome_unknown=True,
        secrets=secrets,
    )


def _result_contract_error(spec: ActionSpec, result: Any) -> Optional[str]:
    """Return a structural response error without treating zero as missing."""
    if not spec.required_result_fields and not spec.required_result_any:
        return None
    if not isinstance(result, Mapping):
        return "Service response Result must be a JSON object"
    missing = sorted(
        field for field in spec.required_result_fields if field not in result
    )
    if missing:
        return "Service response Result is missing required field(s): {}".format(
            ", ".join(missing)
        )
    if spec.required_result_any and not any(
        field in result for field in spec.required_result_any
    ):
        return "Service response Result contains none of the expected fields"
    return None


def _skill_login_argv(profile: str = "", *, remote: bool = False) -> List[str]:
    script_path = os.path.realpath(
        os.path.join(os.path.dirname(__file__), "sms_cli.py")
    )
    argv = ["python3", "-B", script_path, "auth-login"]
    if remote:
        argv.append("--remote")
    if profile:
        argv.extend(["--profile", profile])
    return argv


def _login_completion_contract() -> Dict[str, Any]:
    return {
        "wait_for_process_exit": True,
        "poll_same_job_if_async": True,
        "consume_final_json": True,
        "no_customer_login_timeout": True,
        "process_lease_seconds": LOGIN_PROCESS_LEASE_SECONDS,
        "success_match": {"success": True, "result.status": "auth_ready"},
        "conversation_gate": {
            "forbid_business_questions": True,
            "forbid_business_commands": True,
            "forbid_finishing_turn": True,
            "until": "auth_ready",
        },
        "on_success": {
            "customer_message": "授权已完成，我继续处理短信任务。",
            "resume_original_task": True,
        },
    }


def _login_attempt_remediation(
    profile: str = "",
    *,
    target: str = "current",
    env: Optional[Mapping[str, str]] = None,
    continue_with_env: bool = False,
    cleanup: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    remediation: Dict[str, Any] = {
        "action": "run_login",
        "target": target,
        "argv": _skill_login_argv(profile),
        "session": {
            "mode": "managed_async",
            "return_job_handle": True,
            "must_remain_addressable": True,
            "exclusive": True,
            "detach": False,
        },
        "completion": _login_completion_contract(),
        "browser": {"callback": "loopback", "open_automatically": True},
        "fallback": {
            "when": "loopback_unavailable",
            "argv": _skill_login_argv(profile, remote=True),
            "session": {
                "mode": "managed_async",
                "return_job_handle": True,
                "must_remain_addressable": True,
                "exclusive": True,
                "detach": False,
            },
            "completion": _login_completion_contract(),
            "stdin": {
                "kind": "oauth_authorization_code",
                "append_newline": True,
                "sensitive": True,
            },
            "browser": {
                "url_source": "process_stdout",
                "user_controls_authentication": True,
                "prefer_agent_code_handoff": True,
                "fallback": "user_enters_code_in_same_session",
            },
        },
    }
    if target == "host":
        remediation["continue_on_target"] = True
    if env:
        remediation["env"] = dict(env)
    if continue_with_env:
        remediation["continue_with_env"] = True
    if cleanup:
        remediation["cleanup"] = dict(cleanup)
    return remediation


def _alternate_login_browser_handoff(
    profile: str = "",
    *,
    target: str = "current",
    env: Optional[Mapping[str, str]] = None,
    continue_with_env: bool = False,
    cleanup: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    retry = _login_attempt_remediation(
        profile,
        target=target,
        env=env,
        continue_with_env=continue_with_env,
        cleanup=cleanup,
    )
    retry["customer_interaction"] = {
        "audience": "nontechnical",
        "show_commands": False,
        "presentation": "standalone",
        "render_verbatim": True,
        "message": (
            "已重新打开授权页面，请在浏览器确认授权。完成后我会自动继续；如果仍"
            "无法完成授权，请回复“仍无法授权”。"
        ),
        "suppress_repeated_status": True,
    }
    cancel_current_login = {
        "action": "cancel_current_login",
        "required": True,
        "skip_if_already_exited": True,
        "wait_for_exit": True,
        "discard_previous_oauth_state": True,
    }
    handoff: Dict[str, Any] = {
        "action": "wait_for_customer_browser_login",
        "state": "waiting_for_customer_browser_login",
        "current_login_watch": {
            "job_source": "parent_run_login",
            "observe": [
                "before_customer_prompt",
                "while_waiting_for_customer_reply",
                "before_retry_login",
            ],
            "poll_same_job_if_async": True,
            "consume_final_json": True,
            "success_match": {"success": True, "result.status": "auth_ready"},
            "on_success": {
                "action": "resume_original_task",
                "dismiss_customer_wait": True,
                "skip_after_customer_ready": True,
                "customer_message": "授权已完成，我继续处理短信任务。",
            },
            "on_pending_or_non_success": "continue_customer_handoff",
        },
        "customer_interaction": {
            "presentation": "standalone",
            "render_verbatim": True,
            "message": (
                "请在同一个浏览器中，按你平时的方式登录并进入火山引擎控制台；"
                "看到控制台后回复“已进入”。"
            ),
        },
        "wait_for": {
            "customer_reply": "已进入",
            "meaning": "customer_can_see_volcengine_console",
            "is_authentication_proof": False,
        },
        "after_customer_ready": {
            "before_enter": dict(cancel_current_login),
            "next": retry,
        },
        "max_login_retries_after_customer_ready": 1,
        "on_retry_unrecognized": {
            "action": "stop",
            "when": {
                "browser_visible": "agent_observes_authorization_cannot_continue",
                "browser_not_visible": {"customer_reply": "仍无法授权"},
            },
            "before_stop": dict(cancel_current_login),
            "customer_message": (
                "授权页仍未识别到浏览器登录状态。请确认登录火山引擎控制台和授权页"
                "使用的是同一个浏览器。当前环境暂时无法继续自动授权。"
            ),
        },
        "never_request": [
            "enterprise_login_url",
            "account",
            "password",
            "verification_code",
            "authorization_code",
        ],
        "on_abandon": {
            "action": "stop",
            "before_stop": dict(cancel_current_login),
        },
    }
    if cleanup:
        handoff["on_retry_unrecognized"]["cleanup"] = dict(cleanup)
        handoff["on_abandon"]["cleanup"] = dict(cleanup)
    return handoff


def _login_remediation(
    profile: str = "",
    *,
    target: str = "current",
    env: Optional[Mapping[str, str]] = None,
    continue_with_env: bool = False,
    cleanup: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    remediation = _login_attempt_remediation(
        profile,
        target=target,
        env=env,
        continue_with_env=continue_with_env,
        cleanup=cleanup,
    )
    remediation["customer_interaction"] = {
        "audience": "nontechnical",
        "show_diagnostics": False,
        "show_commands": False,
        "start_without_confirmation": True,
        "selection": {
            "action": "request_login_method_choice",
            "invoke_after_login_started": True,
            "render_as_plain_text": False,
            "current_login_watch": {
                "job_source": "parent_run_login",
                "observe": ["before_selection", "while_selection_open"],
                "poll_same_job_if_async": True,
                "consume_final_json": True,
                "success_match": {
                    "success": True,
                    "result.status": "auth_ready",
                },
                "on_success": {
                    "action": "dismiss_or_skip_selection",
                    "resume_original_task": True,
                    "customer_message": "授权已完成，我继续处理短信任务。",
                },
                "on_pending_or_non_success": "show_or_keep_selection",
            },
            "tool": {
                "preferred": "AskUserQuestion",
                "alternatives": [
                    "request_user_input",
                    "equivalent_structured_choice_tool",
                ],
            },
            "header": "火山引擎授权",
            "question": "授权页面已经打开，请选择接下来的登录方式",
            "options": [
                {
                    "id": "password",
                    "label": "账号密码登录",
                    "description": "在已打开的页面输入账号密码并完成授权",
                },
                {
                    "id": "alternate",
                    "label": "其他方式登录",
                    "description": "先按平时方式登录，之后由我继续完成授权",
                },
            ],
            "on_select": {
                "password": {
                    "action": "wait_for_current_login",
                    "use_parent_completion": True,
                },
                "alternate": _alternate_login_browser_handoff(
                    profile,
                    target=target,
                    env=env,
                    continue_with_env=continue_with_env,
                    cleanup=cleanup,
                ),
            },
            "fallback_when_tool_unavailable": {
                "presentation": "standalone_markdown",
                "render_verbatim": True,
                "message": (
                    "## 火山引擎授权\n\n"
                    "授权页面已经打开，请选择接下来的登录方式：\n\n"
                    "1. **账号密码登录** — 在已打开的页面输入账号密码并完成授权\n"
                    "2. **其他方式登录** — 先按平时方式登录，之后由我继续完成授权"
                ),
            },
            "suppress_surrounding_text": True,
            "suppress_repeated_status": True,
        },
    }
    return remediation


def _ve_install_remediation() -> Dict[str, Any]:
    return {
        "action": "install_ve",
        "selection": "npm_if_available_else_official_release",
        "ask_user_to_choose": False,
        "strategies": {
            "npm": {"argv": list(VE_CLI_INSTALL_ARGV)},
            "official_release": {
                "version": "1.1.1",
                "release_url": VE_CLI_RELEASE_URL,
                "checksums_url": VE_CLI_CHECKSUMS_URL,
                "asset_pattern": "volcengine-cli_1.1.1_{os}_{arch}",
                "verify_sha256": True,
                "install_scope": "user_writable_path",
            },
        },
        "postcondition": ["ve", "--version"],
        "customer_interaction": {
            "audience": "nontechnical",
            "show_diagnostics": False,
            "show_commands": False,
        },
    }


def _ve_fallback_error(
    action: str, code: str, *, profile: str = ""
) -> Dict[str, Any]:
    details = {
        "auth_required": (
            "Volcengine CLI is not authenticated.",
            _login_remediation(profile),
        ),
        "auth_profile_not_found": (
            "The selected Volcengine CLI profile does not exist.",
            _login_remediation(profile),
        ),
        "auth_config_unwritable": (
            "Volcengine CLI cannot access its configuration directory.",
            _login_remediation(profile, target="host"),
        ),
        "ve_cli_missing": (
            "The official Volcengine CLI is not installed.",
            _ve_install_remediation(),
        ),
        "ve_cli_unsupported": (
            "The installed Volcengine CLI does not support the required SMS command.",
            _ve_install_remediation(),
        ),
        "ve_cli_unavailable": (
            "The official Volcengine CLI cannot be started.",
            {
                "action": "inspect_ve_executable",
            },
        ),
    }
    message, remediation = details[code]
    return _error_envelope(
        action,
        code,
        message,
        remediation=remediation,
    )


def _create_private_auth_home() -> str:
    temporary_base = os.path.realpath(tempfile.gettempdir())
    if not os.path.isdir(temporary_base) or not os.access(
        temporary_base, os.W_OK | os.X_OK
    ):
        raise OSError("No writable system temporary directory is available.")

    created_path: Optional[str] = None
    owned_path: Optional[str] = None
    try:
        created_path = os.path.abspath(
            tempfile.mkdtemp(
                prefix=AUTH_HOME_PREFIX,
                dir=temporary_base,
            )
        )
        if os.path.dirname(created_path) != temporary_base:
            raise _TemporaryAuthHomeValidationError(
                "Temporary authentication HOME escaped its base directory."
            )
        owned_path = created_path
        if os.path.realpath(created_path) != created_path:
            raise OSError("Temporary authentication HOME changed after creation.")

        path_stat = os.lstat(created_path)
        if not stat.S_ISDIR(path_stat.st_mode):
            raise OSError("Temporary authentication HOME is not a directory.")
        open_flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            open_flags |= os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"):
            open_flags |= os.O_NOFOLLOW
        directory_fd = os.open(created_path, open_flags)
        try:
            opened_stat = os.fstat(directory_fd)
            if (
                not stat.S_ISDIR(opened_stat.st_mode)
                or opened_stat.st_dev != path_stat.st_dev
                or opened_stat.st_ino != path_stat.st_ino
            ):
                raise OSError("Temporary authentication HOME changed before use.")
            if os.name == "posix":
                os.fchmod(directory_fd, 0o700)
                if os.fstat(directory_fd).st_mode & 0o777 != 0o700:
                    raise OSError("Temporary authentication HOME mode is not 0700.")
        finally:
            os.close(directory_fd)

        if not os.access(created_path, os.W_OK | os.X_OK):
            raise OSError("Temporary authentication HOME is not writable.")
        return created_path
    except _TemporaryAuthHomeValidationError:
        raise
    except OSError:
        if owned_path is not None:
            try:
                os.rmdir(owned_path)
            except FileNotFoundError:
                pass
            except OSError as cleanup_error:
                raise _TemporaryAuthHomeCleanupError(owned_path) from cleanup_error
        raise


def prepare_runtime_auth_home() -> str:
    """Return a private, stable CLI HOME under the OS temporary directory."""
    temporary_base = os.path.realpath(tempfile.gettempdir())
    if not os.path.isdir(temporary_base) or not os.access(
        temporary_base, os.W_OK | os.X_OK
    ):
        raise OSError("No writable system temporary directory is available.")

    identity = str(os.getuid()) if hasattr(os, "getuid") else "current-user"
    runtime_home = os.path.join(
        temporary_base, "{}runtime-{}".format(AUTH_HOME_PREFIX, identity)
    )
    if not os.path.isdir(runtime_home):
        try:
            os.mkdir(runtime_home, 0o700)
        except FileExistsError:
            pass
        except PermissionError:
            # Some managed sandboxes report an existing path as PermissionError.
            # The validation below still enforces path, owner, mode, and access.
            if not os.path.isdir(runtime_home):
                raise

    if os.path.realpath(runtime_home) != runtime_home:
        raise OSError("Runtime authentication HOME must not be a symlink.")
    path_stat = os.lstat(runtime_home)
    if not stat.S_ISDIR(path_stat.st_mode):
        raise OSError("Runtime authentication HOME is not a directory.")
    if hasattr(os, "getuid") and path_stat.st_uid != os.getuid():
        raise OSError("Runtime authentication HOME has a different owner.")
    if os.name == "posix":
        os.chmod(runtime_home, 0o700)
        if os.stat(runtime_home).st_mode & 0o777 != 0o700:
            raise OSError("Runtime authentication HOME mode is not 0700.")
    if not os.access(runtime_home, os.W_OK | os.X_OK):
        raise OSError("Runtime authentication HOME is not writable.")
    return runtime_home


def _auth_cleanup_remediation(
    path: str, *, empty_only: bool = False
) -> Dict[str, Any]:
    script_path = os.path.realpath(
        os.path.join(os.path.dirname(__file__), "sms_cli.py")
    )
    argv = ["python3", "-B", script_path, "auth-cleanup", "--path", path]
    if empty_only:
        argv.append("--empty-only")
    return {"action": "run_command", "argv": argv}


def _validated_auth_home_for_cleanup(path: str) -> str:
    if not isinstance(path, str) or not path or path != os.path.abspath(path):
        raise _TemporaryAuthHomeValidationError(
            "Authentication HOME cleanup path must be absolute."
        )

    temporary_base = os.path.realpath(tempfile.gettempdir())
    if os.path.dirname(path) != temporary_base:
        raise _TemporaryAuthHomeValidationError(
            "Authentication HOME cleanup path escaped its temp base."
        )
    name = os.path.basename(path)
    if not name.startswith(AUTH_HOME_PREFIX) or len(name) <= len(AUTH_HOME_PREFIX):
        raise _TemporaryAuthHomeValidationError(
            "Authentication HOME cleanup path has an invalid name."
        )
    if os.path.realpath(path) != path:
        raise _TemporaryAuthHomeValidationError(
            "Authentication HOME cleanup path is not canonical."
        )

    path_stat = os.lstat(path)
    if not stat.S_ISDIR(path_stat.st_mode):
        raise _TemporaryAuthHomeValidationError(
            "Authentication HOME cleanup path is not a directory."
        )
    if os.name == "posix":
        if hasattr(os, "getuid") and path_stat.st_uid != os.getuid():
            raise _TemporaryAuthHomeValidationError(
                "Authentication HOME cleanup path has a different owner."
            )
        if path_stat.st_mode & 0o077:
            raise _TemporaryAuthHomeValidationError(
                "Authentication HOME cleanup path is not private."
            )
    return path


def select_cli_auth_home(env: Optional[Mapping[str, str]] = None) -> str:
    """Reuse a validated Skill-owned HOME, otherwise use the stable temp HOME."""
    values = os.environ if env is None else env
    candidate = str(values.get("HOME") or "")
    if candidate:
        name = os.path.basename(os.path.abspath(candidate))
        if name.startswith(AUTH_HOME_PREFIX):
            return _validated_auth_home_for_cleanup(candidate)
    return prepare_runtime_auth_home()


def prepare_cli_process_environment(env: Mapping[str, str]) -> Dict[str, str]:
    """Build a CLI environment that also works in sanitized POSIX sandboxes."""
    values = dict(env)
    if os.name != "posix" or str(values.get("USER") or ""):
        return values
    try:
        import pwd

        username = pwd.getpwuid(os.getuid()).pw_name
    except (ImportError, KeyError, OSError):
        username = ""
    if username:
        values["USER"] = username
    return values


def cleanup_private_auth_home(
    path: str, *, empty_only: bool = False
) -> Dict[str, Any]:
    action = "auth-cleanup"
    try:
        validated_path = _validated_auth_home_for_cleanup(path)
        if empty_only:
            os.rmdir(validated_path)
        else:
            if not getattr(shutil.rmtree, "avoids_symlink_attacks", False):
                raise _TemporaryAuthHomeValidationError(
                    "Safe recursive authentication HOME cleanup is unavailable."
                )
            shutil.rmtree(validated_path)
    except _TemporaryAuthHomeValidationError:
        return _error_envelope(
            action,
            "auth_cleanup_path_invalid",
            "The authentication HOME cleanup path failed validation.",
        )
    except OSError:
        return _error_envelope(
            action,
            "auth_cleanup_failed",
            "The authentication HOME could not be removed safely.",
        )
    return {
        "success": True,
        "action": action,
        "request_id": None,
        "result": {"status": "cleaned"},
        "error": None,
    }


def _temporary_auth_home_error(
    action: str, *, profile: str = ""
) -> Dict[str, Any]:
    try:
        temporary_home = _create_private_auth_home()
    except _TemporaryAuthHomeValidationError:
        return _error_envelope(
            action,
            "auth_temp_home_invalid",
            "The temporary authentication HOME failed path validation.",
        )
    except _TemporaryAuthHomeCleanupError as exc:
        remediation = _auth_cleanup_remediation(exc.path, empty_only=True)
        remediation["then"] = "run_auth_doctor"
        return _error_envelope(
            action,
            "auth_temp_home_cleanup_failed",
            "An empty temporary authentication HOME requires cleanup before "
            "authentication can continue.",
            remediation=remediation,
        )
    except OSError:
        return _ve_fallback_error(
            action, "auth_config_unwritable", profile=profile
        )

    return _error_envelope(
        action,
        "auth_config_unwritable",
        "Use a private temporary HOME for Volcengine CLI authentication and "
        "the remaining SMS task.",
        remediation=_login_remediation(
            profile,
            env={"HOME": temporary_home},
            continue_with_env=True,
            cleanup=_auth_cleanup_remediation(temporary_home),
        ),
    )


def _configure_environment_remediation(source: str) -> Dict[str, Any]:
    return {
        "action": "configure_environment",
        "source": source,
        "variables": [
            "VOLCENGINE_ACCESS_KEY",
            "VOLCENGINE_SECRET_KEY",
        ],
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
    if media_type not in TEMPLATE_DEMO_CSV_MEDIA_TYPES:
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
        self._cli_env = (
            prepare_cli_process_environment(self._env)
            if env is None
            else dict(self._env)
        )
        self._cli_auth_home_error = False
        if env is None:
            try:
                auth_home = select_cli_auth_home(self._env)
                self._cli_env["HOME"] = auth_home
                if os.name == "nt":
                    self._cli_env["USERPROFILE"] = auth_home
            except (OSError, _TemporaryAuthHomeValidationError):
                self._cli_auth_home_error = True
        self._env_path = DEFAULT_ENV_PATH if env is None else None
        self._clock = clock or (lambda: datetime.datetime.now(datetime.timezone.utc))
        self._transport = transport or _urllib_transport
        self._sleeper = sleeper or time.sleep
        self._cli_runner = cli_runner or _subprocess_cli_runner
        cli_home = str(self._cli_env.get("HOME") or "")
        try:
            cli_home = _validated_auth_home_for_cleanup(cli_home)
        except (OSError, _TemporaryAuthHomeValidationError):
            cli_home = ""
        self._credential_resolver = VolcengineCredentialResolver(
            self._env,
            credential_provider_factory=credential_provider_factory,
            cli_home=cli_home,
            refresh_cli_cache=self._refresh_cli_cache,
        )
        if prefer_ve_cli is None:
            self._prefer_ve_cli = cli_runner is not None or (
                transport is None and credential_provider_factory is None
            )
        else:
            self._prefer_ve_cli = prefer_ve_cli
        self._timeout = timeout
        self._idempotency_payloads: MutableMapping[Tuple[str, str], str] = {}

    def _refresh_cli_cache(self) -> None:
        cli_env = dict(self._cli_env)
        ve_path = shutil.which("ve", path=cli_env.get("PATH", ""))
        if ve_path is None:
            return
        command = [ve_path, "sts", "GetCallerIdentity"]
        profile = str(self._env.get("VOLCENGINE_PROFILE") or "").strip()
        if profile:
            command.extend(["---profile", profile])
        command.extend(
            [
                "---region",
                str(self._env.get("VOLCENGINE_REGION") or "cn-beijing"),
                "---lang",
                "EN",
            ]
        )
        try:
            self._cli_runner(command, cli_env, min(self._timeout, 30.0))
        except (OSError, subprocess.SubprocessError):
            return

    def auth_doctor(self) -> Dict[str, Any]:
        """Check CLI capabilities and validate credentials without exposing identity."""
        action = "auth-doctor"
        if self._cli_auth_home_error:
            return _error_envelope(
                action,
                "auth_temp_home_invalid",
                "No private system temporary directory is available for authentication.",
            )
        cli_env = dict(self._cli_env)
        cli_env.pop("ARK_SKILL_API_BASE", None)
        cli_env.pop("ARK_SKILL_API_KEY", None)
        probe_timeout = min(self._timeout, 5.0)
        install_remediation = _ve_install_remediation()
        ve_path = shutil.which("ve", path=cli_env.get("PATH", ""))
        if ve_path is None:
            return _ve_fallback_error(action, "ve_cli_missing")

        try:
            version_result = self._cli_runner(
                [ve_path, "--version"], cli_env, probe_timeout
            )
        except FileNotFoundError:
            return _ve_fallback_error(action, "ve_cli_missing")
        except PermissionError:
            return _error_envelope(
                action,
                "ve_cli_unexecutable",
                "The Volcengine CLI executable cannot be started.",
                remediation={"action": "inspect_ve_executable"},
            )
        except subprocess.TimeoutExpired:
            return _error_envelope(
                action,
                "ve_cli_timeout",
                "Volcengine CLI version inspection timed out.",
                retryable=True,
                remediation={"action": "retry"},
            )
        except OSError:
            return _ve_fallback_error(action, "ve_cli_unavailable")
        except Exception:
            return _error_envelope(
                action,
                "ve_cli_unavailable",
                "Unable to inspect the official Volcengine CLI.",
            )

        version_output = _completed_bytes(
            getattr(version_result, "stdout", b"")
        ) + b"\n" + _completed_bytes(getattr(version_result, "stderr", b""))
        parsed_version = _parse_ve_version(version_output)
        if int(getattr(version_result, "returncode", 1)) != 0 or parsed_version is None:
            return _error_envelope(
                action,
                "ve_cli_version_unknown",
                "Unable to determine the installed Volcengine CLI version.",
                remediation=install_remediation,
            )
        version_text, version_tuple = parsed_version
        if version_tuple < MIN_VE_CLI_VERSION:
            return _error_envelope(
                action,
                "ve_cli_too_old",
                "Volcengine CLI {} is older than the required {}.".format(
                    version_text, MIN_VE_CLI_VERSION_TEXT
                ),
                remediation=install_remediation,
            )

        capability_checks = (
            ([ve_path, "login", "--help"], b"--remote", "ve_login_unsupported"),
            (
                [ve_path, VE_CLI_SERVICE, "--help"],
                b"ListSubAccountForAgent",
                "ve_volcsms_unsupported",
            ),
            (
                [ve_path, "sts", "GetCallerIdentity", "--help"],
                b"GetCallerIdentity",
                "ve_sts_unsupported",
            ),
        )
        for command, marker, error_code in capability_checks:
            try:
                completed = self._cli_runner(command, cli_env, probe_timeout)
            except FileNotFoundError:
                return _ve_fallback_error(action, "ve_cli_missing")
            except PermissionError:
                return _error_envelope(
                    action,
                    "ve_cli_unexecutable",
                    "The Volcengine CLI executable cannot be started.",
                    remediation={"action": "inspect_ve_executable"},
                )
            except subprocess.TimeoutExpired:
                return _error_envelope(
                    action,
                    "ve_cli_timeout",
                    "Volcengine CLI capability inspection timed out.",
                    retryable=True,
                    remediation={"action": "retry"},
                )
            except OSError:
                return _ve_fallback_error(action, "ve_cli_unavailable")
            except Exception:
                return _error_envelope(
                    action,
                    error_code,
                    "Unable to inspect a required Volcengine CLI capability.",
                    remediation=install_remediation,
                )
            output = _completed_bytes(
                getattr(completed, "stdout", b"")
            ) + b"\n" + _completed_bytes(getattr(completed, "stderr", b""))
            if int(getattr(completed, "returncode", 1)) != 0 or marker not in output:
                return _error_envelope(
                    action,
                    error_code,
                    "The installed Volcengine CLI lacks a required capability.",
                    remediation=install_remediation,
                )

        try:
            profile = _validated_credential_value(
                self._env.get("VOLCENGINE_PROFILE")
            )
            auth_region = _validated_credential_value(
                self._env.get("VOLCENGINE_REGION")
            ) or "cn-beijing"
        except CredentialResolutionError as exc:
            return _error_envelope(action, "credential_error", str(exc))
        identity_command = [ve_path, "sts", "GetCallerIdentity"]
        if profile:
            identity_command.extend(["---profile", profile])
        identity_command.extend(["---region", auth_region, "---lang", "EN"])
        try:
            identity_result = self._cli_runner(
                identity_command, cli_env, self._timeout
            )
        except FileNotFoundError:
            return _ve_fallback_error(action, "ve_cli_missing")
        except PermissionError:
            return _error_envelope(
                action,
                "ve_cli_unexecutable",
                "The Volcengine CLI executable cannot be started.",
                remediation={"action": "inspect_ve_executable"},
            )
        except subprocess.TimeoutExpired:
            return _error_envelope(
                action,
                "network_error",
                "Volcengine credential validation timed out.",
                retryable=True,
                remediation={"action": "retry"},
            )
        except OSError:
            return _ve_fallback_error(action, "ve_cli_unavailable")
        except Exception:
            return _error_envelope(
                action,
                "cli_error",
                "Volcengine credential validation could not be completed.",
            )

        identity_stdout = _completed_bytes(getattr(identity_result, "stdout", b""))
        identity_stderr = _completed_bytes(getattr(identity_result, "stderr", b""))
        identity_payload = _extract_json_object(identity_stdout)
        if identity_payload is None:
            identity_payload = _extract_json_object(identity_stderr)
        if int(getattr(identity_result, "returncode", 1)) == 0:
            if identity_payload is None:
                return _error_envelope(
                    action,
                    "invalid_response",
                    "Volcengine CLI returned no valid identity response.",
                )
            return {
                "success": True,
                "action": action,
                "request_id": None,
                "result": {"status": "auth_ready", "veVersion": version_text},
                "error": None,
            }

        failure_output = identity_stderr + b"\n" + identity_stdout
        failure_code = _classify_ve_failure(failure_output)
        if failure_code == "auth_config_unwritable":
            return _temporary_auth_home_error(action, profile=profile)
        try:
            direct_credentials = _resolve_environment_credentials(self._env)
        except IncompleteCredentialsError as exc:
            return _error_envelope(
                action,
                "auth_credentials_incomplete",
                str(exc),
                remediation=_configure_environment_remediation(
                    "process_environment"
                ),
            )
        except CredentialResolutionError as exc:
            return _error_envelope(action, "credential_error", str(exc))

        if direct_credentials is None and self._env_path is not None:
            try:
                direct_credentials = _resolve_environment_credentials(
                    _read_env_file(self._env_path)
                )
            except IncompleteCredentialsError as exc:
                return _error_envelope(
                    action,
                    "auth_credentials_incomplete",
                    str(exc),
                    remediation=_configure_environment_remediation("env_file"),
                )
            except CredentialResolutionError as exc:
                return _error_envelope(action, "credential_error", str(exc))

        if direct_credentials is not None:
            validation = self.call_live_read_only("ListSubAccountForAgent", {})
            if validation.get("success"):
                return {
                    "success": True,
                    "action": action,
                    "request_id": validation.get("request_id"),
                    "result": {"status": "auth_ready", "veVersion": version_text},
                    "error": None,
                }
            error_value = validation.get("error")
            if isinstance(error_value, Mapping):
                return {
                    "success": False,
                    "action": action,
                    "request_id": validation.get("request_id"),
                    "result": None,
                    "error": sanitize_output(error_value),
                }
            return _error_envelope(
                action,
                "auth_check_failed",
                "Credential validation failed without a structured error.",
            )
        if failure_code is not None:
            return _ve_fallback_error(action, failure_code, profile=profile)
        return _error_envelope(
            action,
            "cli_error",
            "Volcengine CLI could not validate the current credentials.",
        )

    def _call_via_ve(
        self,
        action: str,
        spec: ActionSpec,
        params: Params,
        secrets: Sequence[str],
        *,
        preserve_presigned_url: bool,
    ) -> VeCallOutcome:
        """Use ``ve volcsms`` first and preserve safe fallback failures."""
        if not self._prefer_ve_cli:
            return VeCallOutcome(None)
        if not spec.cli_supported:
            profile = _validated_credential_value(
                self._env.get("VOLCENGINE_PROFILE")
            )
            return VeCallOutcome(
                None,
                _ve_fallback_error(action, "auth_required", profile=profile),
            )
        try:
            effective_env = dict(self._env)
            command = build_ve_cli_command(action, spec, params, effective_env)
        except CredentialResolutionError as exc:
            return VeCallOutcome(
                _error_envelope(
                    action,
                    "credential_error",
                    str(exc),
                    secrets=secrets,
                )
            )
        except (TypeError, ValueError) as exc:
            return VeCallOutcome(
                _error_envelope(
                    action,
                    "invalid_request",
                    str(exc),
                    secrets=secrets,
                )
            )

        profile = _validated_credential_value(
            effective_env.get("VOLCENGINE_PROFILE")
        )
        if self._cli_auth_home_error:
            return VeCallOutcome(
                _error_envelope(
                    action,
                    "auth_temp_home_invalid",
                    "No private system temporary directory is available for authentication.",
                    secrets=secrets,
                )
            )
        cli_env = dict(self._cli_env)
        cli_env.pop("ARK_SKILL_API_BASE", None)
        cli_env.pop("ARK_SKILL_API_KEY", None)
        cli_env.setdefault("VOLCENGINE_REGION", DEFAULT_REGION)
        try:
            completed = self._cli_runner(command, cli_env, self._timeout)
        except FileNotFoundError:
            return VeCallOutcome(_ve_fallback_error(action, "ve_cli_missing"))
        except PermissionError:
            return VeCallOutcome(
                None, _ve_fallback_error(action, "ve_cli_unavailable")
            )
        except subprocess.TimeoutExpired:
            if spec.read_only:
                return VeCallOutcome(
                    _error_envelope(
                        action,
                        "network_error",
                        "Volcengine CLI timed out",
                        retryable=True,
                        secrets=secrets,
                    )
                )
            return VeCallOutcome(
                _error_envelope(
                    action,
                    "outcome_unknown",
                    "The request may have been accepted but the Volcengine CLI "
                    "timed out",
                    outcome_unknown=True,
                    secrets=secrets,
                )
            )
        except OSError:
            if spec.read_only:
                return VeCallOutcome(
                    None, _ve_fallback_error(action, "ve_cli_unavailable")
                )
            return VeCallOutcome(
                _error_envelope(
                    action,
                    "outcome_unknown",
                    "The Volcengine CLI result is unknown",
                    outcome_unknown=True,
                    secrets=secrets,
                )
            )
        except Exception:
            if spec.read_only:
                return VeCallOutcome(
                    _error_envelope(
                        action,
                        "cli_error",
                        "Volcengine CLI execution failed before a valid response",
                        retryable=False,
                        secrets=secrets,
                    )
                )
            return VeCallOutcome(
                _error_envelope(
                    action,
                    "outcome_unknown",
                    "The Volcengine CLI result is unknown",
                    outcome_unknown=True,
                    secrets=secrets,
                )
            )

        stdout = _completed_bytes(getattr(completed, "stdout", b""))
        stderr = _completed_bytes(getattr(completed, "stderr", b""))
        payload = _extract_json_object(stdout)
        if payload is None:
            payload = _extract_json_object(stderr)
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
            return VeCallOutcome(
                self._normalize(
                    action,
                    spec,
                    response,
                    secrets,
                    preserve_presigned_url=(
                        preserve_presigned_url and action == "GetUploadTosURL"
                    ),
                )
            )

        return_code = int(getattr(completed, "returncode", 1))
        if return_code == 0:
            if action == "TemplateUploadDemo" and stdout:
                return VeCallOutcome(
                    _normalize_template_demo_csv(
                        action,
                        spec,
                        TransportResponse(
                            200,
                            {"Content-Type": "application/octet-stream"},
                            stdout,
                        ),
                        secrets,
                    )
                )
            if not spec.read_only:
                return VeCallOutcome(
                    _error_envelope(
                        action,
                        "outcome_unknown",
                        "The request may have been accepted but the Volcengine CLI "
                        "returned no valid response",
                        outcome_unknown=True,
                        secrets=secrets,
                    )
                )
            return VeCallOutcome(
                _error_envelope(
                    action,
                    "invalid_response",
                    "Volcengine CLI returned no valid JSON response",
                    secrets=secrets,
                )
            )

        if not spec.read_only:
            return VeCallOutcome(
                _error_envelope(
                    action,
                    "outcome_unknown",
                    "The request may have been accepted but the Volcengine CLI "
                    "returned no valid response",
                    outcome_unknown=True,
                    secrets=secrets,
                )
            )

        failure_output = stderr + b"\n" + stdout
        failure_code = _classify_ve_failure(failure_output)
        if failure_code is not None:
            if failure_code == "auth_config_unwritable":
                return VeCallOutcome(
                    None,
                    _error_envelope(
                        action,
                        failure_code,
                        "Run the authentication doctor to prepare a writable "
                        "Volcengine CLI session.",
                        secrets=secrets,
                        remediation={"action": "run_auth_doctor"},
                    ),
                )
            return VeCallOutcome(
                None,
                _ve_fallback_error(action, failure_code, profile=profile),
            )
        return VeCallOutcome(
            None,
            _error_envelope(
                action,
                "cli_error",
                "Volcengine CLI returned an unclassified error",
                secrets=secrets,
            ),
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
                self._env.get("VOLC_ACCESS_KEY"),
                self._env.get("VOLC_SECRET_KEY"),
                self._env.get("VOLC_SESSION_TOKEN"),
            )
            if isinstance(value, str) and value
        )

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

        cli_outcome = self._call_via_ve(
            action,
            spec,
            params,
            environment_secrets,
            preserve_presigned_url=preserve_presigned_url,
        )
        if cli_outcome.result is not None:
            return cli_outcome.result

        credential_source = "cli_profile"
        try:
            try:
                credentials = self._credential_resolver.resolve()
            except CredentialResolutionError:
                credential_source = "process_environment"
                credentials = _resolve_environment_credentials(self._env)
                if credentials is None and self._env_path is not None:
                    credential_source = "env_file"
                    credentials = _resolve_environment_credentials(
                        _read_env_file(self._env_path)
                    )
                if credentials is None:
                    if cli_outcome.fallback_error is not None:
                        return cli_outcome.fallback_error
                    raise CredentialResolutionError(
                        "No usable Volcengine credentials. Configure "
                        "VOLCENGINE_ACCESS_KEY and VOLCENGINE_SECRET_KEY in the "
                        "process environment or ~/.openclaw/.env."
                    )
        except IncompleteCredentialsError as exc:
            return _error_envelope(
                action,
                "auth_credentials_incomplete",
                str(exc),
                secrets=environment_secrets,
                remediation=_configure_environment_remediation(
                    credential_source
                ),
            )
        except CredentialResolutionError as exc:
            return _error_envelope(
                action,
                "credential_error",
                str(exc),
                secrets=environment_secrets,
            )
        resolved_secrets = (
            credentials.access_key,
            credentials.secret_key,
            credentials.session_token,
        )
        secrets = environment_secrets + tuple(
            value for value in resolved_secrets if value
        )

        try:
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
                return _invalid_success_response(
                    action,
                    spec,
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
            return _invalid_success_response(
                action,
                spec,
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
        contract_error = _result_contract_error(spec, result)
        if contract_error is not None:
            return _invalid_success_response(
                action,
                spec,
                contract_error,
                request_id=request_id,
                secrets=secrets,
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
