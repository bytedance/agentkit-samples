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

"""Manage the Volcengine Redis MCP streamable-http background service.

This helper is used only by the optional background service shell scripts.
The normal skill client path remains `scripts/mcp_client.py` over stdio.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import time
from pathlib import Path
from urllib import error, request


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
LOG_DIR = SKILL_DIR / "logs"
PID_FILE = SKILL_DIR / "volcengine_redis_mcp.pid"
SERVER_SOURCE = (
    "git+https://github.com/volcengine/mcp-server.git"
    "#subdirectory=server/mcp_server_redis"
)
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18765


def credential_snapshot() -> dict[str, object]:
    auth_present = bool(os.environ.get("AUTHORIZATION") or os.environ.get("authorization"))
    ak_present = bool(os.environ.get("VOLCENGINE_ACCESS_KEY"))
    sk_present = bool(os.environ.get("VOLCENGINE_SECRET_KEY"))
    session_token_present = bool(os.environ.get("VOLCENGINE_SESSION_TOKEN"))
    region = os.environ.get("VOLCENGINE_REGION")

    if auth_present:
        mode = "authorization"
    elif ak_present and sk_present:
        mode = "aksk+session" if session_token_present else "aksk"
    else:
        mode = "missing"

    missing = []
    if not auth_present:
        if not ak_present:
            missing.append("VOLCENGINE_ACCESS_KEY")
        if not sk_present:
            missing.append("VOLCENGINE_SECRET_KEY")

    return {
        "mode": mode,
        "region": region,
        "has_authorization": auth_present,
        "has_access_key": ak_present,
        "has_secret_key": sk_present,
        "has_session_token": session_token_present,
        "missing": missing,
    }


def ensure_posix() -> None:
    if os.name != "posix":
        raise SystemExit(
            "The streamable-http service scripts require a POSIX-like shell "
            "environment. Use the stdio client path on non-POSIX systems."
        )


def config() -> tuple[str, int, str]:
    host = os.environ.get("VOLCENGINE_REDIS_MCP_HOST", DEFAULT_HOST)
    port = int(os.environ.get("VOLCENGINE_REDIS_MCP_PORT", str(DEFAULT_PORT)))
    endpoint = f"http://{host}:{port}/mcp"
    return host, port, endpoint


def config_from_pidfile(
    data: dict[str, object] | None,
) -> tuple[str, int, str] | None:
    if not isinstance(data, dict):
        return None

    host = data.get("host")
    port = data.get("port")
    endpoint = data.get("endpoint")
    if not isinstance(host, str) or not host:
        return None
    try:
        port_value = int(port)
    except (TypeError, ValueError):
        return None
    if not isinstance(endpoint, str) or not endpoint:
        endpoint = f"http://{host}:{port_value}/mcp"
    return host, port_value, endpoint


def server_command() -> list[str]:
    return [
        "uvx",
        "--from",
        SERVER_SOURCE,
        "mcp-server-redis",
        "-t",
        "streamable-http",
    ]


def is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def process_command(pid: int) -> str:
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return ""
    return result.stdout.strip()


def is_managed_redis_mcp_process(pid: int) -> bool:
    command = process_command(pid)
    return bool(command) and "mcp-server-redis" in command


def tcp_ready(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def listener_pid(port: int) -> int | None:
    try:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fp"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None

    for line in result.stdout.splitlines():
        if not line.startswith("p"):
            continue
        try:
            pid = int(line[1:])
        except ValueError:
            continue
        if is_managed_redis_mcp_process(pid):
            return pid
    return None


def endpoint_health(host: str, port: int, timeout: float = 2.0) -> tuple[bool, str]:
    endpoint = f"http://{host}:{port}/mcp"
    req = request.Request(endpoint, headers={"Accept": "text/event-stream"})
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return True, f"HTTP {resp.status}"
    except error.HTTPError as exc:
        if exc.code in {400, 405, 406}:
            return True, f"HTTP {exc.code}"
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, exc.__class__.__name__


def read_pidfile() -> dict[str, object] | None:
    if not PID_FILE.exists():
        return None

    raw = PID_FILE.read_text(encoding="utf-8").strip()
    if not raw:
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            return {"pid": int(raw)}
        except ValueError:
            return None
    return data


def write_pidfile(
    pid: int,
    host: str,
    port: int,
    endpoint: str,
    log_file: Path,
    credentials: dict[str, object],
) -> None:
    data = {
        "pid": pid,
        "host": host,
        "port": port,
        "endpoint": endpoint,
        "transport": "streamable-http",
        "credentials": credentials,
        "log_file": str(log_file.relative_to(SKILL_DIR)),
        "command": server_command(),
    }
    PID_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def pid_from(data: dict[str, object] | None) -> int | None:
    if not data:
        return None
    try:
        return int(data["pid"])
    except (KeyError, TypeError, ValueError):
        return None


def latest_log() -> Path | None:
    logs = sorted(LOG_DIR.glob("volcengine_redis_mcp_*.log"), reverse=True)
    return logs[0] if logs else None


def print_recent_logs() -> None:
    log_file = latest_log()
    if not log_file:
        return
    print("Recent logs:")
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[-10:]:
        print(line)


def remove_stale_pidfile() -> None:
    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass


def start() -> int:
    host, port, endpoint = config()
    credentials = credential_snapshot()
    data = read_pidfile()
    pid = pid_from(data)
    if pid and is_process_running(pid) and is_managed_redis_mcp_process(pid):
        print(f"Volcengine Redis MCP server is already running with PID {pid}.")
        return 1
    if PID_FILE.exists():
        print("Removing stale Redis MCP pid file.")
        remove_stale_pidfile()

    existing_listener = listener_pid(port)
    if existing_listener is not None:
        print(
            f"Volcengine Redis MCP server is already listening on "
            f"{host}:{port} with PID {existing_listener}."
        )
        return 1
    if tcp_ready(host, port):
        print(f"Port {port} on {host} is already in use. Refusing to start.")
        return 1

    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / f"volcengine_redis_mcp_{time.strftime('%Y%m%d_%H%M%S')}.log"
    env = os.environ.copy()
    env["MCP_SERVER_HOST"] = host
    env["MCP_SERVER_PORT"] = str(port)

    print("Starting Volcengine Redis MCP Server...")
    if credentials["mode"] == "missing":
        missing = ", ".join(credentials["missing"])
        print(
            "Warning: Redis credentials are missing from the startup environment. "
            "The MCP endpoint may start, but Redis tool calls will fail."
        )
        print(f"Missing credentials: {missing}")

    with log_file.open("ab") as log:
        process = subprocess.Popen(
            server_command(),
            cwd=str(SKILL_DIR),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    for _ in range(20):
        if process.poll() is not None:
            break
        listener = listener_pid(port)
        healthy, _ = endpoint_health(host, port)
        if listener is not None and healthy:
            write_pidfile(listener, host, port, endpoint, log_file, credentials)
            print(f"Volcengine Redis MCP Server started with PID {listener}.")
            print("Transport: streamable-http")
            print(f"Endpoint: {endpoint}")
            print(f"Credential mode at startup: {credentials['mode']}")
            print(f"Logs are being written to {log_file.relative_to(SKILL_DIR)}")
            return 0
        time.sleep(1)

    print("Volcengine Redis MCP Server did not become ready in time.")
    print_recent_logs()
    if process.poll() is None:
        process.terminate()
    remove_stale_pidfile()
    return 1


def status() -> int:
    data = read_pidfile()
    persisted_config = config_from_pidfile(data)
    if persisted_config is not None:
        host, port, endpoint = persisted_config
    else:
        host, port, endpoint = config()
    pid = pid_from(data)

    if pid is None:
        print("Status: STOPPED (volcengine_redis_mcp.pid not found)")
        listener = listener_pid(port)
        if listener is not None:
            print(f"Port {port} on {host} is in use by managed PID {listener}.")
        return 0

    if not is_process_running(pid):
        print(f"Status: STOPPED (PID file exists but process {pid} is not running)")
        remove_stale_pidfile()
        return 0

    if not is_managed_redis_mcp_process(pid):
        print(
            "Status: UNKNOWN "
            f"(pid file points to PID {pid}, but it is not a managed Redis MCP process)"
        )
        print("No pid file changes were made.")
        return 1

    print(f"Status: RUNNING (PID: {pid})")
    print("Transport: streamable-http")
    print(f"Endpoint: {endpoint}")
    credentials = data.get("credentials") if isinstance(data, dict) else None
    if isinstance(credentials, dict):
        mode = credentials.get("mode", "unknown")
        print(f"Credential mode at startup: {mode}")
        region = credentials.get("region")
        if region:
            print(f"Startup region: {region}")
        if mode == "missing":
            missing = credentials.get("missing") or []
            if missing:
                print(
                    "Credential warning: Redis tool calls will fail until the "
                    "service is restarted with the required credentials."
                )
                print(f"Missing at startup: {', '.join(str(item) for item in missing)}")
    healthy, detail = endpoint_health(host, port)
    if healthy:
        print(f"Health: READY ({detail})")
    else:
        print(f"Health: NOT_READY ({detail})")
    print_recent_logs()
    return 0


def stop() -> int:
    _, port, _ = config()
    data = read_pidfile()
    pid = pid_from(data)
    if pid is None:
        pid = listener_pid(port)
        if pid is None:
            print("No volcengine_redis_mcp.pid found. Server is likely not running.")
            return 0

    if not is_process_running(pid):
        pid = listener_pid(port)
        if pid is None:
            print("Volcengine Redis MCP server process not found. Cleaning up pid file.")
            remove_stale_pidfile()
            return 0

    if not is_managed_redis_mcp_process(pid):
        print(
            f"Refusing to stop PID {pid} because it is not a managed "
            "Volcengine Redis MCP process."
        )
        print(f"Remove {PID_FILE.name} manually if it is stale.")
        return 1

    print(f"Stopping Volcengine Redis MCP server with PID {pid}...")
    os.kill(pid, signal.SIGTERM)

    deadline = time.time() + 5
    while time.time() < deadline:
        if not is_process_running(pid):
            break
        time.sleep(0.2)

    if is_process_running(pid):
        print("Force killing Volcengine Redis MCP server...")
        os.kill(pid, signal.SIGKILL)

    remove_stale_pidfile()
    print("Volcengine Redis MCP server stopped.")
    return 0


def main() -> int:
    ensure_posix()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "status", "stop"))
    args = parser.parse_args()

    if args.command == "start":
        return start()
    if args.command == "status":
        return status()
    if args.command == "stop":
        return stop()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
