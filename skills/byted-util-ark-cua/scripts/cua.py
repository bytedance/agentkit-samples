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

"""AgentPlan CUA Skill CLI — the single entrypoint an agent calls to drive CUA.

    python3 <skill_dir>/scripts/cua.py <command> [options]

Every invocation prints exactly one JSON object:

    {"ok": true,  "action": "<command>", "data": {...}, "next": {...}}
    {"ok": false, "action": "<command>", "error": {"code": "...", "message": "..."}}

Stdlib only. API keys, authorization headers, cache contents, and artifact bytes
are never printed. See references/ for command and error documentation.
"""

import argparse
import base64
import json
import os
import queue
import secrets
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path

import cua_auth
import cua_http
from cua_state import AuthState, SessionState
from cua_util import (
    RETRYABLE_ERROR_CODES,
    SkillError,
    command_prefix,
    emit_error,
    emit_success,
    ext_for_mime,
    login_setup_command,
    now_epoch,
)

# Long tasks use repeated waits. Each request stays within the gateway's 60-second
# server limit while the CLI tracks the user's larger total wait budget.
DEFAULT_WATCH_WAIT_MS = 20000
RESULT_POLL_WAIT_MS = 20000
SERVER_WAIT_CHUNK_MS = 60000
IDEMPOTENT_RETRIES = 2
CREDENTIAL_TARGET_PROTOCOL = "cua-target/v1"
CREDENTIAL_RUNTIME = Path(__file__).resolve().parents[1]
CREDENTIAL_PAIR_POLL_INTERVAL_SEC = 0.5
CREDENTIAL_GATEWAY_TOOLS = {
    "cua_credential_capabilities",
    "cua_credential_begin",
    "cua_credential_health",
    "cua_credential_browser_authorize_begin",
    "cua_credential_browser_authorize_watch",
    "cua_credential_browser_network_ensure",
    "cua_credential_finish",
    "cua_credential_reset",
}
CREDENTIAL_DEVICE_FEATURES = {"initialize", "pair-relay-v1", "health-v1"}
CREDENTIAL_BROWSER_FEATURES = CREDENTIAL_DEVICE_FEATURES | {
    "browser-unpacked-ensure",
    "browser-authorize-v1",
    "browser-network-ensure-v1",
}


