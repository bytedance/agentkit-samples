#!/usr/bin/env python3
"""Delete the lifecycle snapshot and confirm it disappears from the tool."""

from __future__ import annotations

from agentkit.sdk.tools import types as tools_types

from _common import (
    list_all_snapshots,
    load_state,
    model_to_dict,
    new_client,
    print_json,
    require_string,
    resolve_tool_id,
    save_state,
    state_path,
    utc_now,
    wait_until,
)


def main() -> None:
    state = load_state()
    tool_id = resolve_tool_id(state)
    snapshot_id = require_string(state, "snapshot_id")
    client = new_client()

    response = client.delete_session_snapshot(
        tools_types.DeleteSessionSnapshotRequest(
            tool_id=tool_id,
            snapshot_id=snapshot_id,
        )
    )
    deleted_id = (response.snapshot_id or snapshot_id).strip()
    if deleted_id != snapshot_id:
        raise RuntimeError(
            f"DeleteSessionSnapshot returned unexpected SnapshotId {deleted_id}; "
            f"expected {snapshot_id}"
        )

    state.update(
        {
            "snapshot_deleted_at": utc_now(),
            "delete_snapshot_response": model_to_dict(response),
        }
    )
    save_state(state)

    remaining = wait_until(
        f"snapshot {snapshot_id} to disappear from the tool",
        lambda: list_all_snapshots(client, tool_id),
        lambda snapshots: snapshot_id
        not in {item.get("SnapshotId") for item in snapshots},
        lambda _snapshots: False,
    )
    state["snapshot_delete_verified_at"] = utc_now()
    save_state(state)
    print_json(
        {
            "state_file": str(state_path()),
            "deleted_snapshot_id": snapshot_id,
            "remaining_tool_snapshots": remaining,
        }
    )


if __name__ == "__main__":
    main()
