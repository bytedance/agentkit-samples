#!/usr/bin/env python3
"""Delete the session's sandbox instance while retaining its snapshot."""

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
)


def main() -> None:
    state = load_state()
    tool_id = resolve_tool_id(state)
    instance_id = require_string(state, "instance_id")
    require_string(state, "snapshot_id")
    client = new_client()

    response = client.delete_session(
        tools_types.DeleteSessionRequest(
            tool_id=tool_id,
            session_id=instance_id,
        )
    )
    deleted_id = (response.session_id or instance_id).strip()
    if deleted_id != instance_id:
        raise RuntimeError(
            f"DeleteSession returned unexpected SessionId {deleted_id}; "
            f"expected {instance_id}"
        )

    state.update(
        {
            "deleted_at": utc_now(),
            "delete_response": model_to_dict(response),
        }
    )
    save_state(state)
    print_json({"state_file": str(state_path()), **state})


if __name__ == "__main__":
    main()
