#!/usr/bin/env python3
"""Restore an AgentKit sandbox session from a snapshot.

Given a tool ID and snapshot ID, call ResumeSessionFromSnapshot to recover the
sandbox instance, then look up the restored session details (endpoint, TTL,
status) via GetSession and print them as JSON.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any


DEFAULT_TTL_SECONDS = 28800
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


def restore_snapshot(
    *,
    tool_id: str,
    snapshot_id: str,
    ttl: int = DEFAULT_TTL_SECONDS,
    create_new_instance: bool = False,
    region: str = "",
    access_key: str = "",
    secret_key: str = "",
    session_token: str = "",
) -> dict[str, Any]:
    _load_agentkit()
    client = AgentkitToolsClient(
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        session_token=session_token,
    )

    request_kwargs: dict[str, Any] = {
        "tool_id": tool_id,
        "snapshot_id": snapshot_id,
        "ttl": ttl,
        "create_new_instance": create_new_instance,
    }
    response = client.resume_session_from_snapshot(
        tools_types.ResumeSessionFromSnapshotRequest(**request_kwargs)
    )

    restored_instance_id = (response.session_id or "").strip()
    if not restored_instance_id:
        raise RuntimeError("ResumeSessionFromSnapshot response is missing SessionId")

    session = client.get_session(
        tools_types.GetSessionRequest(tool_id=tool_id, session_id=restored_instance_id)
    )

    result: dict[str, Any] = {
        "action": "restored_from_snapshot",
        "tool_id": tool_id,
        "snapshot_id": snapshot_id,
        "session_id": session.user_session_id or "",
        "instance_id": session.session_id or restored_instance_id,
        "endpoint": session.endpoint or None,
        "internal_endpoint": session.internal_endpoint or None,
        "status": session.status or None,
        "expire_at": session.expire_at or None,
        "created_at": session.created_at or None,
    }
    result["raw"] = {
        "resume_response": _compact_model(response),
        "session": _compact_model(session),
    }
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Restore an AgentKit sandbox session from a snapshot ID and print "
            "the recovered session info (endpoint, instance id, status, etc.)."
        )
    )
    parser.add_argument("positional", nargs="*", help="Optional: TOOL_ID SNAPSHOT_ID")
    parser.add_argument("--tool-id", help="AgentKit sandbox tool ID (required).")
    parser.add_argument("--snapshot-id", help="Snapshot ID to restore from (required).")
    parser.add_argument(
        "--ttl",
        type=int,
        default=int(os.getenv("AGENTKIT_SANDBOX_TTL", DEFAULT_TTL_SECONDS)),
        help=f"Session TTL in seconds. Default: {DEFAULT_TTL_SECONDS}.",
    )
    parser.add_argument(
        "--create-new-instance",
        action="store_true",
        help=(
            "If set, create a brand-new sandbox instance from the snapshot. "
            "Default: reuse the previous instance id."
        ),
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
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    positional = list(args.positional)

    tool_id = args.tool_id or (positional.pop(0) if positional else "")
    snapshot_id = args.snapshot_id or (positional.pop(0) if positional else "")

    if positional:
        raise SystemExit(f"Unexpected positional arguments: {' '.join(positional)}")
    if not tool_id:
        raise SystemExit("--tool-id is required")
    if not snapshot_id:
        raise SystemExit("--snapshot-id is required")
    if args.ttl <= 0:
        raise SystemExit("--ttl must be a positive integer")

    result = restore_snapshot(
        tool_id=(tool_id or "").strip(),
        snapshot_id=(snapshot_id or "").strip(),
        ttl=args.ttl,
        create_new_instance=args.create_new_instance,
        region=(args.region or "").strip(),
        access_key=(args.access_key or "").strip(),
        secret_key=(args.secret_key or "").strip(),
        session_token=(args.session_token or "").strip(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
