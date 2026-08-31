#!/usr/bin/env python3
"""Run one exact-site Credential sync through an explicit CUA Target Adapter v1."""

from __future__ import annotations

import argparse
import json
import os
import queue
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path


class WorkflowError(RuntimeError):
    def __init__(self, code: str, message: str, **details):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def emit(value: dict) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def safe_executable(value: str, label: str, *, python_script: bool = False) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise WorkflowError("PATH_INVALID", f"{label} must be an absolute path.")
    try:
        info = path.lstat()
    except OSError as exc:
        raise WorkflowError("PATH_INVALID", f"{label} does not exist.") from exc
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or (os.name != "nt" and info.st_mode & 0o022)
    ):
        raise WorkflowError("PATH_UNSAFE", f"{label} must be a non-symlink regular file not writable by group or others.")
    if not python_script and os.name != "nt" and not os.access(path, os.X_OK):
        raise WorkflowError("PATH_UNSAFE", f"{label} must be executable.")
    return path


def site_names(values: list[str]) -> list[str]:
    result = list(dict.fromkeys(value.strip() for value in values if value.strip()))
    if not result or len(result) > 32:
        raise WorkflowError("SITE_INVALID", "Pass between one and 32 exact site ids.")
    for site in result:
        if len(site) > 80 or not site[0].isalnum() or not all(char.isalnum() or char in "._-" for char in site):
            raise WorkflowError("SITE_INVALID", "Every site id must use only letters, numbers, dot, underscore, or hyphen.")
    return result


def parse_result(stdout: str, code: str) -> dict:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise WorkflowError(code, "Command returned no machine-readable result.")
    try:
        value = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise WorkflowError(code, "Command returned invalid machine-readable output.") from exc
    if not isinstance(value, dict):
        raise WorkflowError(code, "Command returned a non-object result.")
    return value


def run_json(command: list[str], timeout_seconds: int, code: str) -> dict:
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise WorkflowError(code, "Command timed out.") from exc
    value = parse_result(completed.stdout, code)
    if completed.returncode != 0 or value.get("ok") is False:
        error = value.get("error") if isinstance(value.get("error"), dict) else {}
        raise WorkflowError(
            str(error.get("code") or code),
            str(error.get("message") or "Command failed."),
            upstream_code=error.get("upstream_code"),
        )
    return value


def adapter_command(target_adapter: Path, *arguments: str) -> list[str]:
    return [sys.executable, str(target_adapter), "credential-target", *arguments]


def run_adapter_json(command: list[str], timeout_seconds: int, code: str) -> dict:
    value = run_json(command, timeout_seconds, code)
    if value.get("schema_version") != 1 or value.get("adapter_protocol") != "cua-target/v1":
        raise WorkflowError("TARGET_ADAPTER_INVALID", "Target adapter returned an unsupported protocol envelope.")
    if value.get("ok") is not True or not isinstance(value.get("data"), dict):
        raise WorkflowError("TARGET_ADAPTER_INVALID", "Target adapter returned an invalid success envelope.")
    return value


def start_jsonl(command: list[str]) -> tuple[subprocess.Popen, queue.Queue]:
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    events: queue.Queue = queue.Queue()

    def read_output() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            events.put(line)
        events.put(None)

    threading.Thread(target=read_output, daemon=True).start()
    return process, events


def read_event(events: queue.Queue, deadline: float) -> dict | None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise WorkflowError("SYNC_TIMEOUT", "Timed out waiting for source Agent output.")
    try:
        line = events.get(timeout=remaining)
    except queue.Empty as exc:
        raise WorkflowError("SYNC_TIMEOUT", "Timed out waiting for source Agent output.") from exc
    if line is None:
        return None
    try:
        event = json.loads(line)
    except json.JSONDecodeError as exc:
        raise WorkflowError("SOURCE_OUTPUT_INVALID", "Source Agent returned invalid JSONL output.") from exc
    if not isinstance(event, dict):
        raise WorkflowError("SOURCE_OUTPUT_INVALID", "Source Agent returned a non-object event.")
    emit({"schema_version": 1, "type": "source_event", "event": event})
    return event


