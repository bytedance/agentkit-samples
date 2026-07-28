#!/usr/bin/env python3
"""Ensure an AgentKit sandbox session exists.

The flow mirrors agentkit.toolkit.cli.sandbox.session_create:
1. find an existing remote session by UserSessionId;
2. if absent, find the latest snapshot for the UserSessionId and resume it;
3. if no snapshot exists, create a new session with the UserSessionId.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any


DEFAULT_TTL_SECONDS = 28800
tools_types: Any = None
AgentkitToolsClient: Any = None
build_session_tos_mount_points: Any = None


def _load_agentkit() -> None:
    global AgentkitToolsClient
    global build_session_tos_mount_points
    global tools_types

    if tools_types is not None:
        return

    try:
        from agentkit.sdk.tools import types as loaded_tools_types
        from agentkit.sdk.tools.client import AgentkitToolsClient as LoadedClient
        from agentkit.toolkit.cli.sandbox.tos_config import (
            build_session_tos_mount_points as loaded_build_tos_mount_points,
        )
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing dependency. Run: pip install agentkit-sdk-python==0.8.0"
        ) from exc

    tools_types = loaded_tools_types
    AgentkitToolsClient = LoadedClient
    build_session_tos_mount_points = loaded_build_tos_mount_points


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


def _session_result(
    *,
    action: str,
    tool_id: str,
    session_id: str,
    instance_id: str | None,
    endpoint: str | None,
    snapshot_id: str | None = None,
    raw: Any = None,
) -> dict[str, Any]:
    result = {
        "action": action,
        "tool_id": tool_id,
        "session_id": session_id,
        "instance_id": instance_id,
        "endpoint": endpoint,
    }
    if snapshot_id:
        result["snapshot_id"] = snapshot_id
    if raw is not None:
        result["raw"] = _compact_model(raw)
    return result


def _find_remote_session(
    client: Any,
    *,
    tool_id: str,
    session_id: str,
) -> Any:
    response = client.list_sessions(
        tools_types.ListSessionsRequest(
            tool_id=tool_id,
            max_results=10,
            filters=[
                tools_types.FiltersItemForListSessions(
                    name="UserSessionId",
                    values=[session_id],
                )
            ],
        )
    )
    for session in response.session_infos or []:
        if session.user_session_id == session_id:
            return session
    return None


def _latest_snapshot(
    client: Any,
    *,
    tool_id: str,
    session_id: str,
    page_size: int,
) -> Any:
    snapshots: list[Any] = []
    next_token: str | None = None
    seen_tokens: set[str] = set()

    while True:
        response = client.list_session_snapshots(
            tools_types.ListSessionSnapshotsRequest(
                tool_id=tool_id,
                user_session_id=session_id,
                max_results=page_size,
                next_token=next_token,
            )
        )
        snapshots.extend(response.snapshots or [])

        next_token = response.next_token or None
        if not next_token or next_token in seen_tokens:
            break
        seen_tokens.add(next_token)

    snapshots = [
        snapshot
        for snapshot in snapshots
        if isinstance(snapshot.snapshot_id, str) and snapshot.snapshot_id.strip()
    ]
    if not snapshots:
        return None

    return max(snapshots, key=lambda snapshot: snapshot.created_at or "")


def _resume_from_snapshot(
    client: Any,
    *,
    tool_id: str,
    session_id: str,
    snapshot_id: str,
    ttl: int,
) -> dict[str, Any]:
    response = client.resume_session_from_snapshot(
        tools_types.ResumeSessionFromSnapshotRequest(
            tool_id=tool_id,
            snapshot_id=snapshot_id,
            ttl=ttl,
            create_new_instance=False,
        )
    )
    instance_id = (response.session_id or "").strip()
    if not instance_id:
        raise RuntimeError("ResumeSessionFromSnapshot response missing SessionId")

    session = client.get_session(
        tools_types.GetSessionRequest(tool_id=tool_id, session_id=instance_id)
    )
    return _session_result(
        action="restored_from_snapshot",
        tool_id=tool_id,
        session_id=session.user_session_id or session_id,
        instance_id=session.session_id or instance_id,
        endpoint=session.endpoint,
        snapshot_id=snapshot_id,
        raw=session,
    )


def _create_session(
    client: Any,
    *,
    tool_id: str,
    session_id: str,
    ttl: int,
    include_tos_mount_points: bool,
) -> dict[str, Any]:
    tos_mount_points = None
    if include_tos_mount_points:
        tool = client.get_tool(tools_types.GetToolRequest(tool_id=tool_id))
        tos_mount_points = build_session_tos_mount_points(
            tool,
            tool_id=tool_id,
            session_id=session_id,
        )

    response = client.create_session(
        tools_types.CreateSessionRequest(
            tool_id=tool_id,
            ttl=ttl,
            ttl_unit="second",
            user_session_id=session_id,
            tos_mount_points=tos_mount_points,
        )
    )
    return _session_result(
        action="created",
        tool_id=tool_id,
        session_id=response.user_session_id or session_id,
        instance_id=response.session_id,
        endpoint=response.endpoint,
        raw=response,
    )


def ensure_session(
    *,
    tool_id: str,
    session_id: str,
    ttl: int = DEFAULT_TTL_SECONDS,
    region: str = "",
    access_key: str = "",
    secret_key: str = "",
    session_token: str = "",
    snapshot_page_size: int = 100,
    include_tos_mount_points: bool = True,
) -> dict[str, Any]:
    _load_agentkit()
    client = AgentkitToolsClient(
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        session_token=session_token,
    )

    session = _find_remote_session(client, tool_id=tool_id, session_id=session_id)
    if session:
        return _session_result(
            action="existing",
            tool_id=tool_id,
            session_id=session.user_session_id or session_id,
            instance_id=session.session_id,
            endpoint=session.endpoint,
            raw=session,
        )

    snapshot = _latest_snapshot(
        client,
        tool_id=tool_id,
        session_id=session_id,
        page_size=snapshot_page_size,
    )
    if snapshot and snapshot.snapshot_id:
        return _resume_from_snapshot(
            client,
            tool_id=tool_id,
            session_id=session_id,
            snapshot_id=snapshot.snapshot_id.strip(),
            ttl=ttl,
        )

    return _create_session(
        client,
        tool_id=tool_id,
        session_id=session_id,
        ttl=ttl,
        include_tos_mount_points=include_tos_mount_points,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ensure an AgentKit sandbox session exists by reusing an existing "
            "session, restoring the latest snapshot, or creating a new session."
        )
    )
    parser.add_argument("positional", nargs="*", help="Optional: TOOL_ID SESSION_ID")
    parser.add_argument("--tool-id", help="AgentKit sandbox tool ID.")
    parser.add_argument("--session-id", help="User session ID to ensure.")
    parser.add_argument(
        "--ttl",
        type=int,
        default=int(os.getenv("AGENTKIT_SANDBOX_TTL", DEFAULT_TTL_SECONDS)),
        help=f"Session TTL in seconds. Default: {DEFAULT_TTL_SECONDS}.",
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
        "--snapshot-page-size",
        type=int,
        default=100,
        help="Page size when listing snapshots. Default: 100.",
    )
    parser.add_argument(
        "--no-tos-mount-points",
        action="store_true",
        help="Do not copy TOS mount points from the tool when creating a session.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    positional = list(args.positional)

    tool_id = args.tool_id or (positional.pop(0) if positional else "")
    session_id = args.session_id or (positional.pop(0) if positional else "")

    if positional:
        raise SystemExit(f"Unexpected positional arguments: {' '.join(positional)}")
    if not tool_id:
        raise SystemExit("--tool-id is required")
    if not session_id:
        raise SystemExit("--session-id is required")
    if args.ttl <= 0:
        raise SystemExit("--ttl must be a positive integer")
    if args.snapshot_page_size <= 0:
        raise SystemExit("--snapshot-page-size must be a positive integer")

    result = ensure_session(
        tool_id=tool_id.strip(),
        session_id=session_id.strip(),
        ttl=args.ttl,
        region=args.region.strip(),
        access_key=args.access_key.strip(),
        secret_key=args.secret_key.strip(),
        session_token=args.session_token.strip(),
        snapshot_page_size=args.snapshot_page_size,
        include_tos_mount_points=not args.no_tos_mount_points,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
