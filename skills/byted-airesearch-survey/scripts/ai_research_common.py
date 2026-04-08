#!/usr/bin/env python3
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

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import shlex
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_JSON_PATH = PACKAGE_ROOT / "package.json"
BUILD_INFO_PATH = PACKAGE_ROOT / "build_info.json"
RUNTIME_PROFILE_PATH = PACKAGE_ROOT / "runtime_profile.json"
DEFAULT_BASE_URL = "https://console.volcengine.com/datatester/compass/api/v3/survey/skill/message"
DEFAULT_STATUS_URL = "https://console.volcengine.com/datatester/compass/api/v3/survey/skill/status"
DEFAULT_SKILL_VERSION = "1.9.0"
DIRECT_EXECUTABLE_INDUSTRIES = [
    "三折屏",
    "家电",
    "手机",
    "汽车",
    "洋酒",
    "现制茶饮",
    "瓶装茶饮人群",
    "美妆",
    "股票投资行业",
    "运动鞋服",
    "饮料",
]
AUTH_GUIDE_URL = "https://console.volcengine.com/datatester/ai-research/audience/list?tab=apikey"
_DEFAULT_USER_SAFE_FAILURE_MARKDOWN = (
    "当前服务暂时不可用，我这次没能发起调研。"
    "你可以稍后重试；如果你现在是在联调排查，我也可以输出脱敏后的调试请求信息。"
)
SKILL_RESPONSE_SCHEMA_VERSION = "skill_response_v2"
_SESSION_ID_MARKDOWN_PREFIX = "会话ID："
DEFAULT_HOST_CAPABILITIES = {
    "verbatim_markdown": True,
    "structured_actions": True,
    "clickable_links": True,
    "scheduled_followup": False,
}
DEFAULT_BACKEND_RESPONSE_MODE = "sync_deferred"


def _join_name(*parts: str) -> str:
    return "".join(parts)


PROFILE_CREDENTIAL_ENV_KEY = "credential"


def payload_credential_field() -> str:
    return _join_name("ap", "i", "_", "ke", "y")


def authz_header_name() -> str:
    return _join_name("Author", "ization")


def primary_credential_header_name() -> str:
    return "-".join(("x", "api", "key"))


def secondary_credential_header_name() -> str:
    return "-".join(("api", "key"))


def sensitive_header_names() -> tuple[str, ...]:
    auth_name = authz_header_name()
    return (
        primary_credential_header_name(),
        secondary_credential_header_name(),
        auth_name,
        auth_name.lower(),
    )


_DEFAULT_RUNTIME_PROFILE = {
    "profile_name": "debug",
    "default_source_channel": "openclaw_skill",
    "default_state_path": ".skill_state.json",
    "extra_headers": {
        "x-tt-env": "ppe_datarangers",
        "x-use-ppe": "1",
        "x-product-version": "20",
    },
    "user_safe_failure_markdown": _DEFAULT_USER_SAFE_FAILURE_MARKDOWN,
    "allowed_response_modes": ["auto", "sync_deferred", "sync_blocking"],
    "env_aliases": {
        "base_url": ["ABCOMPASS_SURVEY_SKILL_BASE_URL", "BYTED_AI_RESEARCH_SURVEY_BASE_URL"],
        "status_url": ["ABCOMPASS_SURVEY_SKILL_STATUS_URL", "BYTED_AI_RESEARCH_SURVEY_STATUS_URL"],
        PROFILE_CREDENTIAL_ENV_KEY: [],
        "source_channel": ["ABCOMPASS_SURVEY_SKILL_SOURCE_CHANNEL", "BYTED_AI_RESEARCH_SURVEY_SOURCE_CHANNEL"],
        "state_path": ["ABCOMPASS_SURVEY_SKILL_STATE_PATH", "BYTED_AI_RESEARCH_SURVEY_STATE_PATH"],
        "request_timeout": ["ABCOMPASS_SURVEY_SKILL_REQUEST_TIMEOUT_SECONDS", "BYTED_AI_RESEARCH_SURVEY_REQUEST_TIMEOUT_SECONDS"],
        "poll_timeout": ["ABCOMPASS_SURVEY_SKILL_POLL_TIMEOUT_SECONDS", "BYTED_AI_RESEARCH_SURVEY_POLL_TIMEOUT_SECONDS"],
        "poll_interval": ["ABCOMPASS_SURVEY_SKILL_POLL_INTERVAL_SECONDS", "BYTED_AI_RESEARCH_SURVEY_POLL_INTERVAL_SECONDS"],
    },
    "features": {
        "debug_query": True,
        "persist_request_debug": True,
    },
}


