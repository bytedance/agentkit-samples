"""Shared helpers for the HTTP sandbox snapshot lifecycle example scripts."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from _http_client import AgentKitToolsHttpClient


DEFAULT_TTL_SECONDS = 8 * 60 * 60
DEFAULT_WAIT_TIMEOUT_SECONDS = 10 * 60
DEFAULT_POLL_INTERVAL_SECONDS = 5
STATE_FILE_ENV = "AGENTKIT_LIFECYCLE_STATE"
TOOL_ID_ENVS = ("AGENTKIT_TOOL_ID", "AGENTKIT_SANDBOX_TOOL_ID")

_T = TypeVar("_T")
_AUTHORIZATION_QUERY_RE = re.compile(r"(?i)(Authorization=)[^&\s]+")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_sensitive_values(value: Any) -> Any:
    """Redact signed endpoint tokens before printing or writing local state."""
    if isinstance(value, dict):
        return {key: redact_sensitive_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_sensitive_values(item) for item in value]
    if isinstance(value, str):
        return _AUTHORIZATION_QUERY_RE.sub(r"\1<redacted>", value)
    return value


def model_to_dict(value: dict[str, Any]) -> dict[str, Any]:
    return redact_sensitive_values(value)


def print_json(value: Any) -> None:
    print(
        json.dumps(
            redact_sensitive_values(value),
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def state_path() -> Path:
    configured = os.getenv(STATE_FILE_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).with_name(".sandbox_snapshot_state.json")


def load_state() -> dict[str, Any]:
    path = state_path()
    if not path.is_file():
        raise RuntimeError(
            f"state file does not exist: {path}; run 01_create_session.py first"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"state file must contain a JSON object: {path}")
    return redact_sensitive_values(data)


def save_state(state: dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            redact_sensitive_values(state),
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def require_string(state: dict[str, Any], key: str) -> str:
    value = state.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"state is missing required field {key!r}")
    return value.strip()


def resolve_tool_id(state: dict[str, Any] | None = None) -> str:
    configured = [
        (name, os.getenv(name, "").strip())
        for name in TOOL_ID_ENVS
        if os.getenv(name, "").strip()
    ]
    if len({value for _, value in configured}) > 1:
        values = ", ".join(f"{name}={value}" for name, value in configured)
        raise RuntimeError(f"conflicting tool ID environment variables: {values}")

    env_tool_id = configured[0][1] if configured else ""
    state_tool_id = ""
    if state is not None:
        raw = state.get("tool_id")
        state_tool_id = raw.strip() if isinstance(raw, str) else ""

    if env_tool_id and state_tool_id and env_tool_id != state_tool_id:
        raise RuntimeError(
            f"tool ID from environment ({env_tool_id}) does not match state "
            f"({state_tool_id})"
        )
    tool_id = env_tool_id or state_tool_id
    if not tool_id:
        names = " or ".join(TOOL_ID_ENVS)
        raise RuntimeError(f"set {names} to the sandbox tool ID")
    return tool_id


def positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be greater than zero")
    return value


def ttl_seconds() -> int:
    return positive_int_env("AGENTKIT_SESSION_TTL_SECONDS", DEFAULT_TTL_SECONDS)


def new_client() -> AgentKitToolsHttpClient:
    return AgentKitToolsHttpClient()


def wait_until(
    description: str,
    fetch: Callable[[], _T],
    done: Callable[[_T], bool],
    failed: Callable[[_T], bool],
) -> _T:
    timeout = positive_int_env(
        "AGENTKIT_WAIT_TIMEOUT_SECONDS", DEFAULT_WAIT_TIMEOUT_SECONDS
    )
    interval = positive_int_env(
        "AGENTKIT_POLL_INTERVAL_SECONDS", DEFAULT_POLL_INTERVAL_SECONDS
    )
    deadline = time.monotonic() + timeout
    while True:
        value = fetch()
        if done(value):
            return value
        if failed(value):
            raise RuntimeError(f"{description} entered a failure state")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"timed out after {timeout}s waiting for {description}")
        time.sleep(interval)


def retry_on_exception(
    description: str,
    call: Callable[[], _T],
    retryable: Callable[[Exception], bool],
) -> _T:
    """Retry an API call while the backend reports a known transition state."""
    timeout = positive_int_env(
        "AGENTKIT_WAIT_TIMEOUT_SECONDS", DEFAULT_WAIT_TIMEOUT_SECONDS
    )
    interval = positive_int_env(
        "AGENTKIT_POLL_INTERVAL_SECONDS", DEFAULT_POLL_INTERVAL_SECONDS
    )
    deadline = time.monotonic() + timeout
    while True:
        try:
            return call()
        except Exception as exc:
            if not retryable(exc):
                raise
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"timed out after {timeout}s waiting for {description}"
                ) from exc
            print(f"Waiting for {description}; retrying in {interval}s...")
            time.sleep(interval)


def normalized_status(value: Any) -> str:
    if isinstance(value, dict):
        status = value.get("Status")
    else:
        status = getattr(value, "status", None)
    return status.strip().lower() if isinstance(status, str) else ""


def wait_for_session(
    client: AgentKitToolsHttpClient, tool_id: str, session_id: str
) -> dict[str, Any]:
    ready = {"ready", "running", "available", "active", "succeeded", "success"}
    failed = {"failed", "error", "deleted", "terminated"}

    def fetch() -> dict[str, Any]:
        return client.get_session({"ToolId": tool_id, "SessionId": session_id})

    return wait_until(
        f"session {session_id} to become ready",
        fetch,
        lambda value: normalized_status(value) in ready,
        lambda value: normalized_status(value) in failed,
    )


def wait_for_paused_session(
    client: AgentKitToolsHttpClient, tool_id: str, session_id: str
) -> dict[str, Any]:
    """Wait until a PauseSession request leaves the session paused."""
    failed = {"failed", "error", "deleted", "terminated"}

    def fetch() -> dict[str, Any]:
        return client.get_session({"ToolId": tool_id, "SessionId": session_id})

    return wait_until(
        f"session {session_id} to become paused",
        fetch,
        lambda value: normalized_status(value) == "paused",
        lambda value: normalized_status(value) in failed,
    )


def wait_for_snapshot(
    client: AgentKitToolsHttpClient, tool_id: str, snapshot_id: str
) -> dict[str, Any]:
    ready = {"ready", "available", "completed", "succeeded", "success"}
    failed = {"failed", "error", "deleted"}

    def fetch() -> dict[str, Any]:
        return client.get_session_snapshot(
            {"ToolId": tool_id, "SnapshotId": snapshot_id}
        )

    return wait_until(
        f"snapshot {snapshot_id} to become ready",
        fetch,
        lambda value: normalized_status(value.get("Snapshot") or {}) in ready,
        lambda value: normalized_status(value.get("Snapshot") or {}) in failed,
    )


def list_all_snapshots(
    client: AgentKitToolsHttpClient, tool_id: str
) -> list[dict[str, Any]]:
    """List every snapshot under a tool, following NextToken pagination."""
    snapshots: list[dict[str, Any]] = []
    next_token: str | None = None
    seen_tokens: set[str] = set()
    while True:
        request: dict[str, Any] = {"ToolId": tool_id, "MaxResults": 100}
        if next_token:
            request["NextToken"] = next_token
        response = client.list_session_snapshots(request)
        snapshots.extend(response.get("Snapshots") or [])
        raw_next_token = response.get("NextToken")
        next_token = raw_next_token.strip() if isinstance(raw_next_token, str) else None
        if not next_token:
            return redact_sensitive_values(snapshots)
        if next_token in seen_tokens:
            raise RuntimeError(
                f"ListSessionSnapshots repeated NextToken {next_token!r}"
            )
        seen_tokens.add(next_token)
