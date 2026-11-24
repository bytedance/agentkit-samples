# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""VeADK tool functions that drive an AgentKit Sandbox session with EFS."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

from agentkit_client import AgentKitHttpError, AgentKitToolsHttpClient


DEFAULT_TTL_SECONDS = 8 * 60 * 60
DEFAULT_WAIT_TIMEOUT_SECONDS = 10 * 60
DEFAULT_POLL_INTERVAL_SECONDS = 5
DEFAULT_MOUNT_PATH = "/mnt/efs/"
READY_STATUSES = {"ready", "running", "available", "active", "succeeded", "success"}
FAILED_STATUSES = {"failed", "error", "deleted", "terminated"}
COMMAND_OUTPUT_FIELDS = ("Output", "Stdout", "Stderr", "stdout", "stderr", "Result")
SHARED_READER_SCRIPT = """#!/usr/bin/env python3
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

workspace = Path(__file__).resolve().parent
expected_sha256 = sys.argv[1] if len(sys.argv) > 1 else ""
task_file = workspace / "task.txt"
report_file = workspace / "report.md"
metadata_file = workspace / "metadata.json"

if not task_file.is_file():
    raise SystemExit("task file is missing: " + str(task_file))
if not report_file.is_file():
    raise SystemExit("report file is missing: " + str(report_file))
if not metadata_file.is_file():
    raise SystemExit("metadata file is missing: " + str(metadata_file))

task = task_file.read_text(encoding="utf-8").rstrip("\\n")
metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
actual_sha256 = metadata.get("task_sha256") or hashlib.sha256(
    task.encode("utf-8")
).hexdigest()
if expected_sha256 and actual_sha256 != expected_sha256:
    raise SystemExit(
        "task hash mismatch: " + actual_sha256 + " != " + expected_sha256
    )

verified_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
print(
    "EFS_SHARED_RUN_RESULT="
    + json.dumps(
        dict(
            workspace=str(workspace),
            task_file=str(task_file),
            report_file=str(report_file),
            metadata_file=str(metadata_file),
            executed_file=str(Path(__file__).resolve()),
            task_sha256=actual_sha256,
            verified_at=verified_at,
            report_preview=report_file.read_text(encoding="utf-8")[:400],
        ),
        ensure_ascii=False,
    )
)
"""


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def _positive_int_env(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be greater than zero")
    return value


def _bool_env(name: str, default: bool = False) -> bool:
    raw = _env(name).lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean-like value")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_mount_path(path: str) -> str:
    value = path.strip() or DEFAULT_MOUNT_PATH
    if not value.startswith("/"):
        raise RuntimeError("EFS local mount path must be an absolute path")
    normalized = str(PurePosixPath(value))
    if normalized in {"/", "/tmp", "/opt/bytefaas", "/opt/tiger/bytefaas/binary"}:
        raise RuntimeError(f"EFS local mount path is not allowed: {normalized}")
    return normalized.rstrip("/") + "/"


def _safe_workspace_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-")[:96] or "workspace"


def _preview(value: str, limit: int = 2000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"... <truncated {len(value) - limit} chars>"


def _command_output_text(result: dict[str, Any]) -> str:
    parts: list[str] = []
    for field in COMMAND_OUTPUT_FIELDS:
        value = result.get(field)
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            text = json.dumps(value, ensure_ascii=False)
        else:
            text = str(value)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _status(value: dict[str, Any]) -> str:
    raw = value.get("Status")
    return raw.strip().lower() if isinstance(raw, str) else ""


def _wait_until(
    description: str,
    fetch,
    done,
    failed,
) -> dict[str, Any]:
    timeout = _positive_int_env(
        "AGENTKIT_WAIT_TIMEOUT_SECONDS", DEFAULT_WAIT_TIMEOUT_SECONDS
    )
    interval = _positive_int_env(
        "AGENTKIT_POLL_INTERVAL_SECONDS", DEFAULT_POLL_INTERVAL_SECONDS
    )
    deadline = time.monotonic() + timeout
    while True:
        value = fetch()
        if done(value):
            return value
        if failed(value):
            raise RuntimeError(f"{description} entered a failure state: {value}")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"timed out after {timeout}s waiting for {description}")
        time.sleep(interval)


def _wait_for_session(
    client: AgentKitToolsHttpClient,
    tool_id: str,
    session_id: str,
) -> dict[str, Any]:
    return _wait_until(
        f"session {session_id} to become ready",
        lambda: client.get_session({"ToolId": tool_id, "SessionId": session_id}),
        lambda value: _status(value) in READY_STATUSES,
        lambda value: _status(value) in FAILED_STATUSES,
    )


def build_create_session_body(
    *,
    tool_id: str,
    filespace_name: str,
    mount_path: str,
    ttl_seconds: int,
    user_session_id: str,
    read_only: bool = False,
) -> dict[str, Any]:
    """Build the CreateSession body that enables EFS in the sandbox."""
    filespace_name = filespace_name.strip()
    if not filespace_name:
        raise RuntimeError(
            "EFS filespace name is required; set AGENTKIT_EFS_FILESPACE_NAME"
        )
    if read_only:
        raise RuntimeError(
            "this demo writes files, so AGENTKIT_EFS_READ_ONLY must be false"
        )
    return {
        "ToolId": tool_id,
        "Ttl": ttl_seconds,
        "TtlUnit": "second",
        "UserSessionId": user_session_id,
        "EfsMountConfigs": [
            {
                "FilespaceName": filespace_name,
                "LocalMountPath": _normalize_mount_path(mount_path),
                "ReadOnly": False,
            }
        ],
    }


def _extract_marker_json(
    output: str,
    marker: str,
    *,
    source: str = "command output",
) -> dict[str, Any]:
    marker_value = _try_extract_marker_json(output, marker)
    if marker_value is not None:
        return marker_value
    raise RuntimeError(
        f"{source} did not contain marker {marker}; output preview={_preview(output)!r}"
    )


def _try_extract_marker_json(output: str, marker: str) -> dict[str, Any] | None:
    prefix = marker + "="
    for line in reversed(output.splitlines()):
        marker_index = line.find(prefix)
        if marker_index >= 0:
            return json.loads(line[marker_index + len(prefix) :].strip())
    return None


def _workspace_command(task: str, workspace_path: str) -> str:
    task_b64 = base64.b64encode(task.encode("utf-8")).decode("ascii")
    workspace_b64 = base64.b64encode(workspace_path.encode("utf-8")).decode("ascii")
    reader_b64 = base64.b64encode(SHARED_READER_SCRIPT.encode("utf-8")).decode("ascii")
    return f"""python3 - <<'PY'
import base64
import datetime as _dt
import hashlib
import json
from pathlib import Path

task = base64.b64decode("{task_b64}").decode("utf-8")
workspace = Path(base64.b64decode("{workspace_b64}").decode("utf-8"))
reader_source = base64.b64decode("{reader_b64}").decode("utf-8")
workspace.mkdir(parents=True, exist_ok=True)

task_file = workspace / "task.txt"
report_file = workspace / "report.md"
metadata_file = workspace / "metadata.json"
log_file = workspace / "activity.log"
reader_file = workspace / "read_workspace.py"

task_file.write_text(task + "\\n", encoding="utf-8")
word_count = len(task.split())
char_count = len(task)
task_sha256 = hashlib.sha256(task.encode("utf-8")).hexdigest()
created_at = _dt.datetime.now(_dt.timezone.utc).isoformat()

report = f'''# EFS Code Workspace Report

## Task

{{task}}

## Generated Artifact

- workspace: {{workspace}}
- characters: {{char_count}}
- words: {{word_count}}
- task_sha256: {{task_sha256}}
- created_at: {{created_at}}

## Why this file matters

This report is written inside the EFS mount by one sandbox session. The demo then
creates another sandbox session with the same FilespaceName and executes
read_workspace.py from this directory to prove the workspace is shared at the
filespace level.
'''
report_file.write_text(report, encoding="utf-8")
reader_file.write_text(reader_source, encoding="utf-8")
metadata = {{
    "workspace": str(workspace),
    "task_file": str(task_file),
    "report_file": str(report_file),
    "metadata_file": str(metadata_file),
    "reader_file": str(reader_file),
    "task_sha256": task_sha256,
    "created_at": created_at,
}}
metadata_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
with log_file.open("a", encoding="utf-8") as fp:
    fp.write(f"{{created_at}} created report for task {{task_sha256}}\\n")

print("EFS_DEMO_RESULT=" + json.dumps({{
    "workspace": str(workspace),
    "report_file": str(report_file),
    "metadata_file": str(metadata_file),
    "reader_file": str(reader_file),
    "task_sha256": task_sha256,
}}, ensure_ascii=False))
PY"""


def _reader_command(workspace_path: str, expected_sha256: str) -> str:
    workspace_b64 = base64.b64encode(workspace_path.encode("utf-8")).decode("ascii")
    sha_b64 = base64.b64encode(expected_sha256.encode("utf-8")).decode("ascii")
    return f"""python3 - <<'PY'
import base64
import subprocess
import sys
from pathlib import Path

workspace = Path(base64.b64decode("{workspace_b64}").decode("utf-8"))
expected_sha256 = base64.b64decode("{sha_b64}").decode("utf-8")
reader_file = workspace / "read_workspace.py"

if not workspace.is_dir():
    raise SystemExit("shared workspace is missing: " + str(workspace))
if not reader_file.is_file():
    raise SystemExit("shared reader script is missing: " + str(reader_file))

completed = subprocess.run(
    [sys.executable, str(reader_file), expected_sha256],
    check=False,
    capture_output=True,
    text=True,
)
if completed.stdout:
    print(completed.stdout, end="")
if completed.stderr:
    print(completed.stderr, end="", file=sys.stderr)
if completed.returncode != 0:
    raise SystemExit(completed.returncode)
PY"""


def _isolation_command(workspace_path: str) -> str:
    workspace_b64 = base64.b64encode(workspace_path.encode("utf-8")).decode("ascii")
    return f"""python3 - <<'PY'
import base64
import json
from pathlib import Path

workspace = Path(base64.b64decode("{workspace_b64}").decode("utf-8"))
paths = [
    workspace,
    workspace / "task.txt",
    workspace / "report.md",
    workspace / "metadata.json",
    workspace / "read_workspace.py",
]
visible = [str(path) for path in paths if path.exists()]
if visible:
    raise SystemExit(
        "filespace isolation failed; unexpected paths are visible: "
        + json.dumps(visible, ensure_ascii=False)
    )

print("EFS_ISOLATION_RESULT=" + json.dumps(dict(
    workspace=str(workspace),
    visible_paths=visible,
    isolated=True,
), ensure_ascii=False))
PY"""


def _run_async_command(
    client: AgentKitToolsHttpClient,
    *,
    tool_id: str,
    session_id: str,
    command: str,
) -> dict[str, Any]:
    response = client.async_exec_command(
        {"ToolId": tool_id, "SessionId": session_id, "Command": command}
    )
    task_id = str(response.get("TaskId") or "").strip()
    if not task_id:
        raise RuntimeError("AsyncExecCommand response is missing TaskId")

    timeout = _positive_int_env("AGENTKIT_ASYNC_WAIT_TIMEOUT_SECONDS", 600)
    interval = _positive_int_env("AGENTKIT_ASYNC_POLL_INTERVAL_SECONDS", 2)
    deadline = time.monotonic() + timeout
    while True:
        result = client.view_async_command(
            {"ToolId": tool_id, "SessionId": session_id, "TaskId": task_id}
        )
        status = str(result.get("Status") or "").strip().lower()
        if status != "running":
            if (
                status in {"succeeded", "completed"}
                and type(result.get("ExitCode")) is int
                and result["ExitCode"] == 0
            ):
                result["TaskId"] = task_id
                return result
            raise RuntimeError(
                "async command did not succeed: "
                f"TaskId={task_id!r}, Status={result.get('Status')!r}, "
                f"ExitCode={result.get('ExitCode')!r}, "
                f"OutputPreview={_preview(_command_output_text(result))!r}"
            )
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"timed out after {timeout}s waiting for async task {task_id}"
            )
        time.sleep(interval)


