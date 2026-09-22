#!/usr/bin/env python3
"""Restore the sandbox with the same instance ID after its lifecycle ends.

Let the original session expire naturally. DeleteSession also deletes its
snapshots, so it must only be used for final cleanup in step 06.
"""

from __future__ import annotations

from agentkit.sdk.tools import types as tools_types

from _common import (
    load_state,
    model_to_dict,
    new_client,
    print_json,
    require_string,
    resolve_tool_id,
    retry_on_exception,
    save_state,
    state_path,
    ttl_seconds,
    utc_now,
    wait_for_session,
)


def main() -> None:
    state = load_state()
    tool_id = resolve_tool_id(state)
    snapshot_id = require_string(state, "snapshot_id")
    original_instance_id = require_string(state, "instance_id")
    if state.get("deleted_at") or state.get("snapshot_deleted_at"):
        raise RuntimeError(
            "the session or snapshot has already been deleted; "
            "start a new lifecycle from 01_create_session.py"
        )

    ttl = ttl_seconds()
    client = new_client()
    request = tools_types.ResumeSessionFromSnapshotRequest(
        tool_id=tool_id,
        snapshot_id=snapshot_id,
        ttl=ttl,
        create_new_instance=False,
    )
    # The backend decides when restoration is allowed. An active instance or
    # one still terminating after TTL expiry cannot be restored yet.
    response = retry_on_exception(
        f"session {original_instance_id} to expire and finish terminating",
        lambda: client.resume_session_from_snapshot(request),
        lambda exc: any(
            code in str(exc)
            for code in (
                "InvalidSnapshot.InstanceAlreadyExists",
                "InvalidSnapshot.InstanceTerminating",
            )
        ),
    )
    restored_instance_id = (response.session_id or "").strip()
    if not restored_instance_id:
        raise RuntimeError("ResumeSessionFromSnapshot response is missing SessionId")
    if restored_instance_id != original_instance_id:
        raise RuntimeError(
            "backend did not preserve the sandbox instance ID: "
            f"expected {original_instance_id}, got {restored_instance_id}"
        )

    state.update(
        {
            "restored_at": utc_now(),
            "restored_instance_id": restored_instance_id,
            "restored_ttl_seconds": ttl,
            "resume_response": model_to_dict(response),
        }
    )
    save_state(state)

    session = wait_for_session(client, tool_id, restored_instance_id)
    state["restored_session"] = model_to_dict(session)
    save_state(state)
    print_json({"state_file": str(state_path()), **state})


if __name__ == "__main__":
    main()
