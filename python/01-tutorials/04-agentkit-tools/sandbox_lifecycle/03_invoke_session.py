#!/usr/bin/env python3
"""Run Python code in the sandbox session recorded in the lifecycle state."""

from __future__ import annotations

import json
import os

from pydantic import BaseModel, ConfigDict, Field

from _common import (
    load_state,
    model_to_dict,
    new_data_plane_client,
    positive_int_env,
    print_json,
    require_string,
    resolve_tool_id,
    save_state,
    state_path,
    utc_now,
)


class InvokeToolRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tool_id: str = Field(alias="ToolId")
    session_id: str = Field(alias="SessionId")
    operation_type: str = Field(default="RunCode", alias="OperationType")
    operation_payload: str = Field(alias="OperationPayload")


class InvokeToolResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    session_id: str = Field(alias="SessionId")
    result: str = Field(alias="Result")


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

    # SDK 0.8.7 has no generated InvokeTool method. Register the action while
    # reusing its signing, credential refresh, and API error handling.
    client = new_data_plane_client("InvokeTool")

    response = client._invoke_api(
        api_action="InvokeTool",
        request=InvokeToolRequest(
            tool_id=tool_id,
            session_id=instance_id,
            operation_payload=json.dumps(payload, ensure_ascii=False),
        ),
        response_type=InvokeToolResponse,
    )
    if response.session_id != instance_id:
        raise RuntimeError(
            f"InvokeTool returned unexpected SessionId {response.session_id!r}; "
            f"expected {instance_id}"
        )

    try:
        result = json.loads(response.result)
    except json.JSONDecodeError:
        result = response.result
    state.update(
        {
            "invoked_at": utc_now(),
            "invoke_response": model_to_dict(response),
            "invoke_result": result,
        }
    )
    save_state(state)
    print_json({"state_file": str(state_path()), **state})

    # An accepted API request can still contain a Python execution error.
    if isinstance(result, dict):
        data = result.get("data")
        if result.get("success") is False or (
            isinstance(data, dict) and data.get("status") == "error"
        ):
            raise RuntimeError("RunCode failed; see invoke_result in the output")


if __name__ == "__main__":
    main()