def wait_jsonl_result(
    process: subprocess.Popen,
    events: queue.Queue,
    deadline: float,
    *,
    allow_failure_result: bool = False,
) -> dict:
    result = None
    while True:
        event = read_event(events, deadline)
        if event is None:
            break
        if event.get("type") == "result":
            result = event
    remaining = max(0.1, deadline - time.monotonic())
    try:
        return_code = process.wait(timeout=remaining)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        raise WorkflowError("SYNC_TIMEOUT", "Source Agent did not exit after its final output.") from exc
    if not result or return_code != 0 and not allow_failure_result:
        raise WorkflowError("SOURCE_SYNC_FAILED", "Source Agent sync failed before a final result.")
    return result


def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.kill()
    process.wait()


def raise_source_result_without_job(result: dict) -> None:
    status = str(result.get("status") or "failed").strip()
    error = result.get("error") if isinstance(result.get("error"), dict) else {}
    code = str(error.get("code") or "").strip()
    if (
        status == "failed"
        and code
        and len(code) <= 80
        and all(char.isupper() or char.isdigit() or char == "_" for char in code)
    ):
        raise WorkflowError(
            code,
            "Source Agent stopped before creating an authoritative Sync Job.",
            source_status=status,
        )
    if status == "failed":
        raise WorkflowError(
            "SOURCE_SYNC_FAILED",
            "Source Agent stopped before creating an authoritative Sync Job.",
            source_status=status,
        )
    raise WorkflowError(
        "SYNC_JOB_MISSING",
        "Source Agent reported completion without an authoritative Sync Job.",
        source_status=status,
    )


def wait_authoritative_job(agent: Path, job_id: str, deadline: float) -> dict:
    remaining = deadline - time.monotonic()
    if remaining <= 3:
        raise WorkflowError("SYNC_TIMEOUT", "No observation window remains for the authoritative Sync Job.", job_id=job_id)
    # Finish the Agent's bounded wait before the adapter deadline so its
    # pending_target result is preserved instead of becoming a subprocess
    # timeout with ambiguous remote state.
    observation_seconds = max(1, int(remaining) - 2)
    waiter = None
    try:
        waiter, waiter_events = start_jsonl([
            str(agent), "job", "wait", job_id,
            "--timeout", f"{observation_seconds}s", "--output", "jsonl",
        ])
        return wait_jsonl_result(waiter, waiter_events, deadline, allow_failure_result=True)
    finally:
        stop_process(waiter)


def target_health(target_adapter: Path, workflow_id: str) -> dict:
    try:
        response = run_adapter_json(
            adapter_command(target_adapter, "health", "--workflow-id", workflow_id),
            30,
            "TARGET_HEALTH_UNAVAILABLE",
        )
    except WorkflowError as exc:
        return {"available": False, "error_code": exc.code}
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    return {
        "available": True,
        "healthy": data.get("healthy") is True,
        "device_ready": data.get("device_ready") is True,
        "browser_ready": data.get("browser_ready") is True,
        "warning_count": int(data.get("warning_count") or 0),
        "issue_count": int(data.get("issue_count") or 0),
    }


def ensure_target_network(target_adapter: Path, workflow_id: str, sites: list[str], deadline: float) -> dict:
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise WorkflowError("NETWORK_TIMEOUT", "Timed out waiting for target site policies before network probing.")
        try:
            return run_adapter_json(
                adapter_command(
                    target_adapter,
                    "browser-network-ensure",
                    "--workflow-id",
                    workflow_id,
                    *sites,
                    "--timeout-seconds",
                    str(max(1, min(90, int(remaining)))),
                ),
                max(2, min(95, int(remaining) + 1)),
                "TARGET_NETWORK_FAILED",
            )
        except WorkflowError as exc:
            if exc.message != "credential_browser_site_policy_missing":
                raise
            time.sleep(min(0.5, remaining))


def advisory_warning(phase: str, code: str, **details) -> dict:
    warning = {"phase": phase, "code": code}
    warning.update({key: value for key, value in details.items() if value is not None})
    emit({
        "schema_version": 1,
        "type": "phase",
        "phase": phase,
        "status": "degraded",
        "error_code": code,
    })
    return warning


