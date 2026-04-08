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
from pathlib import Path
import re
import sys
import time

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from ai_research_common import (  # noqa: E402
    DEBUG_QUERY_ENABLED,
    DIRECT_EXECUTABLE_INDUSTRIES,
    DEFAULT_STATE_PATH,
    POLL_INTERVAL_ENV_NAMES,
    POLL_TIMEOUT_ENV_NAMES,
    REQUEST_TIMEOUT_ENV_NAMES,
    build_auth_required_response,
    build_business_error_response,
    build_debug_report,
    build_generating_reply_markdown,
    build_response_envelope,
    build_request_body,
    build_request_debug_snapshot,
    build_request_headers,
    build_user_safe_failure_response,
    extract_request_credential_from_text,
    format_supported_industries_markdown,
    get_json,
    load_build_metadata,
    load_state,
    payload_credential_field,
    post_json,
    read_stdin,
    env_first,
    resolve_request_credential,
    resolve_base_url,
    resolve_session_id,
    resolve_source_channel,
    resolve_state_path,
    resolve_status_url,
    save_last_request_debug,
    save_state,
    normalize_host_capabilities,
)


STATE_PATH = DEFAULT_STATE_PATH
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120
DEFAULT_STATUS_POLL_TIMEOUT_SECONDS = 60
DEFAULT_STATUS_POLL_INTERVAL_SECONDS = 2.0
_POLLABLE_FAILURE_CODES = {502, 503, 504, 599}
_POLLABLE_STATUSES = {"GENERATING"}
_READY_STATUSES = {
    "WAITING_CONFIRM",
    "UNSUPPORTED_INDUSTRY",
    "CONFIRMED",
    "AUDIENCE_RUNNING",
    "TASK_RUNNING",
    "FINISHED",
    "FAILED",
}
_VERSION_QUERY_PATTERNS = (
    r"哪个版本",
    r"什么版本",
    r"当前版本",
    r"skill版本",
    r"技能版本",
    r"\bskill\s+version\b",
)
_REQUEST_DEBUG_PATTERNS = (
    r"\bcurl\b",
    r"请求头",
    r"调试信息",
    r"debug",
    r"最近请求",
)
_SUPPORTED_INDUSTRY_PATTERNS = (
    r"支持.*行业",
    r"有哪些行业",
    r"行业列表",
)
# NOTE: These keyword lists provide a client-side hint to the backend's
# request_kind parameter. The backend (skill_service.py) is the authority.
# Keep these lists in sync with skill_service.py or make them a strict
# subset. False positives are acceptable; false negatives cause extra
# backend re-inference but no correctness issues.
_RESULT_QUERY_KINDS = {"query_status", "query_result", "query_plan"}
_SHORT_FOLLOWUP_MAX_LENGTH = 64
_CONFIRM_EXECUTE_EXACT_MESSAGES = {
    "yes",
    "confirm",
    "start",
    "execute",
    "run",
    "是",
    "确认",
    "开始",
    "执行",
    "启动",
    "开跑",
}
_CONFIRM_EXECUTE_PHRASES = (
    "确认方案",
    "确认执行",
    "确认并执行",
    "开始执行",
    "开始投放",
    "直接投放",
    "按这个执行",
    "就按这个执行",
    "开始调研",
)
_QUERY_VERB_KEYWORDS = (
    "查看",
    "查询",
    "查下",
    "看看",
    "看下",
    "看一下",
    "当前",
    "现在",
    "最新",
)
_STATUS_TOPIC_KEYWORDS = ("状态", "进度", "进展")
_STATUS_QUESTION_KEYWORDS = ("如何", "怎么样", "到哪", "哪一步")
_RESULT_TOPIC_KEYWORDS = ("结果", "报告")
_PLAN_TOPIC_KEYWORDS = ("方案", "计划")
_DETAIL_SIGNAL_KEYWORDS = ("完整", "详细", "详情", "全部")
_DETAIL_TARGET_KEYWORDS = ("方案", "计划", "问卷", "题单", "题目", "题", "选项", "信息", "概览")
_DETAIL_GRANULAR_TARGET_KEYWORDS = ("问卷", "题单", "题目", "题", "选项")
_DETAIL_ACTION_KEYWORDS = ("给我看", "看一下", "看下", "具体")
_FAILURE_REASON_KEYWORDS = ("原因", "详情", "为什么", "为何", "为啥", "卡在哪")
_RESTART_SIGNAL_KEYWORDS = ("重发", "重来", "重新")
_RESTART_TARGET_KEYWORDS = ("发起", "生成", "调研", "来一轮", "来一次", "做一轮", "做一次")