def emit_target_success(action, data):
    payload = {
        "schema_version": 1,
        "adapter_protocol": CREDENTIAL_TARGET_PROTOCOL,
        "ok": True,
        "action": action,
        "data": data,
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    raise SystemExit(0)


def emit_target_error(action, error):
    code = _target_error_code(getattr(error, "code", "TARGET_AGENT_UNAVAILABLE"))
    payload = {
        "schema_version": 1,
        "adapter_protocol": CREDENTIAL_TARGET_PROTOCOL,
        "ok": False,
        "action": action,
        "error": {
            "code": code,
            "message": getattr(error, "message", "Credential target operation failed."),
            "retryable": code in {
                "TARGET_BUSY", "TARGET_AGENT_UNAVAILABLE", "OPERATION_IN_PROGRESS", "NETWORK_AMBIGUOUS"
            },
        },
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    raise SystemExit(1)


def _target_error_code(code):
    value = str(code or "").strip()
    direct = {
        "TARGET_NOT_FOUND", "TARGET_NOT_AUTHORIZED", "TARGET_BUSY",
        "TARGET_AGENT_UNAVAILABLE", "PAIR_RELAY_EXPIRED", "PAIR_RELAY_CLOCK_SKEW",
        "PAIR_RELAY_TARGET_MISMATCH", "BROWSER_SETUP_REQUIRED",
        "BROWSER_PERMISSION_REQUIRED", "BROWSER_NETWORK_UNREACHABLE",
        "OPERATION_IN_PROGRESS", "WORKFLOW_EXPIRED", "NETWORK_AMBIGUOUS",
    }
    if value in direct:
        return value
    mapping = {
        "AUTH_REQUIRED": "TARGET_NOT_AUTHORIZED",
        "FORBIDDEN": "TARGET_NOT_AUTHORIZED",
        "DESKTOP_NOT_BOUND": "TARGET_NOT_FOUND",
        "INVOCATION_NOT_FOUND": "WORKFLOW_EXPIRED",
        "CONFLICT": "TARGET_BUSY",
        "DESKTOP_BUSY": "TARGET_BUSY",
        "ACTIVE_RUN_CONFLICT": "TARGET_BUSY",
        "GATEWAY_TIMEOUT": "NETWORK_AMBIGUOUS",
        "CUA_BACKEND_UNAVAILABLE": "NETWORK_AMBIGUOUS",
        "UPSTREAM_TIMEOUT": "NETWORK_AMBIGUOUS",
        "NETWORK": "NETWORK_AMBIGUOUS",
    }
    return mapping.get(value, "TARGET_AGENT_UNAVAILABLE")


class ParserHelp(Exception):
    """Carry argparse help text to the unified JSON success envelope."""

    def __init__(self, text):
        super().__init__(text)
        self.text = text


class JsonArgumentParser(argparse.ArgumentParser):
    """Route all argparse output through the CLI's one-JSON-object contract."""

    def error(self, message):
        raise SkillError(
            "VALIDATION_ERROR",
            message,
            usage=self.format_usage().strip(),
        )

    def print_help(self, file=None):
        del file
        raise ParserHelp(self.format_help())

    def exit(self, status=0, message=None):
        if status == 0:
            raise ParserHelp(self.format_help())
        raise SkillError(
            "VALIDATION_ERROR",
            (message or "Invalid command-line arguments.").strip(),
            usage=self.format_usage().strip(),
        )


def main(argv=None):
    action = "<parse>"
    try:
        parser = build_parser()
        args = parser.parse_args(argv)
        action = getattr(args, "action", None) or "<parse>"
        if action == "<parse>":
            raise SkillError(
                "VALIDATION_ERROR",
                "A command and subcommand are required.",
                usage=parser.format_usage().strip(),
            )
        state = AuthState.load()
        session = SessionState.load()
        data = args.handler(args, state, session)
        emit_success(action, data)
    except ParserHelp as exc:
        emit_success("help", {"data": {"usage": exc.text}})
    except SkillError as exc:
        if action.startswith("credential-target "):
            emit_target_error(action[len("credential-target "):], exc)
        emit_error(action, exc)
    except BrokenPipeError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface unexpected errors as JSON, not tracebacks
        emit_error(action, SkillError("INTERNAL", str(exc)))


# -- base URL --------------------------------------------------------------


def resolve_base_url(args, state, persist=False):
    base_url = (
        args.api_base_url
        or os.environ.get("AP_CUA_SKILL_API_BASE_URL")
        or os.environ.get("CUA_SKILL_API_BASE_URL")
        or state.api_base_url
        or bundled_base_url()
    )
    if not base_url:
        raise SkillError(
            "VALIDATION_ERROR",
            "No CUA gateway configured. Set api_base_url in the skill's assets/config.json, "
            "pass --api-base-url, or set AP_CUA_SKILL_API_BASE_URL.",
        )
    base_url = _validate_base_url(base_url)
    if persist and state.api_base_url != base_url:
        state.set_api_base_url(base_url)
    return base_url


def _validate_base_url(base_url):
    """Require encrypted bearer-token transport except for loopback testing."""
    if not isinstance(base_url, str) or not base_url.strip():
        raise SkillError("VALIDATION_ERROR", "CUA gateway URL must be a non-empty URL.")
    base_url = base_url.strip().rstrip("/")
    try:
        parts = urllib.parse.urlsplit(base_url)
        hostname = parts.hostname
        _ = parts.port  # Validate malformed/non-numeric ports eagerly.
    except ValueError as exc:
        raise SkillError("VALIDATION_ERROR", "CUA gateway URL is invalid.") from exc
    if not hostname or parts.username is not None or parts.password is not None:
        raise SkillError(
            "VALIDATION_ERROR",
            "CUA gateway URL must include a host and must not include user credentials.",
        )
    scheme = parts.scheme.lower()
    is_loopback_http = scheme == "http" and hostname.lower() in {
        "localhost",
        "127.0.0.1",
        "::1",
    }
    if scheme != "https" and not is_loopback_http:
        raise SkillError(
            "VALIDATION_ERROR",
            "CUA gateway URL must use HTTPS; HTTP is allowed only for localhost, 127.0.0.1, or ::1.",
        )
    return base_url


def bundled_base_url():
    """Gateway URL shipped as a bundled asset (publisher-set, once)."""
    data = bundled_config()
    url = data.get("api_base_url")
    if not isinstance(url, str):
        return None
    url = url.strip()
    if not url or url.startswith("<") or "REPLACE" in url or "example.com" in url:
        return None
    return url


def bundled_config():
    """Read the publisher-controlled, non-secret bundled configuration."""
    try:
        cfg_path = Path(__file__).resolve().parent.parent / "assets" / "config.json"
        if not cfg_path.exists():
            return {}
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


# -- auth commands ---------------------------------------------------------


def cmd_auth_status(args, state, session):
    base_url = resolve_base_url(args, state)
    return {"data": cua_auth.auth_status(state, base_url)}


def cmd_auth_login(args, state, session):
    base_url = resolve_base_url(args, state, persist=True)
    return {"data": cua_auth.login(
        state, base_url,
        prompt=not args.no_prompt,
        manual=args.manual,
    )}


def cmd_auth_logout(args, state, session):
    base_url = resolve_base_url(args, state)
    return {"data": cua_auth.logout(state, base_url)}


# -- CUA commands ----------------------------------------------------------


def cmd_ping(args, state, session):
    base_url = resolve_base_url(args, state)
    return {"data": cua_auth.authorized_call(state, base_url, "GET", "/v1/ping", retries=IDEMPOTENT_RETRIES)}


def cmd_delegate(args, state, session):
    base_url = resolve_base_url(args, state)
    _validate_wait_ms(args.wait_ms)
    # Always create without a synchronous wait so the invocation id is captured
    # before any long polling. This prevents a timeout from causing a duplicate
    # task submission.
    body = {"objective": args.objective, "wait_ms": 0}
    envelope = cua_auth.authorized_call(
        state, base_url, "POST", "/v1/invocations", body=body, timeout=_call_timeout(0)
    )
    envelope = _wait_invocation_with_budget(
        state, base_url, envelope.get("invocation_id"), args.wait_ms, initial_envelope=envelope
    )
    return _envelope_result("delegate", envelope, session)


def cmd_watch(args, state, session):
    base_url = resolve_base_url(args, state)
    invocation_id = _resolve_invocation_id(args, session)
    envelope = _wait_invocation_with_budget(state, base_url, invocation_id, args.wait_ms)
    return _envelope_result("watch", envelope, session)


def cmd_answer(args, state, session):
    base_url = resolve_base_url(args, state)
    _validate_wait_ms(args.wait_ms)
    invocation_id = _resolve_invocation_id(args, session)
    body = {"answer": args.answer, "wait_ms": 0}
    envelope = cua_auth.authorized_call(
        state, base_url, "POST", f"/v1/invocations/{invocation_id}/answer",
        body=body, timeout=_call_timeout(0)
    )
    envelope = _wait_invocation_with_budget(
        state, base_url, invocation_id, args.wait_ms, initial_envelope=envelope
    )
    return _envelope_result("answer", envelope, session)


def cmd_cancel(args, state, session):
    base_url = resolve_base_url(args, state)
    invocation_id = _resolve_invocation_id(args, session)
    data = cua_auth.authorized_call(
        state, base_url, "POST", f"/v1/invocations/{invocation_id}/cancel", retries=IDEMPOTENT_RETRIES
    )
    return {"data": data}


def cmd_result(args, state, session):
    base_url = resolve_base_url(args, state)
    invocation_id = _resolve_invocation_id(args, session)
    deadline = now_epoch() + max(1, args.timeout)
    envelope = None
    while now_epoch() < deadline:
        try:
            if envelope is None:
                envelope = cua_auth.authorized_call(
                    state, base_url, "GET", f"/v1/invocations/{invocation_id}", retries=IDEMPOTENT_RETRIES
                )
            if envelope.get("outcome") != "in_progress":
                break
            envelope = cua_auth.authorized_call(
                state, base_url, "POST", f"/v1/invocations/{invocation_id}/watch",
                body={"wait_ms": RESULT_POLL_WAIT_MS}, timeout=_call_timeout(RESULT_POLL_WAIT_MS),
                retries=IDEMPOTENT_RETRIES
            )
        except SkillError as exc:
            # Transient gateway/backend timeout — the task is still running; keep polling.
            if exc.code in RETRYABLE_ERROR_CODES:
                envelope = None
                time.sleep(2)
                continue
            raise
    if envelope is None:
        # Could not reach a state read within the deadline; report in_progress.
        envelope = cua_auth.authorized_call(
            state, base_url, "GET", f"/v1/invocations/{invocation_id}", retries=IDEMPOTENT_RETRIES
        )
    return _envelope_result("result", envelope, session)


# -- semantic commands -----------------------------------------------------


def cmd_diagnose(args, state, session):
    base_url = resolve_base_url(args, state)
    data = cua_auth.authorized_call(state, base_url, "GET", "/v1/diagnostics", retries=IDEMPOTENT_RETRIES)
    return {"data": data}


def cmd_desktop_list(args, state, session):
    base_url = resolve_base_url(args, state)
    data = cua_auth.authorized_call(state, base_url, "GET", "/v1/desktop-options", retries=IDEMPOTENT_RETRIES)
    return {"data": data}


def cmd_desktop_access(args, state, session):
    base_url = resolve_base_url(args, state)
    data = cua_auth.authorized_call(
        state, base_url, "GET", "/v1/desktop/access", timeout=120,
        retries=IDEMPOTENT_RETRIES,
    )
    access_url = data.get("access_url")
    if access_url:
        desktop_view_url, full_interface_url = _derive_desktop_urls(access_url)
        if desktop_view_url:
            data["desktop_view_url"] = desktop_view_url
        if full_interface_url:
            data["full_interface_url"] = full_interface_url
    hint = (
        "Return this newly issued full_interface_url (or access_url when unavailable) only when "
        "the user requested the CUA App link. Never reuse a URL from an earlier command result. "
        "If opening it reports runtime_capability_required, revoke this ticket and run desktop "
        "access once for a fresh URL; do not rewrite the path."
    )
    return {"data": data, "next": {"agent_hint": hint}}


def cmd_desktop_revoke_access(args, state, session):
    base_url = resolve_base_url(args, state)
    body = {"ticket": args.ticket} if args.ticket else {"access_url": args.access_url}
    data = cua_auth.authorized_call(
        state, base_url, "POST", "/v1/desktop/access/revoke", body=body,
        retries=IDEMPOTENT_RETRIES,
    )
    return {"data": data, "next": {
        "agent_hint": "The temporary CUA App URL has been revoked. Run desktop access if the user needs a new link.",
    }}


def cmd_desktop_shutdown(args, state, session):
    base_url = resolve_base_url(args, state)
    body = {
        "confirm": True,
        "idempotency_key": args.idempotency_key,
        "reason": "user_requested_shutdown",
    }
    if args.desktop:
        body["desktop_id"] = args.desktop
    data = cua_auth.authorized_call(
        state, base_url, "POST", "/v1/desktop/release", body=body,
    )
    operation_id = data.get("operation_id")
    next_action = {
        "agent_hint": "The shutdown request ended billing entitlement and revoked desktop access. "
        "Physical stop or deletion is asynchronous; do not use the old desktop. If "
        "data.operation.recoverable is true, retain data.desktop.desktop_id and "
        "data.operation.purge_after so a later explicit desktop start can recover it before the "
        "retention deadline.",
    }
    if operation_id:
        next_action["command"] = (
            f"{command_prefix()} desktop operation --operation-id {operation_id}"
        )
    return {"data": data, "next": next_action}


def cmd_desktop_start(args, state, session):
    base_url = resolve_base_url(args, state)
    body = {"idempotency_key": args.idempotency_key}
    if args.desktop:
        body["desktop_id"] = args.desktop
    data = cua_auth.authorized_call(
        state, base_url, "POST", "/v1/desktop/start", body=body,
    )
    operation = data.get("operation") if isinstance(data.get("operation"), dict) else {}
    operation_id = data.get("operation_id") or operation.get("operation_id")
    action = data.get("action") or "start"
    if operation_id:
        return {"data": data, "next": {
            "command": f"{command_prefix()} desktop operation --operation-id {operation_id}",
            "agent_hint": (
                f"Desktop {action} is in progress. Keep checking this logical operation until it "
                "is terminal; only succeeded means the desktop and its required access and "
                "entitlement state are ready."
            ),
        }}
    return {"data": data, "next": {
        "agent_hint": (
            f"Desktop start completed with action {action}. Use data.restoring and "
            "data.newly_allocated to distinguish retained recovery from reuse or new allocation."
        ),
    }}


def cmd_desktop_operation(args, state, session):
    base_url = resolve_base_url(args, state)
    data = cua_auth.authorized_call(
        state,
        base_url,
        "GET",
        f"/v1/desktop/operations/{args.operation_id}",
        retries=IDEMPOTENT_RETRIES,
    )
    status = data.get("status")
    terminal = data.get("terminal") is True
    if terminal:
        hint = (
            "The desktop lifecycle operation is terminal. Report whether it succeeded or failed "
            "from data.status and data.operation."
        )
        return {"data": data, "next": {"agent_hint": hint}}
    return {"data": data, "next": {
        "command": f"{command_prefix()} desktop operation --operation-id {args.operation_id}",
        "agent_hint": (
            f"The desktop lifecycle operation is still {status or 'running'}. Keep checking this "
            "same operation; do not submit another start or shutdown request."
        ),
    }}


def cmd_model_get(args, state, session):
    base_url = resolve_base_url(args, state)
    data = cua_auth.authorized_call(state, base_url, "GET", "/v1/model-config", retries=IDEMPOTENT_RETRIES)
    return {"data": data, "next": {
        "agent_hint": "This is the default model config for future CUA delegations on the bound desktop.",
    }}


def cmd_task_run(args, state, session):
    base_url = resolve_base_url(args, state)
    _validate_wait_ms(args.wait_ms)
    body = {"objective": args.objective, "wait_ms": 0}
    if args.desktop:
        body["desktop"] = args.desktop
    if args.title:
        body["title"] = args.title
    envelope = cua_auth.authorized_call(
        state, base_url, "POST", "/v1/tasks", body=body, timeout=_call_timeout(0)
    )
    envelope = _wait_invocation_with_budget(
        state, base_url, envelope.get("invocation_id"), args.wait_ms, initial_envelope=envelope
    )
    return _task_result("task run", envelope, session)


def cmd_task_continue(args, state, session):
    base_url = resolve_base_url(args, state)
    _validate_wait_ms(args.wait_ms)
    context_id = _resolve_context_id(args, session)
    body = {"objective": args.objective, "wait_ms": 0}
    envelope = cua_auth.authorized_call(
        state, base_url, "POST", f"/v1/contexts/{context_id}/tasks", body=body, timeout=_call_timeout(0)
    )
    envelope = _wait_invocation_with_budget(
        state, base_url, envelope.get("invocation_id"), args.wait_ms, initial_envelope=envelope
    )
    return _task_result("task continue", envelope, session)


def cmd_task_status(args, state, session):
    base_url = resolve_base_url(args, state)
    task_id = _resolve_task_id(args, session)
    envelope = cua_auth.authorized_call(
        state, base_url, "GET", f"/v1/tasks/{task_id}", retries=IDEMPOTENT_RETRIES
    )
    return _task_result("task status", envelope, session)


def cmd_task_result(args, state, session):
    base_url = resolve_base_url(args, state)
    task_id = _resolve_task_id(args, session)
    deadline = now_epoch() + max(1, args.timeout)
    envelope = None
    while now_epoch() < deadline:
        try:
            envelope = cua_auth.authorized_call(
                state, base_url, "GET", f"/v1/tasks/{task_id}/result", retries=IDEMPOTENT_RETRIES
            )
            if envelope.get("outcome") != "in_progress":
                break
            time.sleep(3)
        except SkillError as exc:
            if exc.code in RETRYABLE_ERROR_CODES:
                time.sleep(2)
                continue
            raise
    if envelope is None:
        envelope = cua_auth.authorized_call(
            state, base_url, "GET", f"/v1/tasks/{task_id}/result", retries=IDEMPOTENT_RETRIES
        )
    return _task_result("task result", envelope, session)


def cmd_task_answer(args, state, session):
    base_url = resolve_base_url(args, state)
    _validate_wait_ms(args.wait_ms)
    task_id = _resolve_task_id(args, session)
    body = {"answer": args.answer, "wait_ms": 0}
    envelope = cua_auth.authorized_call(
        state, base_url, "POST", f"/v1/tasks/{task_id}/answer", body=body, timeout=_call_timeout(0)
    )
    envelope = _wait_invocation_with_budget(
        state, base_url, task_id, args.wait_ms, initial_envelope=envelope
    )
    return _task_result("task answer", envelope, session)


def cmd_task_cancel(args, state, session):
    base_url = resolve_base_url(args, state)
    task_id = _resolve_task_id(args, session)
    data = cua_auth.authorized_call(
        state, base_url, "POST", f"/v1/tasks/{task_id}/cancel", retries=IDEMPOTENT_RETRIES
    )
    return {"data": data}


def cmd_context_list(args, state, session):
    base_url = resolve_base_url(args, state)
    data = cua_auth.authorized_call(state, base_url, "GET", "/v1/contexts", retries=IDEMPOTENT_RETRIES)
    return {"data": data}


def cmd_context_create(args, state, session):
    base_url = resolve_base_url(args, state)
    body = {}
    if args.title:
        body["title"] = args.title
    if args.desktop:
        body["desktop"] = args.desktop
    data = cua_auth.authorized_call(state, base_url, "POST", "/v1/contexts", body=body)
    context_id = data.get("context_id")
    if context_id:
        session.set_last(last_context_id=context_id)
    return {"data": data, "next": {
        "command": f"{command_prefix()} task continue --context-id {context_id} --objective \"<TASK>\"",
        "agent_hint": "Context created. Add background with context add-note, or start work with task continue.",
    }}


def cmd_context_add_note(args, state, session):
    base_url = resolve_base_url(args, state)
    context_id = _resolve_context_id(args, session)
    data = cua_auth.authorized_call(
        state, base_url, "POST", f"/v1/contexts/{context_id}/notes", body={"text": args.text}
    )
    return {"data": data}


def cmd_context_show(args, state, session):
    base_url = resolve_base_url(args, state)
    context_id = _resolve_context_id(args, session)
    data = cua_auth.authorized_call(
        state, base_url, "GET", f"/v1/contexts/{context_id}", retries=IDEMPOTENT_RETRIES
    )
    return {"data": data}


def cmd_timeline_show(args, state, session):
    base_url = resolve_base_url(args, state)
    context_id = _resolve_context_id(args, session)
    data = cua_auth.authorized_call(
        state, base_url, "GET", f"/v1/contexts/{context_id}/timeline", retries=IDEMPOTENT_RETRIES
    )
    return {"data": data}


def cmd_artifact_list(args, state, session):
    base_url = resolve_base_url(args, state)
    task_id = _resolve_task_id(args, session)
    data = cua_auth.authorized_call(
        state, base_url, "GET", f"/v1/tasks/{task_id}/artifacts", retries=IDEMPOTENT_RETRIES
    )
    return {"data": data}


def cmd_artifact_save(args, state, session):
    base_url = resolve_base_url(args, state)
    artifact_id = args.artifact_id or (session.last_artifact_id if args.last else None)
    if not artifact_id:
        raise SkillError("VALIDATION_ERROR", "artifact_id is required. Pass --artifact-id <id> or --last.")
    task_id = args.task_id or session.last_task_id
    query = {"task_id": task_id} if task_id else None
    headers, raw = cua_auth.authorized_raw_call(
        state, base_url, "GET", f"/v1/artifacts/{artifact_id}/content",
        query=query, timeout=120, retries=IDEMPOTENT_RETRIES
    )
    session.set_last(last_artifact_id=artifact_id)
    data = _legacy_artifact_envelope(raw, headers)
    if data is None:
        mime_type = _content_type(headers)
        if _looks_like_html(mime_type, raw):
            return {"data": {
                "source_artifact_id": artifact_id,
                "source_task_id": task_id,
                "file": None,
                "mime_type": mime_type,
                "bytes": len(raw),
                "suspect_html": True,
            }, "next": {
                "agent_hint": "The downloaded bytes look like an HTML page, not the expected file. "
                "The file was not written. Ask CUA to re-export the artifact instead.",
            }}
        path = _write_artifact(raw, args.output, mime_type)
        result = {
            "source_artifact_id": artifact_id,
            "source_task_id": task_id,
            "file": path,
            "mime_type": mime_type,
            "bytes": len(raw),
            "transport": "raw",
        }
        return {"data": result, "next": {
            "agent_hint": "Artifact saved to data.file from raw bytes. "
            "Share the path with the user; do not print the bytes.",
        }}

    if data.get("missing"):
        return {"data": {
            "source_artifact_id": artifact_id,
            "source_task_id": task_id,
            "file": None,
            "missing": True,
            "placeholder_text": data.get("placeholder_text"),
        }, "next": {
            "agent_hint": "The artifact has no downloadable bytes (placeholder/missing). "
            "Tell the user it is unavailable; do not claim a file was saved.",
        }}

    b64 = data.get("data")
    if not b64:
        raise SkillError("INTERNAL", "Artifact response contained no data and was not marked missing.")
    try:
        raw = base64.b64decode(b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise SkillError("INTERNAL", f"Artifact was not valid base64: {exc}")

    mime_type = data.get("mime_type")
    # A surprise HTML payload usually means an error/interstitial page (e.g. a
    # Cloudflare challenge from an external share link), not the real file.
    if _looks_like_html(mime_type, raw):
        return {"data": {
            "source_artifact_id": artifact_id,
            "source_task_id": task_id,
            "file": None,
            "mime_type": mime_type,
            "bytes": len(raw),
            "suspect_html": True,
        }, "next": {
            "agent_hint": "The downloaded bytes look like an HTML page, not the expected file. "
            "The file was not written. Ask CUA to re-export the artifact instead.",
        }}
    path = _write_artifact(raw, args.output, mime_type)
    result = {
        "source_artifact_id": artifact_id,
        "source_task_id": task_id,
        "file": path,
        "mime_type": mime_type,
        "bytes": len(raw),
        "transport": "legacy_base64",
    }
    return {"data": result, "next": {
        "agent_hint": "Artifact saved to data.file. Share the path with the user; do not print the bytes.",
    }}


def cmd_self_test(args, state, session):
    """Local-only checks. Does not create CUA tasks or call backends."""
    checks = {
        "python_version": sys.version.split()[0],
        "python_ok": sys.version_info >= (3, 8),
        "auth_file": str(state.path),
        "logged_in": bool(state.access_token),
        "api_base_url": resolve_base_url(args, state) if _has_base_url(args, state) else None,
        "last_invocation_id": session.last_invocation_id,
        "credential_runtime": {
            "embedded": True,
            "adapter_protocol": CREDENTIAL_TARGET_PROTOCOL,
        },
    }
    next_hint = None
    if not checks["logged_in"]:
        next_hint = {
            "setup_command": login_setup_command(),
            "agent_hint": "Not logged in yet. Do not run setup_command yourself; ask the user to run it in a local terminal before real work.",
        }
    return {"data": checks, "next": next_hint} if next_hint else {"data": checks}


# -- Credential Skill integration -----------------------------------------


def _credential_tool(args, state, name, payload, *, timeout=120):
    base_url = resolve_base_url(args, state)
    return cua_auth.authorized_tool_call(
        state, base_url, name, payload, timeout=timeout
    )


def _credential_runtime_environment():
    environment_id = str(
        os.environ.get("CREDENTIAL_AGENT_ENVIRONMENT_ID") or ""
    ).strip().lower()
    if environment_id != "prod":
        raise SkillError(
            "TARGET_CAPABILITY_UNAVAILABLE",
            "Credential target operations require the production environment.",
        )
    return environment_id


def _credential_gateway_preflight(args, state, *, browser=False, reset=False):
    base_url = resolve_base_url(args, state)
    manifest = cua_auth.authorized_manifest(state, base_url, timeout=30)
    capabilities = manifest.get("capabilities") if isinstance(manifest.get("capabilities"), dict) else {}
    tools = {
        str(tool.get("name") or "").strip()
        for tool in (manifest.get("tools") or [])
        if isinstance(tool, dict) and tool.get("enabled") is True
    }
    missing_tools = sorted(CREDENTIAL_GATEWAY_TOOLS - tools)
    if capabilities.get("credentials") is not True or missing_tools:
        raise SkillError(
            "TARGET_CAPABILITY_UNAVAILABLE",
            "Credential tools are not enabled on this AgentPlan Skill Gateway.",
            missing_tools=missing_tools,
        )
    payload = {"desktop_id": args.desktop_id} if getattr(args, "desktop_id", None) else {}
    target = _credential_tool(args, state, "cua_credential_capabilities", payload, timeout=30)
    if target.get("adapter_protocol") != CREDENTIAL_TARGET_PROTOCOL or target.get("transport") != "access_hub_gateway":
        raise SkillError("TARGET_CAPABILITY_UNAVAILABLE", "Gateway does not advertise the isolated CUA Target Adapter v1.")
    if target.get("environment_id") != "prod":
        raise SkillError("TARGET_CAPABILITY_UNAVAILABLE", "Gateway does not advertise the production Credential environment.")
    required = {"reset-e2e-v1"} if reset else (CREDENTIAL_BROWSER_FEATURES if browser else CREDENTIAL_DEVICE_FEATURES)
    missing_features = sorted(required - set(target.get("features") or []))
    if missing_features:
        raise SkillError(
            "TARGET_CAPABILITY_UNAVAILABLE",
            "The selected CUA target is missing required Credential features.",
            missing_features=missing_features,
        )
    return target


def _safe_agent_path(value):
    path = Path(str(value or "")).expanduser()
    if not path.is_absolute():
        raise SkillError("TARGET_AGENT_UNAVAILABLE", "Pass an absolute --agent-path for the signed local credential-agent.")
    try:
        info = path.lstat()
    except OSError as exc:
        raise SkillError("TARGET_AGENT_UNAVAILABLE", "The local credential-agent path does not exist.") from exc
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or (os.name != "nt" and info.st_mode & 0o022)
        or (os.name != "nt" and not os.access(path, os.X_OK))
    ):
        raise SkillError(
            "TARGET_AGENT_UNAVAILABLE",
            "The local credential-agent must be an executable non-symlink file not writable by group or others.",
        )
    return path


def _relay_process(agent_path, desktop_name):
    process = subprocess.Popen(
        [
            str(agent_path), "pair", "--approve", "--relay-stdin",
            "--expected-device-name", desktop_name,
            "--expected-device-type", "cloud_desktop",
            "--output", "jsonl",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    events = queue.Queue()

    def reader():
        assert process.stdout is not None
        for line in process.stdout:
            events.put(line)
        events.put(None)

    threading.Thread(target=reader, daemon=True).start()
    return process, events


def _relay_event(events, timeout_seconds):
    try:
        line = events.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        raise SkillError("TARGET_AGENT_UNAVAILABLE", "Local credential-agent did not initialize pair relay in time.") from exc
    if line is None:
        raise SkillError("TARGET_AGENT_UNAVAILABLE", "Local credential-agent exited before pair relay was ready.")
    try:
        value = json.loads(line)
    except json.JSONDecodeError as exc:
        raise SkillError("TARGET_AGENT_UNAVAILABLE", "Local credential-agent returned invalid relay output.") from exc
    if not isinstance(value, dict):
        raise SkillError("TARGET_AGENT_UNAVAILABLE", "Local credential-agent returned invalid relay output.")
    return value


def _finish_local_relay(process, events, deadline):
    result = None
    while result is None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SkillError("TARGET_AGENT_UNAVAILABLE", "Local credential-agent approval timed out.")
        event = _relay_event(events, remaining)
        if event.get("type") == "result":
            result = event
    remaining = max(0.1, deadline - time.monotonic())
    try:
        return_code = process.wait(timeout=remaining)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        raise SkillError("TARGET_AGENT_UNAVAILABLE", "Local credential-agent did not exit after approval.") from exc
    if return_code != 0 or result.get("status") != "succeeded":
        error = result.get("error") if isinstance(result.get("error"), dict) else {}
        reported = str(error.get("code") or "")
        allowed = {"PAIR_RELAY_EXPIRED", "PAIR_RELAY_CLOCK_SKEW", "PAIR_RELAY_TARGET_MISMATCH"}
        raise SkillError(
            reported if reported in allowed else "TARGET_AGENT_UNAVAILABLE",
            "Local credential-agent did not approve the exact CUA pairing request.",
        )
    device = (result.get("details") or {}).get("device")
    return str(device.get("id") or "").strip() if isinstance(device, dict) else ""


def _validate_pair_relay_completion(completed, *, workflow_id, desktop_id):
    completed_workflow_id = str(completed.get("workflow_id") or "").strip()
    completed_desktop_id = str(completed.get("desktop_id") or "").strip()
    device_id = str(completed.get("device_id") or "").strip()
    if not device_id:
        raise SkillError("TARGET_AGENT_UNAVAILABLE", "Gateway did not return the enrolled target Device ID.")
    if completed_workflow_id != workflow_id or completed_desktop_id != desktop_id:
        raise SkillError("PAIR_RELAY_TARGET_MISMATCH", "Gateway completed enrollment for a different Credential target.")
    # The local approval result identifies the authenticated control device
    # that approved this operation. The completion result identifies the newly
    # enrolled cloud-desktop device, so those cross-role IDs must not be
    # compared. Target identity remains bound by the encrypted pair operation,
    # exact resource binding, workflow ID, and desktop ID checked above.
    return device_id


def _credential_begin_once(args, state, request_id):
    payload = {"mode": args.mode, "request_id": request_id}
    if args.desktop_id:
        payload["desktop_id"] = args.desktop_id
    return _credential_tool(
        args, state, "cua_credential_begin", payload,
        timeout=max(30, min(180, args.timeout_seconds)),
    )


def _credential_begin_with_expiry_recovery(args, state, session):
    environment_id = _credential_runtime_environment()
    request_id = session.credential_begin_request(
        environment_id, args.desktop_id, args.mode
    )
    try:
        return _credential_begin_once(args, state, request_id), request_id
    except SkillError as exc:
        if not (
            exc.code == "UPSTREAM_FAILURE"
            and exc.extra.get("upstream_code") == "CredentialWorkflowExpired"
        ):
            raise
    request_id = session.renew_expired_credential_begin_request(
        environment_id, args.desktop_id, args.mode, request_id
    )
    return _credential_begin_once(args, state, request_id), request_id


def _credential_workflow_readiness(args, state, workflow_id, current):
    health = _credential_tool(
        args,
        state,
        "cua_credential_health",
        {"workflow_id": workflow_id},
        timeout=max(1, min(30, args.timeout_seconds)),
    )
    updated = dict(current)
    updated["device_ready"] = health.get("device_ready") is True
    browser_ready = health.get("browser_ready") is True
    updated["browser_connected"] = browser_ready
    updated["browser_extension_ready"] = browser_ready
    return updated


def cmd_credential_target_capabilities(args, state, session):
    del session
    payload = {"desktop_id": args.desktop_id} if args.desktop_id else {}
    data = _credential_tool(args, state, "cua_credential_capabilities", payload, timeout=30)
    if data.get("adapter_protocol") != CREDENTIAL_TARGET_PROTOCOL:
        raise SkillError("TARGET_AGENT_UNAVAILABLE", "Gateway does not advertise CUA Target Adapter v1.")
    desktop = data.get("desktop") if isinstance(data.get("desktop"), dict) else {}
    emit_target_success("capabilities", {
        "transport": "access_hub_gateway",
        "desktop": {
            "id": desktop.get("id"),
            "name": desktop.get("name"),
            "type": "cloud_desktop",
            "state": desktop.get("state"),
        },
        "features": list(data.get("features") or []),
    })


def cmd_credential_target_begin(args, state, session):
    if args.timeout_seconds < 1:
        raise SkillError("TARGET_AGENT_UNAVAILABLE", "--timeout-seconds must be positive.")
    agent_path = _safe_agent_path(args.agent_path)
    deadline = time.monotonic() + args.timeout_seconds
    process = None
    data, request_id = _credential_begin_with_expiry_recovery(args, state, session)
    workflow_id = str(data.get("workflow_id") or "").strip()
    if not workflow_id:
        raise SkillError("TARGET_AGENT_UNAVAILABLE", "Gateway did not return an opaque Credential workflow.")
    try:
        while data.get("status") == "preparing":
            if time.monotonic() >= deadline:
                raise SkillError("OPERATION_IN_PROGRESS", "Target Agent initialization is still in progress.")
            time.sleep(min(CREDENTIAL_PAIR_POLL_INTERVAL_SEC, deadline - time.monotonic()))
            data = _credential_begin_once(args, state, request_id)

        if data.get("status") in {"pair_relay_required", "pair_pending"} and data.get("device_ready") is not True:
            desktop_name = str(data.get("desktop_name") or "").strip()
            if not desktop_name:
                raise SkillError("TARGET_AGENT_UNAVAILABLE", "Gateway did not return the bound target desktop name.")
            process, events = _relay_process(agent_path, desktop_name)
            ready = _relay_event(events, min(15, max(1, deadline - time.monotonic())))
            relay_public_key = str(ready.get("relay_public_key") or "").strip()
            if ready.get("type") != "pair_relay_ready" or not relay_public_key:
                raise SkillError("TARGET_AGENT_UNAVAILABLE", "Local credential-agent returned invalid relay readiness.")
            base_url = resolve_base_url(args, state)
            begun = cua_auth.authorized_private_call(
                state,
                base_url,
                f"/skill/credential-relay/{urllib.parse.quote(workflow_id, safe='')}/begin",
                {"relay_public_key": relay_public_key},
                timeout=min(60, max(1, int(deadline - time.monotonic()))),
            )
            operation_id = str(begun.get("operation_id") or "").strip()
            envelope = begun.get("pairing_envelope")
            if not operation_id or not isinstance(envelope, dict) or "pairing_code" in begun:
                raise SkillError("TARGET_AGENT_UNAVAILABLE", "Gateway returned an invalid encrypted pair relay response.")
            assert process.stdin is not None
            process.stdin.write(json.dumps(envelope, separators=(",", ":")) + "\n")
            process.stdin.close()
            process.stdin = None
            _finish_local_relay(process, events, deadline)
            process = None
            completed = cua_auth.authorized_private_call(
                state,
                base_url,
                f"/skill/credential-relay/{urllib.parse.quote(workflow_id, safe='')}/complete",
                {"operation_id": operation_id},
                timeout=min(180, max(1, int(deadline - time.monotonic()))),
            )
            _validate_pair_relay_completion(
                completed,
                workflow_id=workflow_id,
                desktop_id=str(data.get("desktop_id") or "").strip(),
            )
            data = completed

        while True:
            device_ready = data.get("device_ready") is True
            browser_connected = data.get("browser_connected") is True
            extension_ready = data.get("browser_extension_ready") is True
            if device_ready and (args.mode == "device" or browser_connected and extension_ready):
                break
            if time.monotonic() >= deadline:
                code = "BROWSER_SETUP_REQUIRED" if device_ready else "OPERATION_IN_PROGRESS"
                raise SkillError(code, "Credential target preparation did not finish within the bounded wait.")
            time.sleep(min(CREDENTIAL_PAIR_POLL_INTERVAL_SEC, deadline - time.monotonic()))
            data = _credential_workflow_readiness(args, state, workflow_id, data)

        device_id = str(data.get("device_id") or "").strip()
        if not device_id:
            raise SkillError("TARGET_AGENT_UNAVAILABLE", "Gateway did not return the exact enrolled Device ID.")
        session.complete_credential_begin(
            _credential_runtime_environment(),
            args.desktop_id,
            args.mode,
            workflow_id,
            device_id,
        )
        emit_target_success("begin", {
            "workflow_id": workflow_id,
            "desktop_id": data.get("desktop_id"),
            "device_id": device_id,
            "device_ready": True,
            "browser_extension_ready": data.get("browser_extension_ready") is True,
            "browser_connected": data.get("browser_connected") is True,
            "expires_at": data.get("expires_at"),
        })
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()


def cmd_credential_target_health(args, state, session):
    del session
    data = _credential_tool(args, state, "cua_credential_health", {"workflow_id": args.workflow_id}, timeout=args.timeout_seconds)
    emit_target_success("health", {
        "healthy": data.get("healthy") is True,
        "device_ready": data.get("device_ready") is True,
        "browser_ready": data.get("browser_ready") is True,
        "warning_count": int(data.get("warning_count") or 0),
        "issue_count": int(data.get("issue_count") or 0),
    })


def cmd_credential_target_authorize_begin(args, state, session):
    data = _credential_tool(args, state, "cua_credential_browser_authorize_begin", {
        "workflow_id": args.workflow_id, "sites": args.site,
    }, timeout=args.timeout_seconds)
    operation_id = str(data.get("operation_id") or "").strip()
    if not operation_id:
        raise SkillError("TARGET_AGENT_UNAVAILABLE", "Gateway did not return an HTTPS capability observation.")
    session.remember_credential_operation(
        _credential_runtime_environment(), operation_id, args.workflow_id
    )
    emit_target_success("browser-authorize-begin", {
        "operation_id": operation_id,
        "status": data.get("status") or "running",
        "sites": list(data.get("sites") or args.site),
    })


def cmd_credential_target_authorize_watch(args, state, session):
    workflow_id = session.workflow_for_credential_operation(
        _credential_runtime_environment(), args.operation_id
    )
    if not workflow_id:
        raise SkillError("WORKFLOW_EXPIRED", "HTTPS capability observation is not bound to an active local workflow.")
    deadline = time.monotonic() + args.timeout_seconds
    while True:
        remaining = max(1, int(deadline - time.monotonic()) + 1)
        data = _credential_tool(args, state, "cua_credential_browser_authorize_watch", {
            "workflow_id": workflow_id, "operation_id": args.operation_id,
        }, timeout=min(30, remaining))
        status = str(data.get("status") or "running").lower()
        if status in {"succeeded", "completed", "authorized"}:
            emit_target_success("browser-authorize-watch", {
                "operation_id": args.operation_id, "status": "succeeded", "authorized": True,
            })
        if status in {"failed", "error", "cancelled", "canceled"}:
            raise SkillError("BROWSER_PERMISSION_REQUIRED", "Chrome is withholding the required HTTPS capability.")
        if time.monotonic() >= deadline:
            raise SkillError("OPERATION_IN_PROGRESS", "HTTPS capability observation is still in progress.")
        time.sleep(min(args.poll_interval_ms / 1000, deadline - time.monotonic()))


def cmd_credential_target_network_ensure(args, state, session):
    del session
    data = _credential_tool(args, state, "cua_credential_browser_network_ensure", {
        "workflow_id": args.workflow_id, "sites": args.site,
    }, timeout=args.timeout_seconds)
    emit_target_success("browser-network-ensure", {
        "status": data.get("status") or "unknown",
        "mode": data.get("mode") or "direct",
        "fallback_configured": data.get("fallback_configured") is True,
        "proxy_applied": data.get("proxy_applied") is True,
    })


def cmd_credential_target_finish(args, state, session):
    data = _credential_tool(args, state, "cua_credential_finish", {"workflow_id": args.workflow_id}, timeout=args.timeout_seconds)
    session.finish_credential_workflow(
        _credential_runtime_environment(), args.workflow_id
    )
    emit_target_success("finish", {
        "workflow_id": args.workflow_id,
        "finished": data.get("finished") is True,
        "already_finished": data.get("already_finished") is True,
    })


def cmd_credential_target_reset(args, state, session):
    environment_id = _credential_runtime_environment()
    request_id = session.credential_reset_request(
        environment_id, args.desktop_id, args.device_id
    )
    data = _credential_tool(args, state, "cua_credential_reset", {
        "desktop_id": args.desktop_id,
        "device_id": args.device_id,
        "request_id": request_id,
    }, timeout=args.timeout_seconds)
    if data.get("pair_ready") is True:
        session.finish_credential_reset(
            environment_id, args.desktop_id, args.device_id
        )
    emit_target_success("reset", {
        "desktop_id": data.get("desktop_id") or args.desktop_id,
        "device_id": data.get("device_id") or args.device_id,
        "pair_ready": data.get("pair_ready") is True,
    })


def _credential_agent_default():
    configured = os.environ.get("AL_CREDENTIAL_AGENT_PATH")
    if configured:
        return Path(configured).expanduser()
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Local" / "AL" / "CredentialAgent" / "credential-agent.exe"
    return Path.home() / ".local" / "bin" / "credential-agent"


def _ensure_credential_agent_installed(args, environment):
    requested = Path(args.agent_path).expanduser() if args.agent_path else _credential_agent_default()
    if not requested.is_absolute():
        raise SkillError("TARGET_AGENT_UNAVAILABLE", "Credential Agent install path must be absolute.")
    try:
        requested.lstat()
    except FileNotFoundError:
        command = [
            sys.executable,
            str(CREDENTIAL_RUNTIME / "scripts" / "bootstrap-agent.py"),
        ]
        if args.agent_path:
            command.extend(["--install-path", str(requested)])
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=min(args.timeout_seconds, 240),
                check=False,
                env=environment,
            )
        except subprocess.TimeoutExpired as exc:
            raise SkillError("UPSTREAM_TIMEOUT", "Signed Credential Agent installation timed out.") from exc
        if completed.returncode:
            raise SkillError("AGENT_INSTALL_FAILED", "Signed Credential Agent installation did not complete.")
        agent = _safe_agent_path(requested)
        return {"agent_path": str(agent), "agent_installed": True}
    except OSError as exc:
        raise SkillError("TARGET_AGENT_UNAVAILABLE", "Credential Agent install path cannot be inspected.") from exc
    agent = _safe_agent_path(requested)
    return {"agent_path": str(agent), "agent_installed": False}


def _credential_subprocess_env(args, profile=None, environment_id=None):
    environment = os.environ.copy()
    if getattr(args, "api_base_url", None):
        environment["AP_CUA_SKILL_API_BASE_URL"] = _validate_base_url(args.api_base_url)
    selected = environment_id or (profile or {}).get("environment_id")
    if selected:
        if selected != "prod":
            raise SkillError("UPSTREAM_PROTOCOL_ERROR", "Credential environment is invalid.")
        environment["CREDENTIAL_AGENT_AUTH_MODE"] = "agentplan_device"
        environment["CREDENTIAL_AGENT_ENVIRONMENT_ID"] = selected
    if profile:
        mapping = {
            "control_url": "CREDENTIAL_AGENT_CONTROL_URL",
            "vault_url": "CREDENTIAL_AGENT_VAULT_URL",
            "policy_authority_id": "CREDENTIAL_AGENT_POLICY_AUTHORITY_ID",
            "policy_signing_key_id": "CREDENTIAL_AGENT_POLICY_SIGNING_KEY_ID",
            "policy_signing_public_key": "CREDENTIAL_AGENT_POLICY_SIGNING_PUBLIC_KEY",
        }
        for key, name in mapping.items():
            value = profile.get(key)
            if not isinstance(value, str) or not value.strip():
                raise SkillError("UPSTREAM_PROTOCOL_ERROR", "Credential bootstrap profile is incomplete.")
            environment[name] = value.strip()
    return environment


def _run_credential_script(command, timeout_seconds, *, environment=None):
    try:
        completed = subprocess.run(
            command,
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise SkillError("UPSTREAM_TIMEOUT", "Credential workflow exceeded its bounded client wait.") from exc
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    result = None
    for line in reversed(lines):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("type") == "result":
            result = value
            break
        if isinstance(value, dict) and "status" in value and result is None:
            result = value
    if completed.returncode or not isinstance(result, dict) or result.get("status") != "succeeded":
        error = result.get("error") if isinstance(result, dict) and isinstance(result.get("error"), dict) else {}
        raise SkillError(
            str(error.get("code") or "UPSTREAM_FAILURE"),
            str(error.get("message") or "Credential workflow did not succeed."),
            job_id=(result.get("details") or {}).get("job_id") if isinstance(result, dict) else None,
        )
    return result


def _run_local_target(args, command, timeout_seconds, *, environment=None):
    invocation = [sys.executable, str(Path(__file__).resolve())]
    if getattr(args, "api_base_url", None):
        invocation.extend(["--api-base-url", args.api_base_url])
    invocation.extend(["credential-target", *command])
    try:
        completed = subprocess.run(
            invocation,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise SkillError("UPSTREAM_TIMEOUT", "Credential target operation exceeded its bounded client wait.") from exc
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    try:
        envelope = json.loads(lines[-1]) if lines else {}
    except json.JSONDecodeError as exc:
        raise SkillError("UPSTREAM_PROTOCOL_ERROR", "Credential target returned invalid structured output.") from exc
    if (
        completed.returncode
        or not isinstance(envelope, dict)
        or envelope.get("adapter_protocol") != CREDENTIAL_TARGET_PROTOCOL
        or envelope.get("ok") is not True
    ):
        error = envelope.get("error") if isinstance(envelope, dict) and isinstance(envelope.get("error"), dict) else {}
        raise SkillError(
            str(error.get("code") or "UPSTREAM_FAILURE"),
            str(error.get("message") or "Credential target operation did not succeed."),
        )
    data = envelope.get("data")
    if not isinstance(data, dict):
        raise SkillError("UPSTREAM_PROTOCOL_ERROR", "Credential target returned an invalid result envelope.")
    return data


def _agent_json(command, *, environment, timeout_seconds):
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise SkillError("UPSTREAM_TIMEOUT", "Credential Agent command timed out.") from exc
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SkillError("UPSTREAM_PROTOCOL_ERROR", "Credential Agent returned invalid structured output.") from exc
    if completed.returncode or not isinstance(payload, dict):
        raise SkillError("TARGET_AGENT_UNAVAILABLE", "Credential Agent command did not complete.")
    return payload


def _validate_bootstrap_profile(payload, expected_environment, expected_proof, expected_operation):
    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    if (
        payload.get("proof_jkt") != expected_proof
        or payload.get("device_role") != "control"
        or payload.get("operation_id") != expected_operation
        or profile.get("auth_mode") != "agentplan_device"
        or profile.get("environment_id") != expected_environment
    ):
        raise SkillError("UPSTREAM_PROTOCOL_ERROR", "Credential bootstrap binding is invalid.")
    for key in ("control_url", "vault_url"):
        value = str(profile.get(key) or "").strip()
        parsed = urllib.parse.urlsplit(value)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            raise SkillError("UPSTREAM_PROTOCOL_ERROR", "Credential bootstrap service origin is invalid.")
    for key in ("policy_authority_id", "policy_signing_key_id"):
        value = str(profile.get(key) or "").strip()
        if len(value) < 8 or len(value) > 128 or not all(character.isalnum() or character in "._:-" for character in value):
            raise SkillError("UPSTREAM_PROTOCOL_ERROR", "Credential bootstrap policy identity is invalid.")
    encoded = str(profile.get("policy_signing_public_key") or "").strip()
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise SkillError("UPSTREAM_PROTOCOL_ERROR", "Credential bootstrap policy key is invalid.") from exc
    if len(decoded) != 32 or base64.b64encode(decoded).decode("ascii") != encoded:
        raise SkillError("UPSTREAM_PROTOCOL_ERROR", "Credential bootstrap policy key is invalid.")
    assertion = str(payload.get("assertion") or "").strip()
    if len(assertion) > 65536 or len(assertion.split(".")) != 3:
        raise SkillError("UPSTREAM_PROTOCOL_ERROR", "Credential bootstrap assertion is invalid.")
    return dict(profile), assertion


def _ensure_source_agent_profile(args, state, agent, target):
    environment_id = target.get("environment_id")
    if environment_id != "prod":
        raise SkillError("TARGET_CAPABILITY_UNAVAILABLE", "Credential environment is unavailable.")
    environment = _credential_subprocess_env(args, environment_id=environment_id)
    bootstrap_info = _agent_json(
        [str(agent), "bootstrap-info", "--environment", environment_id,
         "--control-url", "", "--vault-url", "", "--role", "control", "--output", "json"],
        environment=environment,
        timeout_seconds=30,
    )
    proof = str(bootstrap_info.get("proof_jkt") or "").strip()
    if bootstrap_info.get("environment_id") != environment_id or len(proof) != 43:
        raise SkillError("UPSTREAM_PROTOCOL_ERROR", "Credential Agent bootstrap identity is invalid.")
    operation_id = "cred-bootstrap-" + secrets.token_urlsafe(18)
    idempotency_key = "cred-bootstrap-" + secrets.token_urlsafe(18)
    bootstrap = cua_auth.authorized_credential_bootstrap(
        state,
        resolve_base_url(args, state),
        {"proof_jkt": proof, "operation_id": operation_id, "idempotency_key": idempotency_key},
        timeout=60,
    )
    profile, assertion = _validate_bootstrap_profile(
        bootstrap, environment_id, proof, operation_id
    )
    environment = _credential_subprocess_env(args, profile=profile)
    setup_command = [
        str(agent), "setup", "--role", "personal", "--skip-browser",
        "--auth-mode", "agentplan_device", "--environment", environment_id,
        "--control-url", profile["control_url"], "--vault-url", profile["vault_url"],
        "--policy-authority-id", profile["policy_authority_id"],
        "--policy-signing-key-id", profile["policy_signing_key_id"],
        "--policy-signing-public-key", profile["policy_signing_public_key"],
        "--enrollment-assertion-stdin",
    ]
    try:
        completed = subprocess.run(
            setup_command,
            input=assertion + "\n",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=180,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise SkillError("UPSTREAM_TIMEOUT", "Credential Agent enrollment timed out.") from exc
    finally:
        assertion = None
        bootstrap = None
    if completed.returncode:
        raise SkillError("SOURCE_SETUP_FAILED", "Credential Agent did not complete proof-bound enrollment.")
    capabilities = _agent_json(
        [str(agent), "capabilities", "--output", "json"],
        environment=environment,
        timeout_seconds=30,
    )
    enrollment = capabilities.get("enrollment") if isinstance(capabilities.get("enrollment"), dict) else {}
    if (
        enrollment.get("valid") is not True
        or enrollment.get("environment_id") != environment_id
        or enrollment.get("auth_mode") != "agentplan_device"
    ):
        raise SkillError("SOURCE_ENROLLMENT_REQUIRED", "Credential Agent enrollment is not active for the selected environment.")
    return profile, environment


def cmd_credentials_status(args, state, session):
    del session
    target = _credential_gateway_preflight(args, state)
    agent_path = _credential_agent_default()
    agent = {"installed": False, "path": str(agent_path)}
    try:
        checked = _safe_agent_path(agent_path)
        environment = _credential_subprocess_env(
            args, environment_id=target["environment_id"]
        )
        completed = subprocess.run(
            [str(checked), "capabilities", "--output", "json"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=30,
            check=False,
            env=environment,
        )
        capabilities = json.loads(completed.stdout) if completed.returncode == 0 else {}
        enrollment = capabilities.get("enrollment") if isinstance(capabilities.get("enrollment"), dict) else {}
        browser = capabilities.get("browser") if isinstance(capabilities.get("browser"), dict) else {}
        agent = {
            "installed": True,
            "path": str(checked),
            "enrollment_valid": (
                enrollment.get("valid") is True
                and enrollment.get("auth_mode") == "agentplan_device"
                and enrollment.get("environment_id") == target["environment_id"]
            ),
            "environment_id": target["environment_id"],
            "browser_connected": browser.get("connected") is True,
        }
    except (SkillError, ValueError, subprocess.TimeoutExpired):
        pass
    return {"data": {
        "runtime": {
            "embedded": True,
            "adapter_protocol": CREDENTIAL_TARGET_PROTOCOL,
        },
        "source_agent": agent,
        "target": target,
    }}


def cmd_credentials_setup(args, state, session):
    del session
    target_capabilities = _credential_gateway_preflight(
        args, state, browser=not args.skip_browser
    )
    base_environment = _credential_subprocess_env(
        args, environment_id=target_capabilities["environment_id"]
    )
    installed = _ensure_credential_agent_installed(args, base_environment)
    agent = _safe_agent_path(installed.get("agent_path"))
    _profile, environment = _ensure_source_agent_profile(
        args, state, agent, target_capabilities
    )
    command = [
        sys.executable,
        str(CREDENTIAL_RUNTIME / "scripts" / "prepare-source.py"),
        "--agent-path", str(agent),
        "--timeout-seconds", str(args.timeout_seconds),
    ]
    if args.skip_browser:
        command.append("--skip-browser")
    result = _run_credential_script(command, args.timeout_seconds + 15, environment=environment)
    mode = "device" if args.skip_browser else "browser"
    begin = [
        "begin", "--mode", mode, "--agent-path", str(agent),
        "--timeout-seconds", str(args.timeout_seconds),
    ]
    if args.desktop_id:
        begin.extend(["--desktop-id", args.desktop_id])
    target = _run_local_target(
        args, begin, args.timeout_seconds + 15, environment=environment
    )
    workflow_id = str(target.get("workflow_id") or "").strip()
    if not workflow_id or target.get("device_ready") is not True:
        raise SkillError("UPSTREAM_PROTOCOL_ERROR", "Credential target setup did not return an exact ready workflow.")
    setup_error = None
    try:
        browser_ready = target.get("browser_extension_ready") is True and target.get("browser_connected") is True
        if not args.skip_browser and not browser_ready:
            raise SkillError("BROWSER_SETUP_REQUIRED", "Credential target browser did not become ready.")
    except Exception as exc:
        setup_error = exc
        raise
    finally:
        try:
            _run_local_target(args, [
                "finish", "--workflow-id", workflow_id,
                "--timeout-seconds", str(min(args.timeout_seconds, 60)),
            ], min(args.timeout_seconds, 60) + 10, environment=environment)
        except SkillError:
            if setup_error is None:
                raise
    return {"data": {
        "status": "succeeded",
        "desktop_id": target.get("desktop_id"),
        "device_id": target.get("device_id"),
        "device_ready": target.get("device_ready") is True,
        "browser_ready": browser_ready,
        "agent_installed": installed.get("agent_installed") is True,
        "environment_id": target_capabilities["environment_id"],
        "runtime": {
            "embedded": True,
            "adapter_protocol": CREDENTIAL_TARGET_PROTOCOL,
        },
    }}


def _credential_runtime_and_agent(args, state, *, browser):
    target = _credential_gateway_preflight(args, state, browser=browser)
    base_environment = _credential_subprocess_env(
        args, environment_id=target["environment_id"]
    )
    installed = _ensure_credential_agent_installed(args, base_environment)
    agent = _safe_agent_path(installed.get("agent_path"))
    _profile, environment = _ensure_source_agent_profile(args, state, agent, target)
    command = [
        sys.executable,
        str(CREDENTIAL_RUNTIME / "scripts" / "prepare-source.py"),
        "--agent-path", str(agent),
        "--timeout-seconds", str(args.timeout_seconds),
    ]
    if not browser:
        command.append("--skip-browser")
    prepared = _run_credential_script(
        command, args.timeout_seconds + 15, environment=environment
    )
    return agent, prepared, environment


def cmd_credentials_sync_browser(args, state, session):
    del session
    agent, _prepared, environment = _credential_runtime_and_agent(
        args, state, browser=True
    )
    command = [
        sys.executable,
        str(CREDENTIAL_RUNTIME / "scripts" / "sync-cua.py"),
        "--agent-path", str(agent),
        "--target-adapter", str(Path(__file__).resolve()),
        "--desktop-id", args.desktop_id,
        "--timeout-seconds", str(args.timeout_seconds),
        *args.site,
    ]
    result = _run_credential_script(
        command, args.timeout_seconds + 20, environment=environment
    )
    return {"data": result}


def cmd_credentials_sync_resource(args, state, session):
    del session
    agent, _prepared, environment = _credential_runtime_and_agent(
        args, state, browser=False
    )
    command = [
        sys.executable,
        str(CREDENTIAL_RUNTIME / "scripts" / "sync-cua-resource.py"),
        "--agent-path", str(agent),
        "--target-adapter", str(Path(__file__).resolve()),
        "--desktop-id", args.desktop_id,
        "--timeout-seconds", str(args.timeout_seconds),
        args.resource,
    ]
    if args.resource in {"env", "secret"}:
        command.extend(args.name)
    elif args.resource == "credential-set":
        command.extend(["--type", args.set_type, "--name", args.set_name])
    else:
        command.extend(["--profile", args.profile])
    result = _run_credential_script(
        command, args.timeout_seconds + 20, environment=environment
    )
    return {"data": result}


def cmd_credentials_reset(args, state, session):
    target = _credential_gateway_preflight(args, state, reset=True)
    base_environment = _credential_subprocess_env(
        args, environment_id=target["environment_id"]
    )
    installed = _ensure_credential_agent_installed(args, base_environment)
    agent = _safe_agent_path(installed.get("agent_path"))
    _profile, environment = _ensure_source_agent_profile(args, state, agent, target)
    environment_id = target["environment_id"]
    device_id = str(
        args.device_id
        or session.credential_device(environment_id, args.desktop_id)
        or ""
    ).strip()
    if not device_id:
        raise SkillError("VALIDATION_ERROR", "Pass the exact --device-id because no prior target Device ID is recorded.")
    request_id = session.credential_reset_request(
        environment_id, args.desktop_id, device_id
    )
    if not session.credential_reset_central_revoked(
        environment_id, args.desktop_id, device_id
    ):
        revoked = subprocess.run(
            [str(agent), "device", "revoke", "--yes", "--output", "json", "--reason", "reset isolated CUA credential target", device_id],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=min(args.timeout_seconds, 120),
            check=False,
            env=environment,
        )
        if revoked.returncode:
            raise SkillError("UPSTREAM_FAILURE", "Central Device revocation was not confirmed; target reset was not attempted.")
        try:
            revoked_result = json.loads(revoked.stdout)
        except json.JSONDecodeError as exc:
            raise SkillError("UPSTREAM_PROTOCOL_ERROR", "Central Device revocation returned invalid structured output.") from exc
        revoked_device = revoked_result.get("device") if isinstance(revoked_result.get("device"), dict) else {}
        if revoked_result.get("status") != "revoked" or str(revoked_device.get("id") or "") != device_id:
            raise SkillError("UPSTREAM_FAILURE", "Central Device revocation did not confirm the exact target Device ID.")
        session.mark_credential_reset_central_revoked(
            environment_id, args.desktop_id, device_id
        )
    data = _credential_tool(args, state, "cua_credential_reset", {
        "desktop_id": args.desktop_id, "device_id": device_id, "request_id": request_id,
    }, timeout=args.timeout_seconds)
    if data.get("pair_ready") is not True:
        raise SkillError("UPSTREAM_FAILURE", "Target reset did not reach pair_ready.")
    session.finish_credential_reset(environment_id, args.desktop_id, device_id)
    return {"data": {
        "status": "succeeded",
        "desktop_id": args.desktop_id,
        "device_id": device_id,
        "pair_ready": True,
    }}


# -- helpers ---------------------------------------------------------------


def _has_base_url(args, state):
    return bool(args.api_base_url or os.environ.get("AP_CUA_SKILL_API_BASE_URL")
                or os.environ.get("CUA_SKILL_API_BASE_URL")
                or state.api_base_url or bundled_base_url())


def _resolve_task_id(args, session):
    if getattr(args, "task_id", None):
        return args.task_id
    if getattr(args, "last", False) and session.last_task_id:
        return session.last_task_id
    raise SkillError(
        "VALIDATION_ERROR",
        "task_id is required. Pass --task-id <id> or --last to reuse the most recent task.",
    )


def _resolve_context_id(args, session):
    if getattr(args, "context_id", None):
        return args.context_id
    if getattr(args, "last_context", False) and session.last_context_id:
        return session.last_context_id
    raise SkillError(
        "VALIDATION_ERROR",
        "context_id is required. Pass --context-id <id> or --last-context.",
    )


def _task_result(action, envelope, session):
    """Persist task/context ids from an envelope, then return data + task-flavored next."""
    task_id = envelope.get("invocation_id")
    platform = envelope.get("platform") or {}
    context_id = platform.get("context_id")
    session.set_last(
        last_task_id=task_id,
        last_invocation_id=task_id,
        last_context_id=context_id,
    )
    return {"data": envelope, "next": _next_for_task(envelope)}


def _next_for_task(envelope):
    outcome = envelope.get("outcome")
    task_id = envelope.get("invocation_id")
    command = command_prefix()
    next_action = envelope.get("next_action") or {}
    hint = next_action.get("agent_hint", "")
    if outcome == "in_progress":
        return {
            "command": f"{command} task status --task-id {task_id}",
            "agent_hint": hint or "Keep checking task status until completed, needs_input, failed, or cancelled. "
            f"For a hands-off wait use `{command} task result --task-id {task_id}`. "
            "Do not answer the task from progress.",
        }
    if outcome == "needs_input":
        return {
            "command": f'{command} task answer --task-id {task_id} --answer "<USER_ANSWER>"',
            "agent_hint": hint or "Relay input_request.question to the user verbatim, "
            "then submit their reply with task answer.",
        }
    if outcome == "completed":
        return {"agent_hint": hint or "Use data.result.text as the authoritative final result. "
                "Save any produced files with artifact save."}
    if outcome == "failed":
        return {
            "agent_hint": hint or "CUA could not complete the task. "
            "Explain the failure; retry only if the user asks."
        }
    if outcome == "cancelled":
        return {"agent_hint": hint or "The task was cancelled."}
    return None


def _looks_like_html(mime_type, raw):
    if mime_type and "html" in mime_type.lower():
        return True
    head = raw[:512].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def _content_type(headers):
    value = headers.get("content-type") or headers.get("Content-Type") or ""
    return value.split(";", 1)[0].strip() or None


def _legacy_artifact_envelope(raw, headers):
    content_type = _content_type(headers) or ""
    if "json" not in content_type and not raw.lstrip().startswith(b"{"):
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if isinstance(payload, dict) and payload.get("ok") is True and isinstance(payload.get("data"), dict):
        return payload["data"]
    return None


def _write_artifact(raw, output, mime_type):
    if output:
        path = os.path.abspath(os.path.expanduser(output))
        parent = os.path.dirname(path)
        if os.path.lexists(path):
            raise SkillError("VALIDATION_ERROR", f"Refusing to overwrite existing path: {path}")
        if parent and not os.path.isdir(parent):
            raise SkillError("VALIDATION_ERROR", f"Output directory does not exist: {parent}")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
        return path
    ext = ext_for_mime(mime_type)
    fd, path = tempfile.mkstemp(prefix="cua-artifact-", suffix=ext)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
    return path


def _resolve_invocation_id(args, session):
    if getattr(args, "invocation_id", None):
        return args.invocation_id
    if getattr(args, "last", False) and session.last_invocation_id:
        return session.last_invocation_id
    raise SkillError(
        "VALIDATION_ERROR",
        "invocation_id is required. Pass --invocation-id <id> or --last to reuse the most recent invocation.",
    )


def _call_timeout(wait_ms):
    """HTTP timeout must outlast the server-side wait window.

    When wait_ms is None the server applies its own default wait (up to a minute
    or so), so give a generous floor rather than timing out early.
    """
    if wait_ms is None:
        return 120
    return int(wait_ms / 1000.0) + 30


def _wait_invocation_with_budget(state, base_url, invocation_id, wait_ms, initial_envelope=None):
    """Wait for one invocation using a total client budget and <=60s server calls."""
    if wait_ms is None:
        wait_ms = DEFAULT_WATCH_WAIT_MS
    _validate_wait_ms(wait_ms)
    if not invocation_id:
        raise SkillError("INTERNAL", "CUA gateway response did not include an invocation id.")
    if initial_envelope is not None and initial_envelope.get("outcome") != "in_progress":
        return initial_envelope
    if wait_ms == 0:
        if initial_envelope is not None:
            return initial_envelope
        return cua_auth.authorized_call(
            state, base_url, "GET", f"/v1/invocations/{invocation_id}", retries=IDEMPOTENT_RETRIES
        )

    remaining_ms = wait_ms
    envelope = initial_envelope
    while remaining_ms > 0:
        chunk_ms = min(SERVER_WAIT_CHUNK_MS, remaining_ms)
        envelope = cua_auth.authorized_call(
            state,
            base_url,
            "POST",
            f"/v1/invocations/{invocation_id}/watch",
            body={"wait_ms": chunk_ms},
            timeout=_call_timeout(chunk_ms),
            retries=IDEMPOTENT_RETRIES,
        )
        if envelope.get("outcome") != "in_progress":
            return envelope
        remaining_ms -= chunk_ms
    return envelope


def _validate_wait_ms(wait_ms):
    if wait_ms is not None and wait_ms < 0:
        raise SkillError("VALIDATION_ERROR", "--wait-ms must be >= 0")


def _envelope_result(action, envelope, session):
    invocation_id = envelope.get("invocation_id")
    if invocation_id:
        session.set_last_invocation_id(invocation_id)
    return {"data": envelope, "next": _next_for_envelope(envelope)}


def _next_for_envelope(envelope):
    outcome = envelope.get("outcome")
    invocation_id = envelope.get("invocation_id")
    command = command_prefix()
    next_action = envelope.get("next_action") or {}
    hint = next_action.get("agent_hint", "")
    if outcome == "in_progress":
        return {
            "command": f"{command} watch --invocation-id {invocation_id}",
            "agent_hint": hint or "Keep watching until completed, needs_input, failed, or cancelled. "
            "Each watch returns quickly; just call it again while in_progress. For a hands-off wait, "
            f"use `{command} result --invocation-id {invocation_id}`. Do not answer the task from progress.",
        }
    if outcome == "needs_input":
        return {
            "command": f'{command} answer --invocation-id {invocation_id} --answer "<USER_ANSWER>"',
            "agent_hint": hint or "Relay input_request.question to the user verbatim, "
            "then submit their reply with answer.",
        }
    if outcome == "completed":
        return {"agent_hint": hint or "Use data.result.text as the authoritative final result."}
    if outcome == "failed":
        return {
            "agent_hint": hint or "CUA could not complete the task. "
            "Explain the failure; retry only if the user asks."
        }
    if outcome == "cancelled":
        return {"agent_hint": hint or "The task was cancelled."}
    return None


def _derive_desktop_urls(access_url):
    """Return desktop-only and full CUA App URLs without changing ticket scope."""
    try:
        parts = urllib.parse.urlsplit(access_url)
    except (TypeError, ValueError):
        return None, None
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None, None

    path = parts.path or "/"
    segments = [segment for segment in path.split("/") if segment]
    try:
        desktops_index = segments.index("desktops")
    except ValueError:
        desktops_index = -1
    if desktops_index >= 0 and len(segments) > desktops_index + 1:
        public_prefix = "/" + "/".join(segments[:desktops_index]) if desktops_index else ""
        desktop_id = segments[desktops_index + 1]
        desktop_prefix = f"{public_prefix}/desktops/{desktop_id}"
        scope_kind = segments[desktops_index + 2] if len(segments) > desktops_index + 2 else ""
        if scope_kind == "cua-app":
            return None, access_url
        full_path = desktop_prefix + "/cua-app/"
        return access_url, urllib.parse.urlunsplit(
            (parts.scheme, parts.netloc, full_path, parts.query, parts.fragment)
        )

    if path == "/cua-app" or path.startswith("/cua-app/"):
        full_path = path
        desktop_path = path[len("/cua-app"):] or "/"
    else:
        desktop_path = path
        full_path = "/cua-app" + (path if path.startswith("/") else "/" + path)

    desktop_view_url = urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, desktop_path, parts.query, parts.fragment)
    )
    full_interface_url = urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, full_path, parts.query, parts.fragment)
    )
    return desktop_view_url, full_interface_url


# -- argument parser -------------------------------------------------------


def build_parser():
    parser = JsonArgumentParser(prog="cua.py", description="CUA Skill CLI")
    parser.add_argument("--api-base-url", help="CUA gateway base URL (overrides env and cache).")
    sub = parser.add_subparsers(dest="command")

    auth = sub.add_parser("auth", help="Authentication commands").add_subparsers(dest="auth_command")

    p = auth.add_parser("status", help="Check the current login state.")
    p.set_defaults(handler=cmd_auth_status, action="auth status")

    p = auth.add_parser("login", help="Use arkcli by default or explicitly select the hidden manual prompt.")
    login_mode = p.add_mutually_exclusive_group()
    login_mode.add_argument(
        "--no-prompt", action="store_true", help="Do not prompt; require an arkcli credential."
    )
    login_mode.add_argument(
        "--manual",
        action="store_true",
        help="Bypass arkcli and securely prompt for an API key in this local terminal.",
    )
    p.set_defaults(handler=cmd_auth_login, action="auth login")

    p = auth.add_parser("logout", help="Clear the locally cached AgentPlan API key.")
    p.set_defaults(handler=cmd_auth_logout, action="auth logout")

    p = sub.add_parser("ping", help="Read-only auth and desktop-binding check. Creates no task.")
    p.set_defaults(handler=cmd_ping, action="ping")

    p = sub.add_parser("delegate", help="Delegate the user's original objective to CUA.")
    p.add_argument(
        "--objective", required=True,
        help="The user's original request. Do not pre-plan or add constraints.",
    )
    p.add_argument("--wait-ms", type=int, default=0,
                   help="Total ms to wait before returning. Calls are chunked at 60 seconds. "
                        "Default 0 returns the invocation id immediately. Does not cancel the task.")
    p.set_defaults(handler=cmd_delegate, action="delegate")

    p = sub.add_parser("watch", help="Wait for or check an invocation's next state.")
    _add_invocation_args(p)
    p.add_argument(
        "--wait-ms", type=int, default=DEFAULT_WATCH_WAIT_MS,
        help="Total ms to wait before returning; server calls are chunked at 60 seconds. Does not cancel the task.",
    )
    p.set_defaults(handler=cmd_watch, action="watch")

    p = sub.add_parser("answer", help="Submit the user's answer when outcome is needs_input.")
    _add_invocation_args(p)
    p.add_argument("--answer", required=True, help="The user's answer to input_request.question.")
    p.add_argument(
        "--wait-ms", type=int, default=DEFAULT_WATCH_WAIT_MS,
        help="Total ms to wait before returning; calls are chunked at 60 seconds.",
    )
    p.set_defaults(handler=cmd_answer, action="answer")

    p = sub.add_parser("cancel", help="Request cancellation. Only when the user asks to stop.")
    _add_invocation_args(p)
    p.set_defaults(handler=cmd_cancel, action="cancel")

    p = sub.add_parser("result", help="Wait until terminal and return the authoritative result.")
    _add_invocation_args(p)
    p.add_argument("--timeout", type=int, default=600, help="Total seconds to keep waiting for a terminal outcome.")
    p.set_defaults(handler=cmd_result, action="result")


    p = sub.add_parser("self-test", help="Local-only checks. Creates no CUA task.")
    p.set_defaults(handler=cmd_self_test, action="self-test")

    _add_semantic_parsers(sub)
    _add_credential_parsers(sub)

    return parser


def _add_semantic_parsers(sub):
    """Resource-aware semantic command surface."""

    p = sub.add_parser("diagnose", help="Confirm CUA is reachable and a desktop is bound. Creates no task.")
    p.set_defaults(handler=cmd_diagnose, action="diagnose")

    desktop = sub.add_parser("desktop", help="Cloud-desktop commands.").add_subparsers(dest="desktop_command")
    p = desktop.add_parser("list", help="List selectable cloud desktops.")
    p.set_defaults(handler=cmd_desktop_list, action="desktop list")

    p = desktop.add_parser("access", help="Get a temporary CUA App login URL.")
    p.set_defaults(handler=cmd_desktop_access, action="desktop access")

    p = desktop.add_parser("revoke-access", help="Revoke a temporary CUA App access ticket.")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--ticket", help="Ticket returned by desktop access.")
    group.add_argument("--access-url", help="CUA App URL containing the ticket query parameter.")
    p.set_defaults(handler=cmd_desktop_revoke_access, action="desktop revoke-access")

    p = desktop.add_parser(
        "start",
        help="Ensure a desktop is ready by reusing, starting, recovering, or allocating it.",
    )
    p.add_argument(
        "--desktop",
        help="Exact caller-owned desktop id to recover or start. Omit to let the service select the primary desktop or allocate one.",
    )
    p.add_argument(
        "--idempotency-key",
        required=True,
        help="Stable unique key for this user-requested start; reuse it when retrying the same request.",
    )
    p.set_defaults(handler=cmd_desktop_start, action="desktop start")

    p = desktop.add_parser(
        "shutdown",
        help="Release the desktop to stop billing, revoke access, and stop or delete it.",
    )
    p.add_argument("--desktop", help="Optional exact caller-owned desktop id.")
    p.add_argument(
        "--confirm",
        action="store_true",
        required=True,
        help="Confirm that the user explicitly requested shutdown and understands active tasks stop.",
    )
    p.add_argument(
        "--idempotency-key",
        required=True,
        help="Stable unique key for this user-approved shutdown; reuse it when retrying the same request.",
    )
    p.set_defaults(handler=cmd_desktop_shutdown, action="desktop shutdown")

    p = desktop.add_parser("operation", help="Check a desktop start or shutdown operation.")
    p.add_argument("--operation-id", required=True, help="Operation id returned by desktop start or shutdown.")
    p.set_defaults(handler=cmd_desktop_operation, action="desktop operation")


    model = sub.add_parser("model", help="Read the default CUA model config.").add_subparsers(dest="model_command")
    p = model.add_parser("get", help="Read the bound desktop's default model config.")
    p.set_defaults(handler=cmd_model_get, action="model get")


    # -- task --
    task = sub.add_parser(
        "task", help="Run and manage CUA tasks (semantic delegate)."
    ).add_subparsers(dest="task_command")

    p = task.add_parser("run", help="Start a new CUA task, optionally on a chosen desktop.")
    p.add_argument(
        "--objective", required=True,
        help="The user's original request. Do not pre-plan or add constraints.",
    )
    p.add_argument("--desktop", help="Desktop id or name (from desktop list). Defaults to the bound desktop.")
    p.add_argument("--title", help="Title for the auto-created context.")
    p.add_argument(
        "--wait-ms", type=int, default=0,
        help="Total ms to wait before returning; calls are chunked at 60 seconds. Default 0.",
    )
    p.set_defaults(handler=cmd_task_run, action="task run")

    p = task.add_parser("continue", help="Continue work in an existing context.")
    p.add_argument("--objective", required=True, help="What to do next in this context.")
    p.add_argument("--context-id", help="The context to continue.")
    p.add_argument("--last-context", action="store_true", help="Use the most recent context id.")
    p.add_argument(
        "--wait-ms", type=int, default=0,
        help="Total ms to wait before returning; calls are chunked at 60 seconds. Default 0.",
    )
    p.set_defaults(handler=cmd_task_continue, action="task continue")

    p = task.add_parser("status", help="Check a task's current state.")
    _add_task_args(p)
    p.set_defaults(handler=cmd_task_status, action="task status")

    p = task.add_parser("result", help="Wait until terminal and return the authoritative result.")
    _add_task_args(p)
    p.add_argument("--timeout", type=int, default=600, help="Total seconds to keep waiting for a terminal outcome.")
    p.set_defaults(handler=cmd_task_result, action="task result")

    p = task.add_parser("answer", help="Answer CUA's question when outcome is needs_input.")
    _add_task_args(p)
    p.add_argument("--answer", required=True, help="The user's answer to input_request.question.")
    p.add_argument(
        "--wait-ms", type=int, default=DEFAULT_WATCH_WAIT_MS,
        help="Total ms to wait before returning; calls are chunked at 60 seconds.",
    )
    p.set_defaults(handler=cmd_task_answer, action="task answer")

    p = task.add_parser("cancel", help="Cancel a task. Only when the user asks to stop.")
    _add_task_args(p)
    p.set_defaults(handler=cmd_task_cancel, action="task cancel")

    # -- context --
    context = sub.add_parser("context", help="Manage reusable task contexts.").add_subparsers(dest="context_command")

    p = context.add_parser("list", help="List continuable contexts.")
    p.set_defaults(handler=cmd_context_list, action="context list")

    p = context.add_parser("create", help="Open a long-lived context without running a task yet.")
    p.add_argument("--title", help="Context title.")
    p.add_argument("--desktop", help="Desktop id or name. Defaults to the bound desktop.")
    p.set_defaults(handler=cmd_context_create, action="context create")

    p = context.add_parser("add-note", help="Add background to a context without starting a run.")
    _add_context_args(p)
    p.add_argument("--text", required=True, help="The background/context note to record.")
    p.set_defaults(handler=cmd_context_add_note, action="context add-note")

    p = context.add_parser("show", help="Show a context summary and recent task.")
    _add_context_args(p)
    p.set_defaults(handler=cmd_context_show, action="context show")

    # -- timeline --
    timeline = sub.add_parser(
        "timeline", help="Conversation timeline commands."
    ).add_subparsers(dest="timeline_command")
    p = timeline.add_parser("show", help="Show the full conversation timeline projection for a context.")
    _add_context_args(p)
    p.set_defaults(handler=cmd_timeline_show, action="timeline show")

    # -- artifact --
    artifact = sub.add_parser("artifact", help="List and save task artifacts.").add_subparsers(dest="artifact_command")

    p = artifact.add_parser("list", help="List artifacts produced by a task.")
    _add_task_args(p)
    p.set_defaults(handler=cmd_artifact_list, action="artifact list")

    p = artifact.add_parser("save", help="Download an artifact (file, screenshot, log) to a local path.")
    p.add_argument("--artifact-id", help="The artifact id (from artifact list / result).")
    p.add_argument("--last", action="store_true", help="Use the most recent artifact id.")
    p.add_argument("--task-id", help="Task id that owns the artifact. Defaults to the most recent task.")
    p.add_argument("--output", help="Where to write the file. Defaults to a temp file named by content type.")
    p.set_defaults(handler=cmd_artifact_save, action="artifact save")


def _add_credential_parsers(sub):
    credentials = sub.add_parser(
        "credentials",
        help="Prepare, synchronize, diagnose, or reset credentials for an owned CUA.",
    ).add_subparsers(dest="credentials_command")

    p = credentials.add_parser("status", help="Read embedded Credential runtime, source Agent, and target readiness.")
    p.add_argument("--desktop-id")
    p.set_defaults(action="credentials status", handler=cmd_credentials_status)

    p = credentials.add_parser("setup", help="Prepare the source Agent and exact target without creating a model task.")
    p.add_argument("--desktop-id")
    p.add_argument("--agent-path")
    p.add_argument("--skip-browser", action="store_true")
    p.add_argument("--timeout-seconds", type=int, default=600)
    p.set_defaults(action="credentials setup", handler=cmd_credentials_setup)

    sync = credentials.add_parser("sync", help="Synchronize an explicit browser site or resource.").add_subparsers(
        dest="credentials_sync_command"
    )
    p = sync.add_parser("browser", help="Sync explicitly named signed HTTPS site policies.")
    p.add_argument("--desktop-id", required=True)
    p.add_argument("--agent-path")
    p.add_argument("--timeout-seconds", type=int, default=420)
    p.add_argument("site", nargs="+")
    p.set_defaults(action="credentials sync browser", handler=cmd_credentials_sync_browser)

    for resource in ("env", "secret"):
        p = sync.add_parser(resource, help=f"Sync explicitly named {resource} resources.")
        p.add_argument("--desktop-id", required=True)
        p.add_argument("--agent-path")
        p.add_argument("--timeout-seconds", type=int, default=420)
        p.add_argument("name", nargs="+")
        p.set_defaults(
            action=f"credentials sync {resource}",
            handler=cmd_credentials_sync_resource,
            resource=resource,
        )

    p = sync.add_parser("credential-set", help="Sync one explicitly named Credential Set.")
    p.add_argument("--desktop-id", required=True)
    p.add_argument("--agent-path")
    p.add_argument("--timeout-seconds", type=int, default=420)
    p.add_argument("--type", dest="set_type", required=True)
    p.add_argument("--name", dest="set_name", required=True)
    p.set_defaults(
        action="credentials sync credential-set",
        handler=cmd_credentials_sync_resource,
        resource="credential-set",
    )

    p = sync.add_parser("file", help="Sync one managed-file profile.")
    p.add_argument("--desktop-id", required=True)
    p.add_argument("--agent-path")
    p.add_argument("--timeout-seconds", type=int, default=420)
    p.add_argument("--profile", required=True)
    p.set_defaults(
        action="credentials sync file",
        handler=cmd_credentials_sync_resource,
        resource="file",
    )

    p = credentials.add_parser("reset", help="Revoke the exact Device centrally, then reset its target.")
    p.add_argument("--desktop-id", required=True)
    p.add_argument("--device-id")
    p.add_argument("--agent-path")
    p.add_argument("--timeout-seconds", type=int, default=300)
    p.set_defaults(action="credentials reset", handler=cmd_credentials_reset)

    credential_target = sub.add_parser(
        "credential-target",
        help="Internal CUA Target Adapter v1 surface for embedded Credential orchestration.",
    ).add_subparsers(dest="credential_target_command")

    p = credential_target.add_parser("capabilities")
    p.add_argument("--desktop-id")
    p.set_defaults(action="credential-target capabilities", handler=cmd_credential_target_capabilities)

    p = credential_target.add_parser("begin")
    p.add_argument("--mode", choices=("device", "browser"), required=True)
    p.add_argument("--desktop-id")
    p.add_argument("--agent-path", required=True)
    p.add_argument("--timeout-seconds", type=int, default=240)
    p.set_defaults(action="credential-target begin", handler=cmd_credential_target_begin)

    p = credential_target.add_parser("health")
    p.add_argument("--workflow-id", required=True)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.set_defaults(action="credential-target health", handler=cmd_credential_target_health)

    p = credential_target.add_parser(
        "browser-authorize-begin",
        help="Compatibility-only read-only HTTPS capability observation.",
    )
    p.add_argument("--workflow-id", required=True)
    p.add_argument("site", nargs="+")
    p.add_argument("--timeout-seconds", type=int, default=30)
    p.set_defaults(action="credential-target browser-authorize-begin", handler=cmd_credential_target_authorize_begin)

    p = credential_target.add_parser(
        "browser-authorize-watch",
        help="Watch a compatibility HTTPS capability observation without mutation.",
    )
    p.add_argument("--operation-id", required=True)
    p.add_argument("--timeout-seconds", type=int, default=180)
    p.add_argument("--poll-interval-ms", type=int, default=500)
    p.set_defaults(action="credential-target browser-authorize-watch", handler=cmd_credential_target_authorize_watch)

    p = credential_target.add_parser("browser-network-ensure")
    p.add_argument("--workflow-id", required=True)
    p.add_argument("site", nargs="+")
    p.add_argument("--timeout-seconds", type=int, default=90)
    p.set_defaults(action="credential-target browser-network-ensure", handler=cmd_credential_target_network_ensure)

    p = credential_target.add_parser("finish")
    p.add_argument("--workflow-id", required=True)
    p.add_argument("--timeout-seconds", type=int, default=30)
    p.set_defaults(action="credential-target finish", handler=cmd_credential_target_finish)

    p = credential_target.add_parser("reset")
    p.add_argument("--desktop-id", required=True)
    p.add_argument("--device-id", required=True)
    p.add_argument("--timeout-seconds", type=int, default=240)
    p.set_defaults(action="credential-target reset", handler=cmd_credential_target_reset)


def _add_task_args(p):
    p.add_argument("--task-id", help="The task id (same id space as invocation_id).")
    p.add_argument("--last", action="store_true", help="Use the most recent task id from local session cache.")


def _add_context_args(p):
    p.add_argument("--context-id", help="The context id.")
    p.add_argument("--last-context", action="store_true", help="Use the most recent context id.")


def _add_invocation_args(p):
    p.add_argument("--invocation-id", help="The invocation id returned by delegate.")
    p.add_argument("--last", action="store_true", help="Use the most recent invocation id from local session cache.")


if __name__ == "__main__":
    sys.exit(main())
