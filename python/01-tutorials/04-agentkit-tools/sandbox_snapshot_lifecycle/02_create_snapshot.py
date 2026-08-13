#!/usr/bin/env python3
"""Actively create a snapshot for the session's sandbox instance."""

from __future__ import annotations

from agentkit.sdk.tools import types as tools_types

from _common import (
    load_state,
    model_to_dict,
    new_client,
    print_json,
    require_string,
    resolve_tool_id,
    save_state,
    state_path,
    utc_now,
    wait_for_snapshot,
)


def main() -> None:
    state = load_state()
    tool_id = resolve_tool_id(state)
    instance_id = require_string(state, "instance_id")
    client = new_client()

    response = client.create_session_snapshot(
        tools_types.CreateSessionSnapshotRequest(
            tool_id=tool_id,
            session_id=instance_id,
        )
    )
    snapshot_id = (response.snapshot_id or "").strip()
    if not snapshot_id:
        raise RuntimeError("CreateSessionSnapshot response is missing SnapshotId")

    state.update(
        {
            "snapshot_id": snapshot_id,
            "snapshot_requested_at": utc_now(),
            "create_snapshot_response": model_to_dict(response),
        }
    )
    save_state(state)

    snapshot = wait_for_snapshot(client, tool_id, snapshot_id)
    state["snapshot"] = model_to_dict(snapshot)
    save_state(state)
    print_json({"state_file": str(state_path()), **state})


if __name__ == "__main__":
    main()
