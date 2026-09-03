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

"""Remote registry skills executed through a Skills Sandbox.

Flow:
    runtime Agent (skills=[ss-xxx], tools=[execute_skills])
        -> execute_skills
        -> Skills Sandbox A2A
        -> sandbox VeADK Agent executes remote skills

The runtime Agent intentionally exposes only ``execute_skills``. It does not
mount ``run_code`` or any local bash/code execution tool.

Example:
    python3 advanced/a2a/runtime_to_skills_sandbox_execute.py \
        --tool-id t-yes0m2osg0k6ee1en4ke \
        --skill-space-id ss-xxxxxxxx \
        --session-id remote-skills-demo-session \
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
from veadk import Agent, Runner
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.tools.builtin_tools.execute_skills import execute_skills

SOURCE = "runtime-to-skills-sandbox-execute"
DEFAULT_APP_NAME = "remote_skills_runtime_agent"
DEFAULT_USER_ID = "remote_skills_user"
SANDBOX_PROFILE = "skill"
TOOL_ID_ENV = "AGENTKIT_TOOL_ID_SKILLS"
REMOTE_SKILLS_INSTRUCTION_CN = """
你是一个技能执行小助手，但你不能直接执行技能，只能调用 execute_skills 工具。
所以你收到请求后，你需要先调用 execute_skills 工具，才能完成任务。
在调用 execute_skills 时，将用户的请求作为参数传入，由 skills sandbox 中的 Agent 具体执行技能。
即使用户只是询问当前有哪些技能，也不要直接根据上下文中的技能描述回答，必须先调用 execute_skills。
"""
REMOTE_SKILLS_INSTRUCTION_EN = """
You are a skill execution assistant. You cannot execute skills directly; you can only use the execute_skills tool.
When you receive a request, you must first call the execute_skills tool to complete the task.
When calling execute_skills, pass the user's request as a parameter, and the Agent in the skills sandbox will execute the skills.
Even if the user only asks what skills are available, do not answer directly from the skills listed in context; call execute_skills first.
"""


def _build_parser() -> argparse.ArgumentParser:
    """Build CLI arguments for the execute_skills runtime Agent."""
    parser = argparse.ArgumentParser(
        description=(
            "Run a runtime Agent that delegates remote-registry skill execution "
            "to a Skills Sandbox via execute_skills."
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

    instruction = (
        REMOTE_SKILLS_INSTRUCTION_EN
        if args.language == "en"
        else REMOTE_SKILLS_INSTRUCTION_CN
    )
    agent = Agent(
        name="remote_skills_runtime_agent",
        model_name=args.model_name,
        instruction=instruction,
        skills=[skill_space_id],
        skills_mode="skills_sandbox",
        tools=[execute_skills],
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
