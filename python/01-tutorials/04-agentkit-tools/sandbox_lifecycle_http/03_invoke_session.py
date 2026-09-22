#!/usr/bin/env python3
"""Run Python code in the sandbox session recorded in the lifecycle state."""

from __future__ import annotations

import json
import os

from _common import (
    load_state,
    model_to_dict,
    new_client,
    positive_int_env,
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
    payload = {
        "code": os.getenv(
            "AGENTKIT_INVOKE_CODE", "print('Hello from AgentKit sandbox!')"
        ),
        "timeout": positive_int_env("AGENTKIT_INVOKE_TIMEOUT_SECONDS", 30),
        "kernel_name": os.getenv("AGENTKIT_INVOKE_KERNEL_NAME", "").strip()
        or "python3",
    }

    client = new_client()
    response = client.invoke_tool(
        {
            "ToolId": tool_id,
            "SessionId": instance_id,
            "OperationType": "RunCode",
            "OperationPayload": json.dumps(payload, ensure_ascii=False),
        }
    )
    response_session_id = str(response.get("SessionId") or "").strip()
    if response_session_id != instance_id:
        raise RuntimeError(
            f"InvokeTool returned unexpected SessionId {response_session_id!r}; "
            f"expected {instance_id}"
        )

    raw_result = response.get("Result")
    try:
        result = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
    except json.JSONDecodeError:
        result = raw_result

    state.update(
        {
            "invoked_at": utc_now(),
            "invoke_response": model_to_dict(response),
            "invoke_result": result,
        }
    )
    save_state(state)
    print_json({"state_file": str(state_path()), **state})

    if isinstance(result, dict):
        data = result.get("data")
        if result.get("success") is False or (
            isinstance(data, dict) and data.get("status") == "error"
        ):
            raise RuntimeError("RunCode failed; see invoke_result in the output")


if __name__ == "__main__":
    main()
