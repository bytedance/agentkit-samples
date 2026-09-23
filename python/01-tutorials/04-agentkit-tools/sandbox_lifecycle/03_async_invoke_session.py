#!/usr/bin/env python3
"""Submit a Shell command in the saved session and poll its asynchronous result."""

from __future__ import annotations

import argparse
import os
import time

from pydantic import BaseModel, ConfigDict, Field

from _common import (
    load_state,
    model_to_dict,
    new_data_plane_client,
    positive_int_env,
    redact_sensitive_values,
    require_string,
    resolve_tool_id,
    save_state,
    state_path,
    utc_now,
)


class AsyncExecCommandRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tool_id: str = Field(alias="ToolId")
    session_id: str = Field(alias="SessionId")
    command: str = Field(alias="Command", min_length=1)
    exec_dir: str | None = Field(default=None, alias="ExecDir")


class ViewAsyncCommandRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tool_id: str = Field(alias="ToolId")
    session_id: str = Field(alias="SessionId")
    task_id: str = Field(alias="TaskId", min_length=1)


class AsyncCommandResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    tool_id: str = Field(alias="ToolId")
    session_id: str = Field(alias="SessionId")
    task_id: str = Field(alias="TaskId", min_length=1)
    status: str = Field(alias="Status")
    output: str | None = Field(default=None, alias="Output")
    # ExitCode is not meaningful while Running and is absent on submission.
    exit_code: int | None = Field(default=None, alias="ExitCode")


def validate_target(
    response: AsyncCommandResponse,
    tool_id: str,
    session_id: str,
    task_id: str | None = None,
) -> None:
    if response.tool_id != tool_id or response.session_id != session_id:
        raise RuntimeError("API returned an unexpected ToolId or SessionId")
    if not response.task_id.strip():
        raise RuntimeError("API returned an empty TaskId")
    if task_id is not None and response.task_id != task_id:
        raise RuntimeError("ViewAsyncCommand returned an unexpected TaskId")


def print_line(message: str) -> None:
    print(redact_sensitive_values(message), flush=True)


def print_stage(title: str) -> None:
    print_line(f"\n{'*' * 16} {title} {'*' * 16}")


def print_result(response: AsyncCommandResponse, title: str) -> None:
    print_stage(f"[3/3] {title}")
    exit_code = (
        "尚未生效"
        if response.status.strip().lower() == "running"
        else response.exit_code
    )
    print_line(f"- Status={response.status} | ExitCode={exit_code}")
    print_line("---------------- 命令输出 (stdout + stderr) ----------------")
    print_line(response.output or "（无输出）")
    print_line("---------------- 完整状态文件 ----------------")
    print_line(str(state_path()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--view-only",
        action="store_true",
        help="poll the saved async_task_id without submitting another command",
    )
    args = parser.parse_args()
    state = load_state()
    tool_id = resolve_tool_id(state)
    instance_id = require_string(state, "instance_id")
    timeout = positive_int_env("AGENTKIT_ASYNC_WAIT_TIMEOUT_SECONDS", 600)
    interval = positive_int_env("AGENTKIT_ASYNC_POLL_INTERVAL_SECONDS", 2)
    client = new_data_plane_client("AsyncExecCommand", "ViewAsyncCommand")

    if args.view_only:
        task_id = require_string(state, "async_task_id")
        print_stage("[1/3] 读取已有任务（仅查询，不提交）")
    else:
        command = os.getenv(
            "AGENTKIT_ASYNC_COMMAND", "sleep 20 && echo 'Hello from AgentKit sandbox!'"
        )
        if not command.strip():
            raise RuntimeError("AGENTKIT_ASYNC_COMMAND must not be empty")
        print_stage("[1/3] 提交异步任务 (AsyncExecCommand)")
        print_line(f"- Command: {command}")
        response = client._invoke_api(
            api_action="AsyncExecCommand",
            request=AsyncExecCommandRequest(
                tool_id=tool_id,
                session_id=instance_id,
                command=command,
                exec_dir=os.getenv("AGENTKIT_ASYNC_EXEC_DIR", "").strip() or None,
            ),
            response_type=AsyncCommandResponse,
        )
        validate_target(response, tool_id, instance_id)
        task_id = response.task_id
        # Save the task before polling so an interrupted wait can be resumed.
        state.pop("async_view_response", None)
        state.pop("async_viewed_at", None)
        state.update(
            {
                "async_task_id": task_id,
                "async_invoked_at": utc_now(),
                "async_invoke_response": model_to_dict(response),
            }
        )
        save_state(state)
        print_line(f"- 提交状态: {response.status}")

    print_line(f"- ToolId: {tool_id}")
    print_line(f"- SessionId: {instance_id}")
    print_line(f"- TaskId: {task_id}")
    print_line(f"- 状态文件: {state_path()}")
    print_stage("[2/3] 轮询执行结果 (ViewAsyncCommand)")
    print_line(f"- 查询间隔: {interval}s | 本地等待超时: {timeout}s")
    started_at = time.monotonic()
    deadline = started_at + timeout
    poll_count = 0
    while True:
        poll_count += 1
        response = client._invoke_api(
            api_action="ViewAsyncCommand",
            request=ViewAsyncCommandRequest(
                tool_id=tool_id, session_id=instance_id, task_id=task_id
            ),
            response_type=AsyncCommandResponse,
        )
        validate_target(response, tool_id, instance_id, task_id)
        state.update(
            {
                "async_viewed_at": utc_now(),
                "async_view_response": model_to_dict(response),
            }
        )
        save_state(state)
        status = response.status.strip().lower()
        now = time.monotonic()
        print_line(
            f"- 第 {poll_count} 次查询 | Status={response.status} "
            f"| 已等待 {now - started_at:.1f}s"
        )
        if status != "running":
            # The API docs use Succeeded; live sandbox responses also use completed.
            # Completion alone is not success: the command must exit with code 0.
            if status in {"succeeded", "completed"} and response.exit_code == 0:
                print_result(response, "执行成功")
                return
            print_result(response, "执行失败或状态异常")
            if status == "unknown":
                raise RuntimeError(
                    f"task {task_id} is Unknown; it may not exist or may have expired"
                )
            raise RuntimeError(
                f"task {task_id} did not succeed: Status={response.status!r}, "
                f"ExitCode={response.exit_code!r}; see async_view_response"
            )
        # Running responses may contain a placeholder ExitCode; ignore it.
        remaining = deadline - now
        if remaining <= 0:
            print_result(response, "本地等待超时")
            print_line("- 远端命令未取消，可使用 --view-only 继续查询。")
            raise TimeoutError(
                f"timed out after {timeout}s waiting for task {task_id}; "
                "the remote command is not cancelled. Use --view-only to query it again"
            )
        time.sleep(min(interval, remaining))


if __name__ == "__main__":
    main()
