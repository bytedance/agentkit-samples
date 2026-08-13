#!/usr/bin/env python3
"""Create an eight-hour sandbox session and record its instance ID."""

from __future__ import annotations

import os
import uuid

from agentkit.sdk.tools import types as tools_types

from _common import (
    model_to_dict,
    new_client,
    print_json,
    resolve_tool_id,
    save_state,
    state_path,
    ttl_seconds,
    utc_now,
    wait_for_session,
)


def main() -> None:
    tool_id = resolve_tool_id()
    ttl = ttl_seconds()
    user_session_id = os.getenv("AGENTKIT_USER_SESSION_ID", "").strip()
    if not user_session_id:
        user_session_id = f"snapshot-demo-{uuid.uuid4().hex[:16]}"

    client = new_client()
    tool = client.get_tool(tools_types.GetToolRequest(tool_id=tool_id))
    if tool.enable_snapshot is not True:
        raise RuntimeError(
            f"tool {tool_id} does not have EnableSnapshot=true; "
            "snapshots cannot be created for this tool"
        )

    response = client.create_session(
        tools_types.CreateSessionRequest(
            tool_id=tool_id,
            ttl=ttl,
            ttl_unit="second",
            user_session_id=user_session_id,
        )
    )
    instance_id = (response.session_id or "").strip()
    if not instance_id:
        raise RuntimeError("CreateSession response is missing SessionId")

    state = {
        "tool_id": tool_id,
        "user_session_id": response.user_session_id or user_session_id,
        "instance_id": instance_id,
        "ttl_seconds": ttl,
        "created_at": utc_now(),
        "create_response": model_to_dict(response),
    }
    save_state(state)

    session = wait_for_session(client, tool_id, instance_id)
    state["session"] = model_to_dict(session)
    save_state(state)
    print_json({"state_file": str(state_path()), **state})


if __name__ == "__main__":
    main()