def observe_target_network(
    target_adapter: Path,
    workflow_id: str,
    sites: list[str],
    deadline: float,
) -> tuple[dict | None, dict | None]:
    # Network assist must leave time for the source process and authoritative
    # Job waiter. It may accelerate recovery, but it never owns Job outcome.
    assist_deadline = min(deadline, time.monotonic() + 95)
    try:
        response = ensure_target_network(target_adapter, workflow_id, sites, assist_deadline)
    except WorkflowError as exc:
        return None, advisory_warning(
            "target_network",
            "TARGET_NETWORK_ASSIST_UNAVAILABLE",
            upstream_code=exc.code,
        )
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    network = data.get("network") if isinstance(data.get("network"), dict) else data
    status = str(network.get("status") or "").strip()
    if status == "reachable":
        emit({
            "schema_version": 1,
            "type": "phase",
            "phase": "target_network",
            "status": "succeeded",
            "mode": network.get("mode"),
        })
        return network, None
    if status == "unreachable":
        return network, advisory_warning(
            "target_network",
            "TARGET_NETWORK_UNREACHABLE",
            fallback_configured=network.get("fallback_configured") is True,
            mode=network.get("mode"),
        )
    return network, advisory_warning("target_network", "TARGET_NETWORK_RESULT_INVALID")


