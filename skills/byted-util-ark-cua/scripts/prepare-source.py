#!/usr/bin/env python3
"""Install and prepare an environment-bound Credential source Agent."""

import argparse
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_BASE = "https://al-artifacts-bj.tos-cn-beijing.volces.com"


def browser_prepare_command(agent):
    return [
        str(agent),
        "browser",
        "prepare",
        "--artifact-base-url",
        DEFAULT_ARTIFACT_BASE,
        "--output",
        "json",
    ]


def safe_agent(path):
    value = Path(path).expanduser()
    try:
        info = value.lstat()
    except OSError:
        return None
    if (
        not value.is_absolute()
        or not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or (os.name != "nt" and info.st_mode & 0o022)
        or (os.name != "nt" and not os.access(value, os.X_OK))
    ):
        return None
    return value


def run(command, timeout):
    try:
        return subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            command,
            124,
            stdout=json.dumps({
                "schema_version": 1,
                "status": "failed",
                "error": {"code": "OPERATION_TIMEOUT"},
            }) + "\n",
            stderr="",
        )


def json_result(completed):
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    for line in reversed(lines):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {}


def result_error_code(completed):
    result = json_result(completed)
    error = result.get("error") if isinstance(result.get("error"), dict) else {}
    return str(error.get("code") or "").strip()


def exact_browser_ready(status):
    return (
        status.get("connected") is True
        and status.get("install_state") in {"ready", "permission_required"}
        and status.get("extension_id") == status.get("expected_extension_id")
        and status.get("running_build_id") == status.get("expected_build_id")
    )


def manual_browser_install_error(agent, prepared):
    """Open the bounded installer surface and return one cross-platform action."""
    opened = json_result(run([str(agent), "browser", "open-install", "--output", "json"], 30))
    extension_directory = str(
        opened.get("extension_directory") or prepared.get("extension_directory") or ""
    ).strip()
    expected_extension_id = str(
        opened.get("expected_extension_id") or prepared.get("expected_extension_id") or ""
    ).strip()
    message = (
        "Credential Agent 已安装；Chrome 扩展需要一次手动加载。已请求打开 "
        "chrome://extensions/ 和扩展目录。请开启开发者模式，点击 "
        "Load unpacked/加载已解压的扩展程序，选择已打开的扩展目录"
    )
    if extension_directory:
        message += f"：{extension_directory}"
    message += "。完成后重跑同一句请求，后续配对和同步会自动续接。"
    if expected_extension_id:
        message += f" 固定扩展 ID：{expected_extension_id}。"
    return {
        "schema_version": 1,
        "status": "failed",
        "error": {
            "code": "SOURCE_BROWSER_USER_ACTION_REQUIRED",
            "message": message,
        },
    }


