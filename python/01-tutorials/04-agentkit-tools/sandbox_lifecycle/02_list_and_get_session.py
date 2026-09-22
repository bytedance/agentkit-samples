#!/usr/bin/env python3
"""List every session under a tool and get the selected session's details."""

from __future__ import annotations

import os

from agentkit.sdk.tools import types as tools_types

from _common import (
    list_all_sessions,
    load_state,
    model_to_dict,
    new_client,
    print_json,
    require_string,
    resolve_tool_id,
    state_path,
)


def main() -> None:
    state = load_state() if state_path().is_file() else {}
    tool_id = resolve_tool_id(state)
    session_id = os.getenv("AGENTKIT_SESSION_ID", "").strip()
    if not session_id and "instance_id" in state:
        session_id = require_string(state, "instance_id")

    client = new_client()
    sessions = list_all_sessions(client, tool_id)
    session = None
    if session_id:
        response = client.get_session(
            tools_types.GetSessionRequest(
                tool_id=tool_id,
                session_id=session_id,
            )
        )
        if response.session_id != session_id:
            raise RuntimeError(
                f"GetSession returned unexpected SessionId {response.session_id!r}; "
                f"expected {session_id}"
            )
        session = model_to_dict(response)

    print_json(
        {
            "tool_id": tool_id,
            "listed_session_count": len(sessions),
            "all_tool_sessions": sessions,
            "session": session,
        }
    )


if __name__ == "__main__":
    main()
