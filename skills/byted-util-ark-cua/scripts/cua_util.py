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

"""Shared helpers for the AgentPlan CUA Skill CLI.

Stdlib only. Provides the unified JSON output contract and a structured error
type. The CLI never prints AgentPlan API keys, authorization headers, cache
contents, or raw artifact bytes.
"""

import json
import os
import sys
from datetime import datetime, timezone

# Errors that are safe to retry transparently: gateway/upstream timeouts,
# backend hiccups, rate limits, and local network blips. The CLI keeps polling
# on these instead of failing a whole task on a single 504.
RETRYABLE_ERROR_CODES = frozenset(
    {
        "GATEWAY_TIMEOUT",
        "CUA_BACKEND_UNAVAILABLE",
        "VOLCENGINE_REAL_NAME_CHECK_UNAVAILABLE",
        "RATE_LIMITED",
        "NETWORK",
    }
)


class SkillError(Exception):
    """An error that maps to the unified JSON error envelope.

    `code` follows the gateway error codes (AUTH_REQUIRED, TOKEN_EXPIRED,
    REFRESH_FAILED, FORBIDDEN, DESKTOP_NOT_BOUND, INVOCATION_NOT_FOUND,
    INVOCATION_NOT_WAITING_INPUT, ACTIVE_RUN_CONFLICT, MODEL_TIMEOUT,
    DESKTOP_UNHEALTHY, SESSION_CLEANUP, UPSTREAM_FAILURE,
    CUA_BACKEND_UNAVAILABLE, RATE_LIMITED, VALIDATION_ERROR, NETWORK, INTERNAL).
    """

    def __init__(self, code, message, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = {k: v for k, v in extra.items() if v is not None}


def emit_success(action, data=None):
    """Print a single-line JSON success envelope and exit 0."""
    payload = {"ok": True, "action": action}
    if data:
        payload.update(data)
    _print(payload)
    sys.exit(0)


def emit_error(action, error):
    """Print a single-line JSON error envelope and exit non-zero."""
    if isinstance(error, SkillError):
        body = {"code": error.code, "message": error.message}
        body.update(error.extra)
    else:
        body = {"code": "INTERNAL", "message": str(error)}
    payload = {"ok": False, "action": action, "error": body}
    next_hint = _next_for_error(body)
    if next_hint:
        payload["next"] = next_hint
    _print(payload)
    sys.exit(1)


def _next_for_error(body):
    code = body.get("code")
    if _is_active_run_conflict(body):
        return {
            "agent_hint": "The new CUA task was not started because the cloud desktop already has an active task/run. "
            "Stop here for this user request: do not retry, do not call delegate/task run/task continue again, "
            "and do not probe with diagnose/watch --last unless the user explicitly asks to inspect or cancel "
            "the existing task. Tell the user to wait until the current desktop task finishes, then try again.",
        }
    setup = body.get("setup_command")
    if code in ("AUTH_REQUIRED", "REFRESH_FAILED", "TOKEN_EXPIRED") and setup:
        if body.get("manual_login_required"):
            agent_hint = (
                "The user explicitly selected manual API-key login. Ask them to open a local "
                "terminal, run setup_command there, and enter the key through the hidden prompt. "
                "This path intentionally bypasses arkcli. Never ask them to paste the key into chat."
            )
        elif body.get("arkcli_status"):
            agent_hint = (
                "arkcli discovery already ran. Inspect error.arkcli_status and follow error.arkcli_hint first; "
                "never expose the key. If arkcli is unavailable or cannot be repaired, ask the user to open "
                "a local terminal, run setup_command there, and use the hidden API-key prompt. Never ask the "
                "user to paste the API key into chat."
            )
        else:
            agent_hint = (
                "Do not run setup_command yourself. Ask the user to open a local terminal, "
                "run setup_command there, enter their AgentPlan API key through the hidden prompt, "
                "then retry the original command. Never ask the user to paste the API key into chat."
            )
        next_hint = {
            "setup_command": setup,
            "agent_hint": agent_hint,
        }
        if body.get("environment_variables"):
            next_hint["environment_variables"] = body["environment_variables"]
        return next_hint
    retry = body.get("retry_command")
    if code in ("AUTH_REQUIRED", "REFRESH_FAILED") and retry:
        return {
            "setup_command": retry,
            "agent_hint": "Do not run retry_command yourself. Ask the user to open a local terminal, "
            "run it there, enter their AgentPlan API key in that terminal prompt, "
            "then retry the original command. Never ask the user to paste the API key into chat.",
        }
    if code == "TOKEN_EXPIRED" and retry:
        return {
            "setup_command": retry,
            "agent_hint": "Do not run retry_command yourself. Ask the user to run it "
            "in a local terminal, then retry the original command.",
        }
    if code == "MODEL_TIMEOUT":
        return {
            "agent_hint": "The model provider timed out. Report error.reason and error.request_id. "
            "Retry only when the operation is safe and the user wants to try again.",
        }
    if code == "VOLCENGINE_REAL_NAME_REQUIRED" and body.get("verification_url"):
        return {
            "verification_url": body["verification_url"],
            "agent_hint": "The API key is valid, but this operation would allocate a new CUA. "
            "Ask the user to complete Volcengine real-name verification at verification_url, "
            "then run `auth status` and retry. Existing allocated CUA invocations are unaffected.",
        }
    if code in ("DESKTOP_UNHEALTHY", "SESSION_CLEANUP", "UPSTREAM_FAILURE"):
        return {
            "agent_hint": "Do not retry blindly. Report error.reason, error.request_id, and any safe context "
            "so the owning service can diagnose the failure.",
        }
    if code in RETRYABLE_ERROR_CODES:
        return {
            "agent_hint": "Transient gateway/backend timeout — this is not a real failure. "
            "The task is likely still running. Just re-run the same command (for a long task, "
            "prefer `watch --last` or `result --last`).",
        }
    return None


def _is_active_run_conflict(body):
    code = str(body.get("code") or "").strip()
    if code in ("ACTIVE_RUN_CONFLICT", "active_run_conflict", "ActiveTaskRunning"):
        return True
    message = str(body.get("message") or "").lower()
    return code == "UpstreamError" and (
        "already active" in message
        or "active task" in message
        or "active run" in message
        or "desktop run is already active" in message
    )


def _print(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def now_epoch():
    return datetime.now(timezone.utc).timestamp()


def script_path():
    return os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else "scripts/cua.py"


def command_prefix():
    return f"python3 {script_path()}"


def login_setup_command(manual=False):
    """The command the user should run in their own local terminal to login."""
    suffix = " --manual" if manual else ""
    return f"{command_prefix()} auth login{suffix}"


# MIME type -> file extension, for artifact downloads that don't specify a name.
_EXT_BY_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "application/pdf": ".pdf",
    "application/json": ".json",
    "application/zip": ".zip",
    "application/octet-stream": ".bin",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "text/html": ".html",
    "text/markdown": ".md",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


def ext_for_mime(mime_type):
    """Best-effort file extension for a MIME type. Defaults to .bin."""
    if not mime_type:
        return ".bin"
    base = mime_type.split(";", 1)[0].strip().lower()
    if base in _EXT_BY_MIME:
        return _EXT_BY_MIME[base]
    # Fall back to the subtype for unknown but well-formed types (e.g. image/heic -> .heic).
    if "/" in base:
        subtype = base.split("/", 1)[1]
        subtype = subtype.split("+", 1)[0]
        if subtype.isalnum():
            return "." + subtype
    return ".bin"