def _load_state() -> dict:
    return load_state(STATE_PATH)



def _save_state(state: dict) -> None:
    save_state(STATE_PATH, state)


def _load_state_at(state_path: Path) -> dict:
    return load_state(state_path)


def _save_state_at(state_path: Path, state: dict) -> None:
    save_state(state_path, state)


def _resolve_runtime_state_path(payload: dict, state_path_override: Path | None = None) -> Path:
    if state_path_override is not None:
        return Path(state_path_override).expanduser().resolve()
    if payload.get("state_path") not in (None, ""):
        return resolve_state_path(payload.get("state_path"))
    resolved = resolve_state_path()
    if resolved != DEFAULT_STATE_PATH:
        return resolved
    return STATE_PATH



def _resolve_session_id(payload: dict, state: dict) -> str:
    return resolve_session_id(payload, state)



def _build_request_body(payload: dict, message: str, session_id: str, source_channel: str) -> dict:
    return build_request_body(payload, message, session_id, source_channel)



def _resolve_credential(payload: dict) -> str:
    return resolve_request_credential(payload)



def _build_auth_required_response(reason: str = "missing", **kwargs) -> dict:
    return build_auth_required_response(reason, **kwargs)



def _build_request_headers(credential_value: str) -> dict[str, str]:
    return build_request_headers(credential_value)



def _post_json(url: str, body: dict, credential_value: str, timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS) -> dict:
    return post_json(url, body, credential_value, timeout_seconds=timeout_seconds)



def _get_json(url: str, query: dict, credential_value: str, timeout_seconds: int = 15) -> dict:
    return get_json(url, query, credential_value, timeout_seconds=timeout_seconds)



def _resolve_request_timeout_seconds(payload: dict | None = None) -> int:
    raw = str((payload or {}).get("timeout_seconds") or env_first(*REQUEST_TIMEOUT_ENV_NAMES) or "").strip()
    try:
        value = int(raw)
    except Exception:
        value = DEFAULT_REQUEST_TIMEOUT_SECONDS
    return max(5, value)



def _resolve_status_poll_timeout_seconds(payload: dict | None = None) -> int:
    raw = str((payload or {}).get("poll_timeout_seconds") or env_first(*POLL_TIMEOUT_ENV_NAMES) or "").strip()
    try:
        value = int(raw)
    except Exception:
        value = DEFAULT_STATUS_POLL_TIMEOUT_SECONDS
    return max(0, value)



def _resolve_status_poll_interval_seconds(payload: dict | None = None) -> float:
    raw = str((payload or {}).get("poll_interval_seconds") or env_first(*POLL_INTERVAL_ENV_NAMES) or "").strip()
    try:
        value = float(raw)
    except Exception:
        value = DEFAULT_STATUS_POLL_INTERVAL_SECONDS
    return max(0.5, value)



def _extract_data(payload: dict) -> dict:
    data = payload.get("data") or {}
    return data if isinstance(data, dict) else {}


