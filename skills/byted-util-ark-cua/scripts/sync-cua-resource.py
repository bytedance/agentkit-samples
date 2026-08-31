#!/usr/bin/env python3
"""Deliver one non-browser resource through CUA Target Adapter v1."""

import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path


class ResourceError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def safe_file(value, label, executable=False):
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ResourceError("PATH_INVALID", f"{label} must be absolute.")
    try:
        info = path.lstat()
    except OSError as exc:
        raise ResourceError("PATH_INVALID", f"{label} does not exist.") from exc
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or (os.name != "nt" and info.st_mode & 0o022)
    ):
        raise ResourceError("PATH_UNSAFE", f"{label} is not a safe regular file.")
    if executable and os.name != "nt" and not os.access(path, os.X_OK):
        raise ResourceError("PATH_UNSAFE", f"{label} is not executable.")
    return path


def parse_object(raw, code):
    lines = [line for line in raw.splitlines() if line.strip()]
    if not lines:
        raise ResourceError(code, "Command returned no structured result.")
    try:
        value = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise ResourceError(code, "Command returned invalid structured output.") from exc
    if not isinstance(value, dict):
        raise ResourceError(code, "Command returned invalid structured output.")
    return value


def adapter(adapter_path, *args, timeout=300):
    completed = subprocess.run(
        [sys.executable, str(adapter_path), "credential-target", *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=timeout,
        check=False,
    )
    value = parse_object(completed.stdout, "TARGET_OPERATION_FAILED")
    if completed.returncode or value.get("ok") is not True or value.get("adapter_protocol") != "cua-target/v1":
        error = value.get("error") if isinstance(value.get("error"), dict) else {}
        raise ResourceError(str(error.get("code") or "TARGET_OPERATION_FAILED"), str(error.get("message") or "Target operation failed."))
    return value.get("data") if isinstance(value.get("data"), dict) else {}


def resource_command(args, agent, device_id):
    if args.resource == "env":
        return [str(agent), "env", "sync", "--to", device_id, *args.name]
    if args.resource == "secret":
        return [str(agent), "secret", "sync", "--to", device_id, *args.name]
    if args.resource == "credential-set":
        return [str(agent), "credential-set", "sync", "--to", device_id, "--type", args.set_type, "--name", args.set_name]
    if args.resource == "file":
        return [str(agent), "file", "sync", "--to", device_id, "--profile", args.profile]
    raise ResourceError("RESOURCE_INVALID", "Unsupported resource type.")


def run(args):
    agent = safe_file(args.agent_path, "credential-agent", executable=True)
    adapter_path = safe_file(args.target_adapter, "CUA Target Adapter")
    desktop = ["--desktop-id", args.desktop_id] if args.desktop_id else []
    begun = adapter(
        adapter_path, "begin", "--mode", "device", "--agent-path", str(agent),
        *desktop, "--timeout-seconds", str(args.timeout_seconds),
        timeout=args.timeout_seconds + 10,
    )
    workflow_id = str(begun.get("workflow_id") or "").strip()
    device_id = str(begun.get("device_id") or "").strip()
    if not workflow_id or not device_id or begun.get("device_ready") is not True:
        raise ResourceError("TARGET_OPERATION_FAILED", "Target did not return an exact ready device and workflow.")
    delivery_error = None
    try:
        interactive = args.resource in {"secret", "credential-set"}
        completed = subprocess.run(
            resource_command(args, agent, device_id),
            stdin=None if interactive else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=None if interactive else subprocess.DEVNULL,
            text=True,
            timeout=args.timeout_seconds,
            check=False,
        )
        if completed.returncode:
            raise ResourceError("SOURCE_SYNC_FAILED", "credential-agent did not complete the requested resource delivery.")
        return {
            "schema_version": 1,
            "status": "succeeded",
            "resource": args.resource,
            "resource_count": len(args.name) if hasattr(args, "name") else 1,
            "device_id": device_id,
        }
    except Exception as exc:
        delivery_error = exc
        raise
    finally:
        try:
            adapter(adapter_path, "finish", "--workflow-id", workflow_id, timeout=40)
        except (ResourceError, subprocess.TimeoutExpired):
            if delivery_error is None:
                raise


def parser():
    value = argparse.ArgumentParser()
    value.add_argument("--agent-path", required=True)
    value.add_argument("--target-adapter", required=True)
    value.add_argument("--desktop-id")
    value.add_argument("--timeout-seconds", type=int, default=420)
    sub = value.add_subparsers(dest="resource", required=True)
    for kind in ("env", "secret"):
        item = sub.add_parser(kind)
        item.add_argument("name", nargs="+")
    item = sub.add_parser("credential-set")
    item.add_argument("--type", dest="set_type", required=True)
    item.add_argument("--name", dest="set_name", required=True)
    item = sub.add_parser("file")
    item.add_argument("--profile", required=True)
    return value


def main():
    try:
        result = run(parser().parse_args())
    except (ResourceError, subprocess.TimeoutExpired) as exc:
        code = exc.code if isinstance(exc, ResourceError) else "SYNC_TIMEOUT"
        message = exc.message if isinstance(exc, ResourceError) else "Credential resource sync timed out."
        print(json.dumps({"schema_version": 1, "status": "failed", "error": {"code": code, "message": message}}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