def run(args: argparse.Namespace) -> dict:
    started = time.monotonic()
    agent = safe_executable(args.agent_path, "credential-agent")
    target_adapter = safe_executable(args.target_adapter, "CUA Target Adapter", python_script=True)
    sites = site_names(args.site)
    deadline = started + args.timeout_seconds

    validated = run_json(
        [str(agent), "browser", "validate", "--output", "json", *sites],
        min(90, args.timeout_seconds),
        "SOURCE_VALIDATION_FAILED",
    )
    if validated.get("status") != "succeeded":
        raise WorkflowError("SOURCE_VALIDATION_FAILED", "Source browser login validation failed.")
    emit({"schema_version": 1, "type": "phase", "phase": "source_validate", "status": "succeeded"})

    desktop_args = ["--desktop-id", args.desktop_id] if args.desktop_id else []
    capabilities = run_adapter_json(
        adapter_command(target_adapter, "capabilities", *desktop_args),
        min(30, args.timeout_seconds),
        "TARGET_RESOLVE_FAILED",
    )
    capability_data = capabilities["data"]
    features = set(capability_data.get("features") or [])
    required_features = {
        "pair-relay-v1",
        "browser-unpacked-ensure",
        "browser-network-ensure-v1",
        "health-v1",
    }
    if not required_features.issubset(features):
        raise WorkflowError("TARGET_ADAPTER_INCOMPATIBLE", "Target adapter is missing required browser capabilities.")
    emit({
        "schema_version": 1,
        "type": "phase",
        "phase": "target_resolve",
        "status": "succeeded",
        "transport": capability_data.get("transport"),
    })

    paired = run_adapter_json(
        adapter_command(
            target_adapter,
            "begin",
            "--mode",
            "browser",
            "--agent-path",
            str(agent),
            *desktop_args,
            "--timeout-seconds",
            str(min(240, args.timeout_seconds)),
        ),
        min(250, args.timeout_seconds),
        "TARGET_PAIR_FAILED",
    )
    pair_data = paired["data"]
    device_id = str(pair_data.get("device_id") or "").strip()
    workflow_id = str(pair_data.get("workflow_id") or "").strip()
    if (
        not device_id
        or not workflow_id
        or pair_data.get("browser_extension_ready") is not True
        or pair_data.get("browser_connected") is not True
    ):
        raise WorkflowError("TARGET_PAIR_FAILED", "CUA pairing did not return an exact ready device and opaque workflow.")
    emit({"schema_version": 1, "type": "phase", "phase": "target_pair", "status": "succeeded", "device_id": device_id})

    # The Adapter owns the workflow-to-session mapping. Always finish the exact
    # opaque workflow after local observers stop, without discovering sessions.
    try:
        source, source_events = start_jsonl([
            str(agent), "browser", "sync", "--to", device_id, "--yes", "--output", "jsonl", *sites
        ])
        job_id = ""
        source_result = None
        warnings: list[dict] = []
        try:
            while True:
                event = read_event(source_events, deadline)
                if event is None:
                    break
                if event.get("type") == "result":
                    source_result = event
                    details = event.get("details") if isinstance(event.get("details"), dict) else {}
                    job = details.get("job") if isinstance(details.get("job"), dict) else {}
                    job_id = str(job.get("id") or "").strip()
                    break
                if event.get("type") == "phase" and event.get("phase") == "create_sync_job" and event.get("status") == "succeeded":
                    details = event.get("details") if isinstance(event.get("details"), dict) else {}
                    job = details.get("job") if isinstance(details.get("job"), dict) else {}
                    job_id = str(job.get("id") or "").strip()
                    break
            if not job_id:
                if source_result is not None:
                    raise_source_result_without_job(source_result)
                raise WorkflowError(
                    "SOURCE_SYNC_FAILED",
                    "Source Agent exited before creating an authoritative Sync Job or returning a result.",
                )

            _network, network_warning = observe_target_network(
                target_adapter,
                workflow_id,
                sites,
                deadline,
            )
            if network_warning:
                warnings.append(network_warning)
            if source_result is None:
                source_result = wait_jsonl_result(source, source_events, deadline, allow_failure_result=True)
        finally:
            stop_process(source)

        if source_result.get("status") == "pending_target":
            source_result = wait_authoritative_job(agent, job_id, deadline)
        if source_result.get("status") == "pending_target":
            details = source_result.get("details") if isinstance(source_result.get("details"), dict) else {}
            job = details.get("job") if isinstance(details.get("job"), dict) else {}
            raise WorkflowError(
                "SYNC_PENDING_TARGET",
                "The authoritative Sync Job is still pending after the bounded observation window.",
                job_id=job_id,
                status=str(job.get("status") or "pending_target"),
                target_health=target_health(target_adapter, workflow_id),
                warnings=warnings,
            )
        if source_result.get("status") != "succeeded":
            raise WorkflowError(
                "SYNC_NOT_SUCCEEDED",
                "The authoritative Sync Job did not succeed.",
                job_id=job_id,
                status=source_result.get("status"),
                target_health=target_health(target_adapter, workflow_id),
                warnings=warnings,
            )

        result = {
            "schema_version": 1,
            "status": "succeeded",
            "device_id": device_id,
            "job_id": job_id,
            "sites": sites,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        if warnings:
            result["warnings"] = warnings
        return result
    finally:
        active_error = sys.exc_info()[0] is not None
        try:
            run_adapter_json(
                adapter_command(target_adapter, "finish", "--workflow-id", workflow_id),
                30,
                "WORKFLOW_CLEANUP_FAILED",
            )
            emit({"schema_version": 1, "type": "phase", "phase": "workflow_cleanup", "status": "succeeded"})
        except WorkflowError as cleanup_error:
            emit({
                "schema_version": 1,
                "type": "phase",
                "phase": "workflow_cleanup",
                "status": "failed",
                "error_code": cleanup_error.code,
            })
            if not active_error:
                raise


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Sync exact browser sites through an explicit CUA Target Adapter v1.")
    value.add_argument("--agent-path", required=True)
    value.add_argument("--target-adapter", required=True)
    value.add_argument("--desktop-id")
    value.add_argument("--timeout-seconds", type=int, default=420)
    value.add_argument("site", nargs="+")
    return value


def main() -> int:
    args = parser().parse_args()
    if args.timeout_seconds < 60:
        emit({"schema_version": 1, "type": "result", "status": "failed", "error": {"code": "TIMEOUT_INVALID"}})
        return 2
    try:
        result = run(args)
    except WorkflowError as exc:
        emit({
            "schema_version": 1,
            "type": "result",
            "status": "failed",
            "error": {"code": exc.code, "message": exc.message},
            "details": exc.details,
        })
        return 1
    emit({"schema_version": 1, "type": "result", **result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