def _ensure_generating_reply_markdown(
    data: dict,
    session_id: str,
    host_capabilities: dict | None = None,
) -> dict:
    current = dict(data or {})
    current.setdefault("session_id", session_id)
    current["status"] = _extract_status(current) or "GENERATING"
    reply = build_generating_reply_markdown(host_capabilities)
    created_at = str(current.get("created_at") or "").strip()
    if created_at:
        try:
            from datetime import datetime as _dt
            created = _dt.fromisoformat(created_at.replace("Z", "+00:00"))
            now = _dt.now(created.tzinfo) if created.tzinfo else _dt.now()
            elapsed_minutes = int((now - created).total_seconds() / 60)
            if elapsed_minutes >= 1:
                reply += f"\n- 当前已等待约 {elapsed_minutes} 分钟。"
        except Exception:
            pass
    current["reply_markdown"] = reply
    return current


def _extract_status(data: dict) -> str:
    return str((data or {}).get("status") or "").strip().upper()


def _normalize_message(message: str) -> str:
    return re.sub(r"\s+", " ", str(message or "").strip())


def _compact_message_text(message: str) -> str:
    normalized = _normalize_message(message).lower()
    return re.sub(r"[\s\.,!?，。！？:：;；'\"`~\\-_/\\\\()\\[\\]{}]+", "", normalized)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _is_short_followup_message(message: str) -> bool:
    return len(_normalize_message(message)) <= _SHORT_FOLLOWUP_MAX_LENGTH


def _is_confirm_execute_message(message: str) -> bool:
    compact = _compact_message_text(message)
    if compact in {_compact_message_text(item) for item in _CONFIRM_EXECUTE_EXACT_MESSAGES}:
        return True
    lowered = _normalize_message(message).lower()
    return _contains_any(lowered, _CONFIRM_EXECUTE_PHRASES)


def _is_status_query_message(message: str) -> bool:
    lowered = _normalize_message(message).lower()
    if re.search(r"\b(status|progress)\b", lowered):
        return True
    if _contains_any(lowered, _STATUS_TOPIC_KEYWORDS) and _contains_any(lowered, _QUERY_VERB_KEYWORDS + _STATUS_QUESTION_KEYWORDS):
        return True
    return "到哪一步" in lowered


def _is_result_query_message(message: str) -> bool:
    lowered = _normalize_message(message).lower()
    if re.search(r"\b(result|report)\b", lowered):
        return True
    if _contains_any(lowered, _RESULT_TOPIC_KEYWORDS) and _contains_any(lowered, _QUERY_VERB_KEYWORDS + ("有", "出来", "呢")):
        return True
    return "调研结果" in lowered


def _is_plan_query_message(message: str) -> bool:
    lowered = _normalize_message(message).lower()
    if "show plan" in lowered or "showplan" in lowered:
        return True
    if _contains_any(lowered, _PLAN_TOPIC_KEYWORDS) and _contains_any(lowered, _QUERY_VERB_KEYWORDS + ("呢",)):
        return True
    return False


def _is_detail_query_message(message: str) -> bool:
    lowered = _normalize_message(message).lower()
    if _contains_any(lowered, _DETAIL_SIGNAL_KEYWORDS) and _contains_any(lowered, _DETAIL_TARGET_KEYWORDS):
        return True
    return _contains_any(lowered, _DETAIL_GRANULAR_TARGET_KEYWORDS) and _contains_any(lowered, _DETAIL_ACTION_KEYWORDS)


def _is_failure_reason_query_message(message: str) -> bool:
    lowered = _normalize_message(message).lower()
    return "失败" in lowered and _contains_any(lowered, _FAILURE_REASON_KEYWORDS)


def _is_restart_message(message: str) -> bool:
    lowered = _normalize_message(message).lower()
    if "重发" in lowered or "重来" in lowered:
        return True
    return "重新" in lowered and _contains_any(lowered, _RESTART_TARGET_KEYWORDS)


