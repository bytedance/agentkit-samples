#!/usr/bin/env python3
"""List every snapshot under the tool, then get the newly created snapshot."""

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
)


def main() -> None:
    state = load_state()
    tool_id = resolve_tool_id(state)
    snapshot_id = require_string(state, "snapshot_id")
    client = new_client()

    snapshots = list_all_snapshots(client, tool_id)
    listed_ids = {item.get("SnapshotId") for item in snapshots}
    if snapshot_id not in listed_ids:
        raise RuntimeError(
            f"new snapshot {snapshot_id} was not returned by ListSessionSnapshots"
        )

    response = client.get_session_snapshot(
        tools_types.GetSessionSnapshotRequest(
            tool_id=tool_id,
            snapshot_id=snapshot_id,
        )
    )
    if response.snapshot is None:
        raise RuntimeError("GetSessionSnapshot response is missing Snapshot")

    state.update(
        {
            "snapshots_listed_at": utc_now(),
            "listed_snapshot_count": len(snapshots),
            "snapshot": model_to_dict(response),
        }
    )
    save_state(state)
    print_json(
        {
            "state_file": str(state_path()),
            "all_tool_snapshots": snapshots,
            "new_snapshot": model_to_dict(response),
        }
    )


if __name__ == "__main__":
    main()