def default_agent():
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Local" / "AL" / "CredentialAgent" / "credential-agent.exe"
    return Path.home() / ".local" / "bin" / "credential-agent"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-path")
    parser.add_argument("--install-only", action="store_true")
    parser.add_argument("--skip-browser", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args()
    agent = safe_agent(args.agent_path or default_agent())
    installed = False
    if agent is None:
        bootstrap = run([sys.executable, str(ROOT / "scripts" / "bootstrap-agent.py")], min(args.timeout_seconds, 240))
        if bootstrap.returncode:
            print(json.dumps({"schema_version": 1, "status": "failed", "error": {"code": "AGENT_INSTALL_FAILED"}}))
            return 1
        agent = safe_agent(args.agent_path or default_agent())
        if agent is None:
            print(json.dumps({"schema_version": 1, "status": "failed", "error": {"code": "AGENT_INSTALL_INVALID"}}))
            return 1
        installed = True
    if args.install_only:
        print(json.dumps({
            "schema_version": 1,
            "status": "succeeded",
            "agent_path": str(agent),
            "agent_installed": installed,
            "device_ready": False,
            "browser_ready": False,
        }))
        return 0
    environment_id = os.environ.get("CREDENTIAL_AGENT_ENVIRONMENT_ID", "").strip()
    if environment_id != "prod":
        print(json.dumps({
            "schema_version": 1,
            "status": "failed",
            "error": {"code": "SOURCE_ENVIRONMENT_REQUIRED"},
        }))
        return 1
    capabilities = json_result(run([str(agent), "capabilities", "--output", "json"], 30))
    enrollment = capabilities.get("enrollment") if isinstance(capabilities.get("enrollment"), dict) else {}
    browser_capabilities = capabilities.get("browser") if isinstance(capabilities.get("browser"), dict) else {}
    if (
        enrollment.get("valid") is not True
        or enrollment.get("environment_id") != environment_id
        or enrollment.get("auth_mode") != "agentplan_device"
    ):
        print(json.dumps({
            "schema_version": 1,
            "status": "failed",
            "error": {"code": "SOURCE_BOOTSTRAP_REQUIRED"},
        }))
        return 1
    if not args.skip_browser:
        prepared = run(browser_prepare_command(agent), min(args.timeout_seconds, 180))
        if prepared.returncode:
            print(json.dumps({"schema_version": 1, "status": "failed", "error": {"code": "SOURCE_BROWSER_PREPARE_FAILED"}}))
            return 1
        prepared_result = json_result(prepared)
        status = json_result(run([str(agent), "browser", "status", "--output", "json"], 30))
        if browser_capabilities.get("connected") is True and status.get("connected") is not True:
            reconnected = run(
                [str(agent), "browser", "wait", "--for", "connected", "--timeout", "30s", "--output", "json"],
                min(args.timeout_seconds, 40),
            )
            if not reconnected.returncode:
                status = json_result(run([str(agent), "browser", "status", "--output", "json"], 30))
        if status.get("connected") is True and not exact_browser_ready(status):
            activated = run([str(agent), "browser", "activate", "--timeout", "2m", "--output", "json"], min(args.timeout_seconds, 150))
        else:
            activated = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        if activated.returncode:
            # A proof-bound setup can restart the Agent daemon while Chrome's
            # native host is reconnecting. Do not misreport that bounded race
            # as a user-action gate: wait for the existing enabled extension,
            # then retry activation once.
            reconnected = run(
                [str(agent), "browser", "wait", "--for", "connected", "--timeout", "30s", "--output", "json"],
                min(args.timeout_seconds, 40),
            )
            if not reconnected.returncode:
                activated = run([str(agent), "browser", "activate", "--timeout", "2m", "--output", "json"], min(args.timeout_seconds, 150))
        status = json_result(run([str(agent), "browser", "status", "--output", "json"], 30))
        if activated.returncode or not exact_browser_ready(status):
            print(json.dumps(manual_browser_install_error(agent, prepared_result), ensure_ascii=False))
            return 1
        waited = run([str(agent), "browser", "wait", "--for", "connected", "--timeout", "5m", "--output", "json"], min(args.timeout_seconds, 310))
        if waited.returncode:
            print(json.dumps({"schema_version": 1, "status": "failed", "error": {"code": "SOURCE_BROWSER_NOT_CONNECTED"}}))
            return 1
    doctor = None
    for attempt in range(5):
        doctor_command = [str(agent), "doctor", "--strict", "--output", "json"]
        if args.skip_browser:
            doctor_command.append("--skip-browser")
        doctor = run(doctor_command, min(args.timeout_seconds, 30))
        if not doctor.returncode:
            break
        if attempt < 4:
            time.sleep(0.5)
    if doctor is None or doctor.returncode:
        print(json.dumps({"schema_version": 1, "status": "failed", "error": {"code": "SOURCE_HEALTH_FAILED"}}))
        return 1
    print(json.dumps({
        "schema_version": 1,
        "status": "succeeded",
        "agent_path": str(agent),
        "agent_installed": installed,
        "device_ready": True,
        "browser_ready": not args.skip_browser,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