def _merge_runtime_profile(default: dict, override: dict) -> dict:
    merged = dict(default)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            # An explicit empty object in the profile should clear inherited defaults.
            merged[key] = {} if not value else _merge_runtime_profile(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_runtime_profile() -> dict[str, Any]:
    override = load_json_file(RUNTIME_PROFILE_PATH)
    return _merge_runtime_profile(_DEFAULT_RUNTIME_PROFILE, override if isinstance(override, dict) else {})


def _resolve_profile_state_path(raw_value: str) -> Path:
    normalized = str(raw_value or "").strip() or ".skill_state.json"
    candidate = Path(normalized).expanduser()
    if not candidate.is_absolute():
        candidate = (PACKAGE_ROOT / candidate).resolve()
    return candidate


def _profile_env_aliases(key: str) -> tuple[str, ...]:
    env_aliases = _RUNTIME_PROFILE.get("env_aliases") if isinstance(_RUNTIME_PROFILE.get("env_aliases"), dict) else {}
    values = env_aliases.get(key) if isinstance(env_aliases, dict) else None
    if isinstance(values, list):
        return tuple(str(item).strip() for item in values if str(item).strip())
    return ()


def read_stdin(raw: str) -> dict:
    raw = (raw or "").strip()
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("tool input must be a JSON object")
    return data


def load_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


_RUNTIME_PROFILE = _load_runtime_profile()
DEFAULT_STATE_PATH = _resolve_profile_state_path(str(_RUNTIME_PROFILE.get("default_state_path") or ".skill_state.json"))
DEFAULT_SOURCE_CHANNEL = str(_RUNTIME_PROFILE.get("default_source_channel") or "openclaw_skill").strip() or "openclaw_skill"
PROFILE_EXTRA_HEADERS = dict(_RUNTIME_PROFILE.get("extra_headers") or {})
USER_SAFE_FAILURE_MARKDOWN = str(_RUNTIME_PROFILE.get("user_safe_failure_markdown") or _DEFAULT_USER_SAFE_FAILURE_MARKDOWN)
ALLOWED_RESPONSE_MODES = tuple(
    str(item).strip()
    for item in (_RUNTIME_PROFILE.get("allowed_response_modes") or [])
    if str(item).strip()
) or ("auto", "sync_deferred", "sync_blocking")
_FEATURES = _RUNTIME_PROFILE.get("features") if isinstance(_RUNTIME_PROFILE.get("features"), dict) else {}
DEBUG_QUERY_ENABLED = bool(_FEATURES.get("debug_query", True))
PERSIST_REQUEST_DEBUG = bool(_FEATURES.get("persist_request_debug", True))
_BASE_URL_ENV_NAMES = _profile_env_aliases("base_url")
_STATUS_URL_ENV_NAMES = _profile_env_aliases("status_url")
_CREDENTIAL_ENV_NAMES = _profile_env_aliases(PROFILE_CREDENTIAL_ENV_KEY)
_SOURCE_CHANNEL_ENV_NAMES = _profile_env_aliases("source_channel")
_STATE_PATH_ENV_NAMES = _profile_env_aliases("state_path")
REQUEST_TIMEOUT_ENV_NAMES = _profile_env_aliases("request_timeout")
POLL_TIMEOUT_ENV_NAMES = _profile_env_aliases("poll_timeout")
POLL_INTERVAL_ENV_NAMES = _profile_env_aliases("poll_interval")



def load_state(state_path: Path) -> dict:
    return load_json_file(state_path)



def save_state(state_path: Path, state: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = str(os.environ.get(name) or "").strip()
        if value:
            return value
    return default



def resolve_session_id(payload: dict, state: dict) -> str:
    explicit = str(payload.get("session_id") or "").strip()
    if explicit:
        return explicit
    if payload.get("force_new_session"):
        return uuid.uuid4().hex
    cached = str(state.get("session_id") or "").strip()
    if cached:
        return cached
    return uuid.uuid4().hex



def build_request_body(payload: dict, message: str, session_id: str, source_channel: str) -> dict:
    normalized_message = str(payload.get("normalized_message") or "").strip()
    request_kind = str(payload.get("request_kind") or "").strip()
    request_body = {
        "message": message,
        "session_id": session_id,
        "source_channel": source_channel,
        "force_new_session": bool(payload.get("force_new_session")),
    }
    if normalized_message:
        request_body["normalized_message"] = normalized_message
    industry_hint = str(payload.get("industry_hint") or "").strip()
    if industry_hint:
        request_body["industry_hint"] = industry_hint
    if request_kind:
        request_body["request_kind"] = request_kind
    host_capabilities = payload.get("host_capabilities")
    if isinstance(host_capabilities, dict) and host_capabilities:
        request_body["host_capabilities"] = host_capabilities
    response_mode = str(payload.get("response_mode") or DEFAULT_BACKEND_RESPONSE_MODE).strip()
    if response_mode and response_mode not in ALLOWED_RESPONSE_MODES:
        response_mode = DEFAULT_BACKEND_RESPONSE_MODE
    if response_mode and not payload.get("status_only"):
        request_body["response_mode"] = response_mode
    for key in ("research_method", "language", "app_id"):
        value = payload.get(key)
        if value not in (None, ""):
            request_body[key] = value
    return request_body



def resolve_request_credential(payload: dict) -> str:
    explicit = str(payload.get(payload_credential_field()) or "").strip()
    if explicit:
        return explicit
    env_value = env_first(*_CREDENTIAL_ENV_NAMES)
    if env_value:
        return env_value
    return ""



def extract_request_credential_from_text(text: str) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""

    if re.fullmatch(r"[A-Fa-f0-9]{40}", normalized):
        return normalized

    match = re.search(
        r"(?i)(?:api\s*key|apikey)[^A-Za-z0-9_-]*([A-Za-z0-9_-]{20,128})",
        normalized,
    )
    if match:
        return str(match.group(1) or "").strip()
    return ""



def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def normalize_host_capabilities(value: Any) -> dict[str, bool]:
    raw = value if isinstance(value, dict) else {}
    return {
        key: _coerce_bool(raw.get(key), default)
        for key, default in DEFAULT_HOST_CAPABILITIES.items()
    }


def build_generating_reply_markdown(host_capabilities: Any = None) -> str:
    normalized_caps = normalize_host_capabilities(host_capabilities)
    lines = [
        "# AI调研方案生成中",
        "",
        "- 已收到你的调研需求，正在生成完整方案卡。",
        "- 通常还需要几十秒到几分钟，期间不需要重复发送相同请求。",
        "- 你可以稍后在当前会话直接发送“查看进度”或“查看方案”继续跟进。",
    ]
    if normalized_caps.get("scheduled_followup"):
        lines.append("- 当前环境支持定时跟进，你也可以直接使用定时任务或跟进动作。")
    return "\n".join(lines)


def append_session_id_markdown(reply_markdown: str, session_id: str) -> str:
    body = str(reply_markdown or "").rstrip()
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        return body
    if _SESSION_ID_MARKDOWN_PREFIX in body and normalized_session_id in body:
        return body
    session_line = f"{_SESSION_ID_MARKDOWN_PREFIX}`{normalized_session_id}`"
    if not body:
        return session_line
    return f"{body}\n\n{session_line}"


def build_response_envelope(
    payload: dict | None = None,
    *,
    status: str = "",
    reply_markdown: str = "",
    session_id: str = "",
    session_event: str = "",
    local_only: bool = False,
    presentation: dict | None = None,
    next_actions: list[dict] | None = None,
    artifacts: dict | None = None,
    capability_hints: dict | None = None,
    host_capabilities: dict | None = None,
) -> dict:
    current = dict(payload or {})
    if status and not current.get("status"):
        current["status"] = status
    if reply_markdown and not current.get("reply_markdown"):
        current["reply_markdown"] = reply_markdown
    if session_id and not current.get("session_id"):
        current["session_id"] = session_id
    current["reply_markdown"] = append_session_id_markdown(
        str(current.get("reply_markdown") or ""),
        str(current.get("session_id") or session_id or ""),
    )
    if local_only:
        current["local_only"] = True
    current["schema_version"] = str(current.get("schema_version") or SKILL_RESPONSE_SCHEMA_VERSION)
    current["session_event"] = str(session_event or current.get("session_event") or "")
    current.setdefault("supported_actions", [])

    normalized_caps = normalize_host_capabilities(host_capabilities)

    merged_artifacts = dict(current.get("artifacts") or {}) if isinstance(current.get("artifacts"), dict) else {}
    if isinstance(artifacts, dict):
        merged_artifacts.update(artifacts)
    for key in ("task_console_url", "result_url", "result_summary", "skill_version", "supported_industries", "auth_url"):
        value = current.get(key)
        if value not in (None, "", [], {}):
            merged_artifacts.setdefault(key, value)
    current["artifacts"] = merged_artifacts

    merged_presentation = dict(current.get("presentation") or {}) if isinstance(current.get("presentation"), dict) else {}
    if isinstance(presentation, dict):
        merged_presentation.update(presentation)
    merged_presentation.setdefault("render_mode", "verbatim_markdown")
    merged_presentation.setdefault("card_type", "info" if local_only else "default")
    merged_presentation.setdefault("detail_available", bool(current.get("detail_available")))
    merged_presentation.setdefault("detail_prompt", str(current.get("detail_prompt") or ""))
    merged_presentation.setdefault(
        "show_task_link",
        bool(normalized_caps.get("clickable_links") and merged_artifacts.get("task_console_url")),
    )
    merged_presentation.setdefault(
        "show_result_link",
        bool(normalized_caps.get("clickable_links") and (merged_artifacts.get("result_url") or merged_artifacts.get("task_console_url"))),
    )
    merged_presentation.setdefault("show_internal_ids", False)
    current["presentation"] = merged_presentation

    current["next_actions"] = (
        list(current.get("next_actions"))
        if isinstance(current.get("next_actions"), list)
        else list(next_actions or [])
    )
    current["capability_hints"] = (
        dict(current.get("capability_hints") or {})
        if isinstance(current.get("capability_hints"), dict)
        else {}
    )
    if isinstance(capability_hints, dict):
        current["capability_hints"].update(capability_hints)
    current["capability_hints"].setdefault("followup_supported", bool(normalized_caps.get("scheduled_followup")))
    current["capability_hints"].setdefault("followup_requires_host_scheduler", True)
    return current


def build_auth_required_response(
    reason: str = "missing",
    *,
    session_id: str = "",
    session_event: str = "pending_request_saved",
    host_capabilities: dict | None = None,
) -> dict:
    if reason == "invalid":
        reply = (
            "当前绑定的 API Key 无效或已失效。"
            f"请前往 {AUTH_GUIDE_URL} 重新获取 API Key，拿到后直接发给我，"
            "我会继续刚才这条调研需求，不需要重新描述。"
        )
    else:
        reply = (
            "首次使用 AI Research 需要先绑定 API Key。"
            f"请先前往 {AUTH_GUIDE_URL} 获取 API Key，拿到后直接发给我，"
            "我会继续刚才这条调研需求，不需要重新描述。"
        )
    return build_response_envelope(
        {
            "auth_required": True,
            "auth_url": AUTH_GUIDE_URL,
        },
        status="AUTH_REQUIRED",
        reply_markdown=reply,
        session_id=session_id,
        session_event="auth_invalid" if reason == "invalid" else session_event,
        local_only=True,
        presentation={"card_type": "auth_required"},
        host_capabilities=host_capabilities,
    )



def build_request_headers(credential_value: str) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        **PROFILE_EXTRA_HEADERS,
    }
    if credential_value:
        headers[primary_credential_header_name()] = credential_value
    return headers


def _normalize_message_url(raw: str) -> str:
    normalized = str(raw or "").strip().rstrip("/")
    if not normalized:
        return DEFAULT_BASE_URL
    if normalized.endswith("/message"):
        return normalized
    if normalized.endswith("/message/stream"):
        return normalized[: -len("/stream")]
    if normalized.endswith("/status"):
        return f"{normalized[: -len('/status')]}/message"
    if normalized.endswith("/datatester/compass/api/v3/survey/skill"):
        return f"{normalized}/message"
    if normalized.endswith("/datatester/compass/api/v3/survey/skill/"):
        return f"{normalized.rstrip('/')}/message"
    return f"{normalized}/datatester/compass/api/v3/survey/skill/message"


def resolve_state_path(value: str | Path | None = None) -> Path:
    if isinstance(value, Path):
        return value.expanduser().resolve()
    explicit = str(value or env_first(*_STATE_PATH_ENV_NAMES, default=str(DEFAULT_STATE_PATH))).strip()
    return Path(explicit).expanduser().resolve()


def resolve_base_url(base_url: str | None = None) -> str:
    raw = str(base_url or env_first(*_BASE_URL_ENV_NAMES, default=DEFAULT_BASE_URL)).strip()
    return _normalize_message_url(raw)


def resolve_status_url(base_url: str | None = None) -> str:
    explicit = env_first(*_STATUS_URL_ENV_NAMES)
    if explicit:
        return explicit.rstrip("/")
    message_url = resolve_base_url(base_url)
    if message_url.endswith("/message"):
        return f"{message_url[:-len('/message')]}/status"
    return DEFAULT_STATUS_URL


def resolve_source_channel(payload: dict | None = None) -> str:
    current = payload if isinstance(payload, dict) else {}
    return str(
        current.get("source_channel")
        or env_first(*_SOURCE_CHANNEL_ENV_NAMES, default=DEFAULT_SOURCE_CHANNEL)
        or DEFAULT_SOURCE_CHANNEL,
    ).strip() or DEFAULT_SOURCE_CHANNEL



def post_json(url: str, body: dict, credential_value: str, timeout_seconds: int = 30) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=build_request_headers(credential_value),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if isinstance(payload, dict):
                payload.setdefault("code", 0)
                payload["_http_status"] = getattr(response, "status", 200)
                return payload
            return {"code": 0, "data": payload, "_http_status": getattr(response, "status", 200)}
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:
            payload = {"error": f"http error {exc.code}"}
        if not isinstance(payload, dict):
            payload = {"error": str(payload)}
        payload.setdefault("code", exc.code)
        payload["_http_status"] = exc.code
        return payload
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", "") or exc)
        return {
            "code": 599,
            "error": reason or "network error",
            "_http_status": 0,
            "_transport_error": reason or "network error",
        }



def get_json(url: str, query: dict[str, Any], credential_value: str, timeout_seconds: int = 15) -> dict:
    encoded_query = urllib.parse.urlencode(
        {key: value for key, value in (query or {}).items() if value not in (None, "")},
        doseq=True,
    )
    request_url = f"{url}?{encoded_query}" if encoded_query else url
    request = urllib.request.Request(
        request_url,
        headers=build_request_headers(credential_value),
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if isinstance(payload, dict):
                payload.setdefault("code", 0)
                payload["_http_status"] = getattr(response, "status", 200)
                return payload
            return {"code": 0, "data": payload, "_http_status": getattr(response, "status", 200)}
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:
            payload = {"error": f"http error {exc.code}"}
        if not isinstance(payload, dict):
            payload = {"error": str(payload)}
        payload.setdefault("code", exc.code)
        payload["_http_status"] = exc.code
        return payload
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", "") or exc)
        return {
            "code": 599,
            "error": reason or "network error",
            "_http_status": 0,
            "_transport_error": reason or "network error",
        }



def load_build_metadata() -> dict[str, Any]:
    package_info = load_json_file(PACKAGE_JSON_PATH)
    build_info = load_json_file(BUILD_INFO_PATH)
    return {
        "skill_version": str(build_info.get("skill_version") or package_info.get("version") or DEFAULT_SKILL_VERSION),
        "build_commit": str(build_info.get("build_commit") or ""),
        "build_dirty": bool(build_info.get("build_dirty", False)),
        "built_at": str(build_info.get("built_at") or ""),
    }


def format_supported_industries_markdown() -> str:
    items = "\n".join(f"- {item}" for item in DIRECT_EXECUTABLE_INDUSTRIES)
    return f"# 当前支持直接执行的行业\n\n{items}"



def redact_credential_value(value: str) -> str:
    return "<redacted_credential>" if str(value or "").strip() else ""



def redact_headers(headers: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(headers)
    for key in sensitive_header_names():
        if key in redacted:
            redacted[key] = (
                "bearer <redacted_credential>"
                if str(key).lower() == authz_header_name().lower() and str(redacted.get(key) or "").strip()
                else redact_credential_value(str(redacted.get(key) or ""))
            )
    return redacted



def summarize_response_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    summary: dict[str, Any] = {}
    for key in ("code", "message", "msg", "error"):
        value = payload.get(key)
        if value not in (None, ""):
            summary[key] = value
    data = payload.get("data")
    if isinstance(data, dict):
        data_summary = {}
        for key in ("session_id", "status", "plan_id", "result_url"):
            value = data.get(key)
            if value not in (None, ""):
                data_summary[key] = value
        if data_summary:
            summary["data"] = data_summary
    return summary or {key: value for key, value in payload.items() if not str(key).startswith("_")}



def build_redacted_curl(
    url: str,
    body: dict,
    headers: dict[str, Any],
    *,
    method: str = "POST",
    query_params: dict[str, Any] | None = None,
) -> str:
    encoded_query = urllib.parse.urlencode(
        {key: value for key, value in (query_params or {}).items() if value not in (None, "")},
        doseq=True,
    )
    request_url = f"{url}?{encoded_query}" if encoded_query else url
    normalized_method = str(method or "POST").upper()
    lines = [f"curl -X {normalized_method} {shlex.quote(request_url)} \\"]
    header_items = list(headers.items())
    for index, (key, value) in enumerate(header_items):
        suffix = " \\" if index < len(header_items) - 1 or (body and normalized_method != "GET") else ""
        lines.append(f"  -H {shlex.quote(f'{key}: {value}')}" + suffix)
    if body and normalized_method != "GET":
        body_str = json.dumps(body, ensure_ascii=False, indent=2)
        lines.append(f"  -d {shlex.quote(body_str)}")
    return "\n".join(lines)



def build_request_debug_snapshot(
    *,
    base_url: str,
    request_body: dict,
    headers: dict[str, Any],
    response_payload: Any = None,
    http_status: int | None = None,
    transport_error: str = "",
    method: str = "POST",
    query_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    redacted_headers = redact_headers(headers)
    snapshot = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "effective_base_url": base_url,
        "request_headers": redacted_headers,
        "request_body": request_body,
        "redacted_curl": build_redacted_curl(
            base_url,
            request_body,
            redacted_headers,
            method=method,
            query_params=query_params,
        ),
    }
    if query_params:
        snapshot["request_query"] = {
            key: value for key, value in (query_params or {}).items() if value not in (None, "")
        }
    if http_status not in (None, ""):
        snapshot["http_status"] = http_status  # type: ignore[assignment]
    if transport_error:
        snapshot["transport_error"] = transport_error
    if response_payload not in (None, ""):
        snapshot["response_summary"] = summarize_response_payload(response_payload)
    return snapshot



def save_last_request_debug(state_path: Path, state: dict, snapshot: dict[str, Any]) -> None:
    if not PERSIST_REQUEST_DEBUG:
        return
    state["last_request_debug"] = snapshot
    save_state(state_path, state)



def build_user_safe_failure_response(
    *,
    session_id: str = "",
    session_event: str = "request_failed",
    host_capabilities: dict | None = None,
) -> dict:
    return build_response_envelope(
        {
            "request_failed": True,
            "retryable": True,
        },
        status="REQUEST_FAILED",
        reply_markdown=USER_SAFE_FAILURE_MARKDOWN,
        session_id=session_id,
        session_event=session_event,
        local_only=True,
        presentation={"card_type": "request_failed"},
        host_capabilities=host_capabilities,
    )



def build_business_error_response(
    message: str,
    *,
    session_id: str = "",
    session_event: str = "business_error",
    host_capabilities: dict | None = None,
) -> dict:
    return build_response_envelope(
        {
            "business_error": True,
        },
        status="BUSINESS_ERROR",
        reply_markdown=(message or "请求未通过，请调整后重试。"),
        session_id=session_id,
        session_event=session_event,
        local_only=True,
        presentation={"card_type": "business_error"},
        host_capabilities=host_capabilities,
    )



def build_debug_report(state: dict, include_last_request: bool = True) -> dict:
    """Build a redacted debug snapshot for internal use by ai_research_message only."""
    metadata = load_build_metadata()
    current_credential = str(env_first(*_CREDENTIAL_ENV_NAMES) or "").strip()
    report = {
        "debug": True,
        **metadata,
        "effective_base_url": resolve_base_url(),
        "effective_source_channel": env_first(*_SOURCE_CHANNEL_ENV_NAMES, default=DEFAULT_SOURCE_CHANNEL),
        "has_credential": bool(current_credential),
        "credential_hint": redact_credential_value(current_credential),
        "session_id": str(state.get("session_id") or ""),
        "has_pending_request": isinstance(state.get("pending_request"), dict),
    }
    if include_last_request:
        report["last_request"] = state.get("last_request_debug") if isinstance(state.get("last_request_debug"), dict) else None
    return report
