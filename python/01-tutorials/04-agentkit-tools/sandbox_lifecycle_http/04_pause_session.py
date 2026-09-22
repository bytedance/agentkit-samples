#!/usr/bin/env python3
"""Pause the sandbox session recorded in the lifecycle state via HTTP."""

from __future__ import annotations

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
    wait_for_paused_session,
)


def main() -> None:
    state = load_state()
    tool_id = resolve_tool_id(state)
    instance_id = require_string(state, "instance_id")
    client = new_client()

    response = client.pause_session(
        {
            "ToolId": tool_id,
            "SessionId": instance_id,
        }
    )
    response_session_id = str(response.get("SessionId") or instance_id).strip()
    if response_session_id != instance_id:
        raise RuntimeError(
            f"PauseSession returned unexpected SessionId {response_session_id}; "
            f"expected {instance_id}"
        )

    state.update(
        {
            "pause_requested_at": utc_now(),
            "pause_response": model_to_dict(response),
        }
    )
    save_state(state)

    session = wait_for_paused_session(client, tool_id, instance_id)
    state.update(
        {
            "paused_at": utc_now(),
            "paused_session": model_to_dict(session),
        }
    )
    save_state(state)
    print_json({"state_file": str(state_path()), **state})


if __name__ == "__main__":
    main()