def _infer_request_kind_from_message(message: str) -> str:
    if not _is_short_followup_message(message):
        return ""
    if _is_confirm_execute_message(message):
        return "confirm_execute"
    if _is_detail_query_message(message):
        return "expand_plan_detail"
    if _is_failure_reason_query_message(message):
        return "query_failure_reason"
    if _is_result_query_message(message):
        return "query_result"
    if _is_plan_query_message(message):
        return "query_plan"
    if _is_status_query_message(message):
        return "query_status"
    if _is_restart_message(message):
        return "restart"
    return ""


def _matches_any_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    normalized = str(text or "").strip().lower()
    return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)


def _is_version_query(message: str) -> bool:
    return _matches_any_pattern(message, _VERSION_QUERY_PATTERNS)


def _is_request_debug_query(message: str) -> bool:
    return _matches_any_pattern(message, _REQUEST_DEBUG_PATTERNS)


def _is_supported_industry_query(message: str) -> bool:
    return _matches_any_pattern(message, _SUPPORTED_INDUSTRY_PATTERNS)


def _resolve_host_capabilities(payload: dict) -> dict[str, bool]:
    return normalize_host_capabilities(payload.get("host_capabilities"))


def _ensure_response_envelope(
    payload: dict,
    *,
    status: str = "",
    reply_markdown: str = "",
    session_id: str = "",
    session_event: str = "",
    local_only: bool = False,
    presentation: dict | None = None,
    host_capabilities: dict | None = None,
) -> dict:
    return build_response_envelope(
        payload,
        status=status,
        reply_markdown=reply_markdown,
        session_id=session_id,
        session_event=session_event,
        local_only=local_only,
        presentation=presentation,
        host_capabilities=host_capabilities,
    )


def _build_version_response(*, host_capabilities: dict | None = None) -> dict:
    metadata = load_build_metadata()
    version = str(metadata.get("skill_version") or "unknown").strip() or "unknown"
    return _ensure_response_envelope(
        {
            "skill_version": version,
        },
        status="LOCAL_INFO",
        reply_markdown=f"当前 AI Research skill 版本为 v{version}。",
        local_only=True,
        session_event="local_query_only",
        presentation={"card_type": "info"},
        host_capabilities=host_capabilities,
    )


def _build_supported_industry_response(*, host_capabilities: dict | None = None) -> dict:
    return _ensure_response_envelope(
        {
            "supported_industries": list(DIRECT_EXECUTABLE_INDUSTRIES),
        },
        status="LOCAL_INFO",
        reply_markdown=format_supported_industries_markdown(),
        local_only=True,
        session_event="local_query_only",
        presentation={"card_type": "info"},
        host_capabilities=host_capabilities,
    )


def _build_request_debug_response(
    state: dict,
    *,
    include_last_request: bool,
    host_capabilities: dict | None = None,
) -> dict:
    report = build_debug_report(state, include_last_request=include_last_request)
    last_request = report.get("last_request") if isinstance(report.get("last_request"), dict) else None
    if not last_request:
        reply = (
            "当前还没有可用的最近请求快照。"
            "请先发起一次调研请求；如果需要调试信息，再明确说明即可。"
        )
    else:
        curl_text = str(last_request.get("redacted_curl") or "").strip()
        lines = [
            "下面是最近一次请求的脱敏调试信息：",
            "",
            "```bash",
            curl_text or "# 暂无可展示的 curl 快照",
            "```",
        ]
        reply = "\n".join(lines)
    return _ensure_response_envelope(
        {
            "debug": True,
            "skill_version": str(report.get("skill_version") or ""),
            "last_request": last_request,
        },
        status="DEBUG_INFO",
        reply_markdown=reply,
        local_only=True,
        session_event="debug_query_only",
        presentation={"card_type": "debug"},
        host_capabilities=host_capabilities,
    )



