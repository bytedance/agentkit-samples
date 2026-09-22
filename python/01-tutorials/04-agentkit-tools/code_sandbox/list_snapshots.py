#!/usr/bin/env python3
"""List all session snapshots for a given AgentKit sandbox tool.

Supports filtering by UserSessionId, SessionId, and creation time range.
Automatically paginates through all results.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any


tools_types: Any = None
AgentkitToolsClient: Any = None


def _load_agentkit() -> None:
    global AgentkitToolsClient
    global tools_types

    if tools_types is not None:
        return

    try:
        from agentkit.sdk.tools import types as loaded_tools_types
        from agentkit.sdk.tools.client import AgentkitToolsClient as LoadedClient
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing dependency. Run: pip install agentkit-sdk-python==0.8.0"
        ) from exc

    tools_types = loaded_tools_types
    AgentkitToolsClient = LoadedClient


def _compact_model(model: Any) -> dict[str, Any]:
    if model is None:
        return {}
    if hasattr(model, "model_dump"):
        return model.model_dump(by_alias=True, exclude_none=True)
    return {
        key: value
        for key, value in vars(model).items()
        if not key.startswith("_") and value is not None
    }


def list_snapshots(
    *,
    tool_id: str,
    user_session_id: str = "",
    session_id: str = "",
    page_size: int = 100,
    region: str = "",
    access_key: str = "",
    secret_key: str = "",
    session_token: str = "",
    create_time_after: str = "",
    create_time_before: str = "",
) -> dict[str, Any]:
    _load_agentkit()
    client = AgentkitToolsClient(
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        session_token=session_token,
    )

    snapshots: list[Any] = []
    next_token: str | None = None
    seen_tokens: set[str] = set()

    while True:
        request_kwargs: dict[str, Any] = {
            "tool_id": tool_id,
            "max_results": page_size,
            "next_token": next_token,
        }
        if user_session_id:
            request_kwargs["user_session_id"] = user_session_id
        if session_id:
            request_kwargs["session_id"] = session_id
        if create_time_after:
            request_kwargs["create_time_after"] = create_time_after
        if create_time_before:
            request_kwargs["create_time_before"] = create_time_before

        response = client.list_session_snapshots(
            tools_types.ListSessionSnapshotsRequest(**request_kwargs)
        )
        snapshots.extend(response.snapshots or [])

        next_token = response.next_token or None
        if not next_token or next_token in seen_tokens:
            break
        seen_tokens.add(next_token)

    return {
        "tool_id": tool_id,
        "total_count": len(snapshots),
        "snapshots": [_compact_model(snapshot) for snapshot in snapshots],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "List all session snapshots for a given AgentKit sandbox tool, "
            "with optional filtering by UserSessionId, SessionId, or creation time."
        )
    )
    parser.add_argument(
        "positional", nargs="*", help="Optional: TOOL_ID [USER_SESSION_ID]"
    )
    parser.add_argument("--tool-id", help="AgentKit sandbox tool ID (required).")
    parser.add_argument(
        "--user-session-id",
        default="",
        help="Filter snapshots by UserSessionId.",
    )
    parser.add_argument(
        "--session-id",
        default="",
        help="Filter snapshots by the internal SessionId (sandbox session id).",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=100,
        help="Page size when listing snapshots per request. Default: 100.",
    )
    parser.add_argument(
        "--region",
        default=os.getenv("VOLCENGINE_REGION", ""),
        help="Volcengine region. Defaults to VOLCENGINE_REGION or SDK config.",
    )
    parser.add_argument(
        "--access-key",
        default=os.getenv("VOLCENGINE_ACCESS_KEY", ""),
        help="Volcengine access key. Defaults to VOLCENGINE_ACCESS_KEY.",
    )
    parser.add_argument(
        "--secret-key",
        default=os.getenv("VOLCENGINE_SECRET_KEY", ""),
        help="Volcengine secret key. Defaults to VOLCENGINE_SECRET_KEY.",
    )
    parser.add_argument(
        "--session-token",
        default=os.getenv("VOLCENGINE_SESSION_TOKEN", ""),
        help="Optional STS session token. Defaults to VOLCENGINE_SESSION_TOKEN.",
    )
    parser.add_argument(
        "--create-time-after",
        default="",
        help="Only list snapshots created after this time (RFC3339 string, e.g. 2025-01-01T00:00:00Z).",
    )
    parser.add_argument(
        "--create-time-before",
        default="",
        help="Only list snapshots created before this time (RFC3339 string).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    positional = list(args.positional)

    tool_id = args.tool_id or (positional.pop(0) if positional else "")
    user_session_id = args.user_session_id or (positional.pop(0) if positional else "")

    if positional:
        raise SystemExit(f"Unexpected positional arguments: {' '.join(positional)}")
    if not tool_id:
        raise SystemExit("--tool-id is required")
    if args.page_size <= 0:
        raise SystemExit("--page-size must be a positive integer")

    result = list_snapshots(
        tool_id=(tool_id or "").strip(),
        user_session_id=(user_session_id or "").strip(),
        session_id=(args.session_id or "").strip(),
        page_size=args.page_size,
        region=(args.region or "").strip(),
        access_key=(args.access_key or "").strip(),
        secret_key=(args.secret_key or "").strip(),
        session_token=(args.session_token or "").strip(),
        create_time_after=(args.create_time_after or "").strip(),
        create_time_before=(args.create_time_before or "").strip(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