def _create_ready_session(
    client: AgentKitToolsHttpClient,
    create_body: dict[str, Any],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    tool_id = str(create_body["ToolId"])
    response = client.create_session(create_body)
    session_id = str(response.get("SessionId") or "").strip()
    if not session_id:
        raise RuntimeError("CreateSession response is missing SessionId")
    ready_session = _wait_for_session(client, tool_id, session_id)
    return session_id, response, ready_session


def _cleanup_sessions(
    client: AgentKitToolsHttpClient,
    *,
    tool_id: str,
    session_ids: list[str],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for session_id in session_ids:
        try:
            results.append(
                {
                    "session_id": session_id,
                    "response": client.delete_session(
                        {"ToolId": tool_id, "SessionId": session_id}
                    ),
                }
            )
        except Exception as exc:  # noqa: BLE001 - cleanup should not mask demo result.
            results.append(
                {
                    "session_id": session_id,
                    "error": str(exc),
                    "type": exc.__class__.__name__,
                }
            )
    return results


def _make_user_session_id(run_id: str, role: str) -> str:
    suffix = "-" + role
    safe_run_id = _safe_workspace_name(run_id)
    return safe_run_id[: max(1, 96 - len(suffix))] + suffix


def run_efs_workspace_demo(
    task: str,
    filespace_name: str = "",
    isolation_filespace_name: str = "",
    cleanup: bool = True,
) -> dict[str, Any]:
    """Use two EFS-mounted sandboxes to verify filespace-level sharing.

    Args:
        task: The coding task or artifact description to save into the EFS workspace.
        filespace_name: Optional EFS Filespace name. If empty, the tool reads
            AGENTKIT_EFS_FILESPACE_NAME.
        isolation_filespace_name: Optional second Filespace name used for a
            negative isolation check. If empty, the tool reads
            AGENTKIT_EFS_ISOLATION_FILESPACE_NAME. When still empty, the
            isolation check is skipped.
        cleanup: Whether to delete the sandbox session after verification. Keep
            this true for demos unless you need to inspect the live session.

    Returns:
        A dictionary containing writer and reader session IDs, EFS workspace path,
        generated files, same-filespace verification result, optional isolation
        check result, and cleanup status. On failure, returns {"ok": False, ...}.
    """
    client: AgentKitToolsHttpClient | None = None
    tool_id = ""
    cleanup_session_ids: list[str] = []
    try:
        if not task.strip():
            return {"ok": False, "error": "task must not be empty"}

        tool_id = _env("AGENTKIT_TOOL_ID") or _env("AGENTKIT_SANDBOX_TOOL_ID")
        if not tool_id:
            return {
                "ok": False,
                "error": "set AGENTKIT_TOOL_ID to the AgentKit sandbox tool ID",
            }

        filespace = (filespace_name or _env("AGENTKIT_EFS_FILESPACE_NAME")).strip()
        isolation_filespace = (
            isolation_filespace_name or _env("AGENTKIT_EFS_ISOLATION_FILESPACE_NAME")
        ).strip()
        if isolation_filespace and isolation_filespace == filespace:
            return {
                "ok": False,
                "error": (
                    "isolation_filespace_name must be different from filespace_name"
                ),
            }

        mount_path = _normalize_mount_path(
            _env("AGENTKIT_EFS_LOCAL_MOUNT_PATH") or DEFAULT_MOUNT_PATH
        )
        read_only = _bool_env("AGENTKIT_EFS_READ_ONLY", False)
        ttl = _positive_int_env("AGENTKIT_SESSION_TTL_SECONDS", DEFAULT_TTL_SECONDS)
        run_id = _env("AGENTKIT_EFS_DEMO_RUN_ID") or _env(
            "AGENTKIT_EFS_DEMO_USER_SESSION_ID"
        )
        if not run_id:
            run_id = f"efs-code-agent-{uuid.uuid4().hex[:12]}"
        workspace = f"{mount_path}agentkit-code-agent/{_safe_workspace_name(run_id)}"

        writer_user_session_id = _make_user_session_id(run_id, "writer")
        reader_user_session_id = _make_user_session_id(run_id, "reader")

        client = AgentKitToolsHttpClient()
        writer_create_body = build_create_session_body(
            tool_id=tool_id,
            filespace_name=filespace,
            mount_path=mount_path,
            ttl_seconds=ttl,
            user_session_id=writer_user_session_id,
            read_only=read_only,
        )
        writer_session_id, writer_create_response, writer_ready_session = (
            _create_ready_session(client, writer_create_body)
        )
        cleanup_session_ids.append(writer_session_id)
        create_output = _run_async_command(
            client,
            tool_id=tool_id,
            session_id=writer_session_id,
            command=_workspace_command(task, workspace),
        )
        create_output_text = _command_output_text(create_output)
        created_artifact = _try_extract_marker_json(
            create_output_text, "EFS_DEMO_RESULT"
        )
        if created_artifact is None:
            task_sha256 = hashlib.sha256(task.encode("utf-8")).hexdigest()
            created_artifact = {
                "workspace": workspace,
                "report_file": f"{workspace}/report.md",
                "metadata_file": f"{workspace}/metadata.json",
                "reader_file": f"{workspace}/read_workspace.py",
                "task_sha256": task_sha256,
                "verified_by_exit_code": True,
                "marker_missing": True,
                "task_id": create_output.get("TaskId"),
                "output_preview": _preview(create_output_text),
            }

        reader_create_body = build_create_session_body(
            tool_id=tool_id,
            filespace_name=filespace,
            mount_path=mount_path,
            ttl_seconds=ttl,
            user_session_id=reader_user_session_id,
            read_only=read_only,
        )
        reader_session_id, reader_create_response, reader_ready_session = (
            _create_ready_session(client, reader_create_body)
        )
        cleanup_session_ids.append(reader_session_id)

        verify_output = _run_async_command(
            client,
            tool_id=tool_id,
            session_id=reader_session_id,
            command=_reader_command(workspace, created_artifact["task_sha256"]),
        )
        verify_output_text = _command_output_text(verify_output)
        verification = _try_extract_marker_json(
            verify_output_text, "EFS_SHARED_RUN_RESULT"
        )
        if verification is None:
            verification = {
                "workspace": workspace,
                "executed_file": created_artifact["reader_file"],
                "task_sha256": created_artifact["task_sha256"],
                "verified_by_exit_code": True,
                "marker_missing": True,
                "task_id": verify_output.get("TaskId"),
                "output_preview": _preview(verify_output_text),
            }

        isolation_check: dict[str, Any]
        isolation_session_id = ""
        isolation_create_response: dict[str, Any] | None = None
        isolation_ready_session: dict[str, Any] | None = None
        if isolation_filespace:
            isolation_user_session_id = _make_user_session_id(run_id, "isolation")
            isolation_create_body = build_create_session_body(
                tool_id=tool_id,
                filespace_name=isolation_filespace,
                mount_path=mount_path,
                ttl_seconds=ttl,
                user_session_id=isolation_user_session_id,
                read_only=read_only,
            )
            (
                isolation_session_id,
                isolation_create_response,
                isolation_ready_session,
            ) = _create_ready_session(client, isolation_create_body)
            cleanup_session_ids.append(isolation_session_id)
            isolation_output = _run_async_command(
                client,
                tool_id=tool_id,
                session_id=isolation_session_id,
                command=_isolation_command(workspace),
            )
            isolation_output_text = _command_output_text(isolation_output)
            isolation_check = _try_extract_marker_json(
                isolation_output_text, "EFS_ISOLATION_RESULT"
            )
            if isolation_check is None:
                isolation_check = {
                    "workspace": workspace,
                    "isolated": True,
                    "verified_by_exit_code": True,
                    "marker_missing": True,
                    "task_id": isolation_output.get("TaskId"),
                    "output_preview": _preview(isolation_output_text),
                }
            isolation_check["filespace_name"] = isolation_filespace
        else:
            isolation_check = {
                "skipped": True,
                "reason": (
                    "set AGENTKIT_EFS_ISOLATION_FILESPACE_NAME or pass "
                    "isolation_filespace_name to verify negative isolation"
                ),
            }

        delete_responses: list[dict[str, Any]] = []
        if cleanup:
            delete_responses = _cleanup_sessions(
                client,
                tool_id=tool_id,
                session_ids=cleanup_session_ids,
            )

        return {
            "ok": True,
            "created_at": _utc_now(),
            "tool_id": tool_id,
            "run_id": run_id,
            "workspace": workspace,
            "filespace_name": filespace,
            "efs_mount_config": writer_create_body["EfsMountConfigs"][0],
            "writer_session": {
                "session_id": writer_session_id,
                "user_session_id": writer_user_session_id,
                "create_response": writer_create_response,
                "ready_status": writer_ready_session.get("Status"),
            },
            "reader_session": {
                "session_id": reader_session_id,
                "user_session_id": reader_user_session_id,
                "create_response": reader_create_response,
                "ready_status": reader_ready_session.get("Status"),
            },
            "isolation_session": (
                {
                    "session_id": isolation_session_id,
                    "create_response": isolation_create_response,
                    "ready_status": isolation_ready_session.get("Status")
                    if isolation_ready_session
                    else None,
                }
                if isolation_session_id
                else None
            ),
            "created_artifact": created_artifact,
            "verification": verification,
            "isolation_check": isolation_check,
            "async_tasks": {
                "writer": create_output.get("TaskId"),
                "reader": verify_output.get("TaskId"),
                "isolation": isolation_output.get("TaskId")
                if isolation_filespace
                else None,
            },
            "cleanup": cleanup,
            "delete_responses": delete_responses,
        }
    except AgentKitHttpError as exc:
        cleanup_errors = []
        if cleanup and client and tool_id and cleanup_session_ids:
            cleanup_errors = _cleanup_sessions(
                client,
                tool_id=tool_id,
                session_ids=cleanup_session_ids,
            )
        return {
            "ok": False,
            "error": str(exc),
            "action": exc.action,
            "code": exc.code,
            "message": exc.message,
            "request_id": exc.request_id,
            "cleanup": cleanup,
            "delete_responses": cleanup_errors,
        }
    except Exception as exc:
        cleanup_errors = []
        if cleanup and client and tool_id and cleanup_session_ids:
            cleanup_errors = _cleanup_sessions(
                client,
                tool_id=tool_id,
                session_ids=cleanup_session_ids,
            )
        return {
            "ok": False,
            "error": str(exc),
            "type": exc.__class__.__name__,
            "cleanup": cleanup,
            "delete_responses": cleanup_errors,
        }