def _build_status_query(request_body: dict) -> dict:
    query = {
        "session_id": request_body.get("session_id"),
        "source_channel": request_body.get("source_channel"),
    }
    app_id = request_body.get("app_id")
    if app_id not in (None, ""):
        query["app_id"] = app_id
    host_capabilities = request_body.get("host_capabilities")
    if isinstance(host_capabilities, dict) and host_capabilities:
        query["host_capabilities"] = json.dumps(host_capabilities, ensure_ascii=False, separators=(",", ":"))
    return query
def _query_status_once(status_url: str, request_body: dict, credential_value: str) -> dict:
    return _get_json(status_url, _build_status_query(request_body), credential_value, timeout_seconds=15)


def _should_recover_via_status_query(response: dict, http_status: int, transport_error: str) -> bool:
    code = int(response.get("code", 0) or 0)
    if code in {400, 401}:
        return False
    if transport_error:
        return True
    return code in _POLLABLE_FAILURE_CODES or http_status in _POLLABLE_FAILURE_CODES


def run_payload(
    payload: dict,
    *,
    state_path_override: Path | None = None,
) -> tuple[dict, int]:
    try:
        payload = dict(payload or {})
        message = str(payload.get("message") or "").strip()
        if not message:
            return {"error": "message is required"}, 1

        state_path = _resolve_runtime_state_path(payload, state_path_override)
        state = _load_state_at(state_path)
        if state.pop(payload_credential_field(), None) is not None:
            _save_state_at(state_path, state)
        debug_mode = bool(payload.get("debug_mode")) and DEBUG_QUERY_ENABLED
        normalized_host_capabilities = _resolve_host_capabilities(payload)

        if _is_version_query(message):
            return _build_version_response(host_capabilities=normalized_host_capabilities), 0

        if _is_supported_industry_query(message):
            return _build_supported_industry_response(host_capabilities=normalized_host_capabilities), 0

        if debug_mode and _is_request_debug_query(message):
            return (
                _build_request_debug_response(
                    state,
                    include_last_request=True,
                    host_capabilities=normalized_host_capabilities,
                ),
                0,
            )

        explicit_request_kind = str(payload.get("request_kind") or "").strip()
        inferred_request_kind = _infer_request_kind_from_message(message) if not explicit_request_kind else ""
        request_kind = explicit_request_kind or inferred_request_kind
        if request_kind:
            payload["request_kind"] = request_kind
        if request_kind in _RESULT_QUERY_KINDS and "status_only" not in payload:
            payload["status_only"] = True

        session_id = _resolve_session_id(payload, state)
        base_url = resolve_base_url(payload.get("base_url"))
        status_url = resolve_status_url(payload.get("base_url"))
        source_channel = resolve_source_channel(payload)
        current_request = _build_request_body(payload, message, session_id, source_channel)
        status_only = bool(payload.get("status_only"))

        inline_credential = extract_request_credential_from_text(message)
        credential_value = _resolve_credential(payload) or inline_credential
        pending_request = state.get("pending_request") if isinstance(state.get("pending_request"), dict) else None
        if not credential_value:
            session_event = "pending_request_waiting_auth"
            if not pending_request:
                state["pending_request"] = current_request
                state["session_id"] = session_id
                _save_state_at(state_path, state)
                session_event = "pending_request_saved"
            return (
                _build_auth_required_response(
                    session_id=session_id,
                    session_event=session_event,
                    host_capabilities=normalized_host_capabilities,
                ),
                0,
            )

        explicit_credential = str(payload.get(payload_credential_field()) or inline_credential or "").strip()
        request_body = dict(pending_request) if explicit_credential and pending_request else current_request
        if "source_channel" not in request_body or not request_body.get("source_channel"):
            request_body["source_channel"] = source_channel
        if "session_id" not in request_body or not request_body.get("session_id"):
            request_body["session_id"] = session_id
        if "message" not in request_body or not str(request_body.get("message") or "").strip():
            request_body["message"] = message

        headers = _build_request_headers(credential_value)
        state["session_id"] = str(request_body.get("session_id") or session_id)

        request_query = _build_status_query(request_body) if status_only else None
        effective_request_url = status_url if status_only else base_url
        if status_only:
            response = _query_status_once(status_url, request_body, credential_value)
        else:
            response = _post_json(
                base_url,
                request_body,
                credential_value,
                timeout_seconds=_resolve_request_timeout_seconds(payload),
            )
        http_status = int(response.pop("_http_status", 0) or 0)
        transport_error = str(response.pop("_transport_error", "") or "").strip()
        if int(response.get("code", 0) or 0) == 0 and _extract_status(_extract_data(response)) in _POLLABLE_STATUSES:
            response["data"] = _ensure_generating_reply_markdown(
                _extract_data(response),
                str(request_body.get("session_id") or session_id),
                normalized_host_capabilities,
            )

        if not status_only and _should_recover_via_status_query(response, http_status, transport_error):
            recovered = _query_status_once(status_url, request_body, credential_value)
            recovered_http_status = int(recovered.pop("_http_status", 0) or 0)
            recovered_transport_error = str(recovered.pop("_transport_error", "") or "").strip()
            if int(recovered.get("code", 0) or 0) == 401:
                _save_state_at(state_path, state)
                return (
                    _build_auth_required_response(
                        reason="invalid",
                        session_id=str(request_body.get("session_id") or session_id),
                        host_capabilities=normalized_host_capabilities,
                    ),
                    0,
                )
            if int(recovered.get("code", 0) or 0) == 0:
                response = recovered
                http_status = recovered_http_status
                transport_error = recovered_transport_error
                request_query = _build_status_query(request_body)
                effective_request_url = status_url
                if _extract_status(_extract_data(response)) in _POLLABLE_STATUSES:
                    response["data"] = _ensure_generating_reply_markdown(
                        _extract_data(response),
                        str(request_body.get("session_id") or session_id),
                        normalized_host_capabilities,
                    )

        save_last_request_debug(
            state_path,
            state,
            build_request_debug_snapshot(
                base_url=effective_request_url,
                request_body=request_body,
                headers=headers,
                response_payload=response,
                http_status=http_status,
                transport_error=transport_error,
                method="GET" if request_query else "POST",
                query_params=request_query,
            ),
        )

        code = int(response.get("code", 0) or 0)
        if code != 0:
            if code == 401:
                _save_state_at(state_path, state)
                return (
                    _build_auth_required_response(
                        reason="invalid",
                        session_id=str(request_body.get("session_id") or session_id),
                        host_capabilities=normalized_host_capabilities,
                    ),
                    0,
                )

            message_text = str(response.get("msg") or response.get("message") or response.get("error") or "").strip()
            if code == 400 and message_text:
                _save_state_at(state_path, state)
                return (
                    build_business_error_response(
                        message_text,
                        session_id=str(request_body.get("session_id") or session_id),
                        host_capabilities=normalized_host_capabilities,
                    ),
                    0,
                )

            _save_state_at(state_path, state)
            return (
                build_user_safe_failure_response(
                    session_id=str(request_body.get("session_id") or session_id),
                    host_capabilities=normalized_host_capabilities,
                ),
                0,
            )

        data = _extract_data(response)
        session_event = "pending_request_replayed" if explicit_credential and pending_request else ""
        data = _ensure_response_envelope(
            data,
            session_id=str(data.get("session_id") or request_body.get("session_id") or session_id),
            session_event=session_event,
            host_capabilities=normalized_host_capabilities,
        )
        if explicit_credential and pending_request:
            state.pop("pending_request", None)
        state["session_id"] = str(data.get("session_id") or request_body.get("session_id") or session_id)
        _save_state_at(state_path, state)
        return data, 0
    except Exception as exc:
        return {"error": str(exc)}, 1


def main() -> int:
    payload = read_stdin(sys.stdin.read())
    response, code = run_payload(payload)
    print(json.dumps(response, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
