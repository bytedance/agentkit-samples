#!/usr/bin/env python3
#
# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Remote registry skills executed through async Skills Sandbox tools.

Flow:
    runtime Agent (SkillToolset remote registry + invoke_skill + poll_skill)
        -> invoke_skill creates a non-blocking Skills Sandbox A2A task
        -> poll_skill fetches task snapshots until the sandbox task completes
        -> sandbox VeADK Agent executes remote skills

This sample differs from ``runtime_to_skills_sandbox_execute.py``:
    * ``execute_skills`` is synchronous and waits for the final result.
    * ``invoke_skill`` + ``poll_skill`` exposes non-blocking A2A task control
      to the runtime Agent.

Example:
    python3 advanced/a2a/runtime_to_skills_sandbox_invoke_poll.py \
        --tool-id t-yes0m2osg0k6ee1en4ke \
        --skill-space-id ss-xxxxxxxx \
        --session-id remote-skills-poll-demo-session \
        --prompt "你有哪些技能"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

from agentkit.toolkit.cli.sandbox.cli_invoke import _error_payload
from google.adk.tools.skill_toolset import SkillToolset
from veadk import Agent, Runner
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.skills import VeSkillRegistry
from veadk.tools.builtin_tools.invoke_skill import invoke_skill
from veadk.tools.builtin_tools.poll_skill import poll_skill

SOURCE = "runtime-to-skills-sandbox-invoke-poll"
DEFAULT_APP_NAME = "remote_skills_invoke_poll_runtime_agent"
DEFAULT_USER_ID = "remote_skills_invoke_poll_user"
SANDBOX_PROFILE = "skill"
TOOL_ID_ENV = "AGENTKIT_TOOL_ID_SKILLS"
REMOTE_SKILLS_INVOKE_POLL_INSTRUCTION_CN = """
你是一个技能执行小助手。
你可以使用 SkillToolset 查询远程 Skill Space 中有哪些技能，但你不能在 runtime 本地直接执行技能。
凡是需要执行技能、查询技能能力或让远端技能完成任务，都必须先调用 invoke_skill 创建 Skills Sandbox A2A 任务。
invoke_skill 返回 task_id 后，你必须继续调用 poll_skill 查询同一个 task_id，直到任务进入 completed、failed 或 canceled 等终态。
如果任务完成，基于 poll_skill 返回的最终结果答复用户；如果任务失败或取消，说明最终状态和错误信息。
不要要求用户提供 task_id；task_id 必须来自你刚刚调用 invoke_skill 的返回结果。
"""
REMOTE_SKILLS_INVOKE_POLL_INSTRUCTION_EN = """
You are a skill execution assistant.
You may use SkillToolset to inspect skills from the remote Skill Space, but you must not execute skills locally in the runtime.
For any request that needs skill execution, skill capability lookup, or a remote skill result, first call invoke_skill to create a Skills Sandbox A2A task.
After invoke_skill returns a task_id, keep calling poll_skill with the same task_id until the task reaches a terminal state such as completed, failed, or canceled.
If the task completes, answer from the final poll_skill result. If it fails or is canceled, explain the final state and error.
Do not ask the user for a task_id; use the task_id returned by your invoke_skill call.
"""


def _build_parser() -> argparse.ArgumentParser:
    """Build CLI arguments for the invoke/poll runtime Agent."""
    parser = argparse.ArgumentParser(
        description=(
            "Run a runtime Agent that delegates remote-registry skill execution "
            "to a Skills Sandbox via invoke_skill and poll_skill."
        ),
    )
    parser.add_argument(
        "--sandbox-profile",
        choices=(SANDBOX_PROFILE,),
        default=SANDBOX_PROFILE,
        help="Compatibility option. This sample uses the skill sandbox profile.",
    )
    parser.add_argument(
        "--tool-id",
        default=os.getenv(TOOL_ID_ENV) or os.getenv("AGENTKIT_TOOL_ID"),
        help=(
            "Skills Sandbox Tool ID. Defaults to AGENTKIT_TOOL_ID_SKILLS, then "
            "AGENTKIT_TOOL_ID."
        ),
    )
    parser.add_argument(
        "--skill-space-id",
        default=os.getenv("SKILL_SPACE_ID"),
        help="Remote Skill Space ID, usually starting with ss-.",
    )
    parser.add_argument(
        "--session-id",
        required=True,
        help="Runtime Agent session ID. The sandbox session is derived from it.",
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="User request sent to the runtime Agent.",
    )
    parser.add_argument(
        "--app-name",
        default=DEFAULT_APP_NAME,
        help="Runtime Agent app name.",
    )
    parser.add_argument(
        "--user-id",
        default=DEFAULT_USER_ID,
        help="Runtime Agent user ID.",
    )
    parser.add_argument(
        "--model-name",
        default=os.getenv("MODEL_AGENT_NAME", "deepseek-v4-pro-260425"),
        help="Runtime Agent model name.",
    )
    parser.add_argument(
        "--language",
        choices=("zh", "en"),
        default="zh",
        help="Runtime Agent system prompt language.",
    )
    return parser


def _required_arg(value: str | None, option: str) -> str:
    resolved = (value or "").strip()
    if not resolved:
        raise ValueError(f"{option} is required")
    return resolved


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump(exclude_none=True))
    if hasattr(value, "dict"):
        return _jsonable(value.dict())
    return str(value)


def _set_tool_id_env(tool_id: str) -> None:
    os.environ[TOOL_ID_ENV] = tool_id
    os.environ.setdefault("AGENTKIT_TOOL_ID", tool_id)


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    prompt = _required_arg(args.prompt, "--prompt")
    tool_id = _required_arg(args.tool_id, "--tool-id")
    skill_space_id = _required_arg(args.skill_space_id, "--skill-space-id")
    _set_tool_id_env(tool_id)

    skill_toolset = SkillToolset(
        registry=VeSkillRegistry(skill_source_id=skill_space_id),
    )
    instruction = (
        REMOTE_SKILLS_INVOKE_POLL_INSTRUCTION_EN
        if args.language == "en"
        else REMOTE_SKILLS_INVOKE_POLL_INSTRUCTION_CN
    )
    agent = Agent(
        name="remote_skills_invoke_poll_runtime_agent",
        model_name=args.model_name,
        instruction=instruction,
        tools=[skill_toolset, invoke_skill, poll_skill],
    )
    runner = Runner(
        agent=agent,
        short_term_memory=ShortTermMemory(backend="local"),
        app_name=args.app_name,
        user_id=args.user_id,
    )

    response = await runner.run(messages=prompt, session_id=args.session_id)
    return {
        "ok": True,
        "source": SOURCE,
        "app_name": args.app_name,
        "user_id": args.user_id,
        "session_id": args.session_id,
        "tool_id": tool_id,
        "skill_space_id": skill_space_id,
        "response": _jsonable(response),
    }


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments, run the runtime Agent, and print JSON output."""
    args = _build_parser().parse_args(argv)
    try:
        output = asyncio.run(_run(args))
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(
            json.dumps(_error_payload(exc), ensure_ascii=False, indent=2),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
