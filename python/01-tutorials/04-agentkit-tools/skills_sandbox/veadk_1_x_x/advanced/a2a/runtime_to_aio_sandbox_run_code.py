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

"""Remote registry skills with code execution in an AIO sandbox.

Flow:
    runtime Agent (SkillToolset remote registry + run_code)
        -> remote skills are loaded into the runtime
        -> run_code executes Python or shell commands in the AIO/script sandbox

This sample does not use ``execute_skills``. Skills are discovered from the
remote Skill Space through ``SkillToolset``. Whenever the workflow needs code or
shell execution, the runtime Agent must call ``run_code``.

Example:
    python3 advanced/a2a/runtime_to_aio_sandbox_run_code.py \
        --tool-id t-yes0m2osg0k6ee1en4ke \
        --skill-space-id ss-xxxxxxxx \
        --session-id aio-skills-demo-session \
        --prompt "请用 Python 打印 Hello World 并执行"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

from agentkit.toolkit.cli.sandbox.cli_invoke import _error_payload
from google.adk.agents.invocation_context import InvocationContext
from google.adk.code_executors.base_code_executor import BaseCodeExecutor
from google.adk.code_executors.code_execution_utils import (
    CodeExecutionInput,
    CodeExecutionResult,
)
from google.adk.tools import ToolContext
from google.adk.tools.skill_toolset import SkillToolset
from veadk import Agent, Runner
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.skills import VeSkillRegistry
from veadk.tools.builtin_tools.run_code import run_code

SOURCE = "runtime-to-aio-sandbox-run-code"
DEFAULT_APP_NAME = "aio_skills_runtime_agent"
DEFAULT_USER_ID = "aio_skills_user"
SANDBOX_PROFILE = "skill"
TOOL_ID_ENV = "AGENTKIT_TOOL_ID_SCRIPT"
AIO_SKILLS_INSTRUCTION_CN = """
你是一个技能执行小助手，你有 run_code 工具。
假设你需要执行 skills 来完成任务，在执行 skills 过程中，如果有需要跑的代码、执行一些 shell 命令，需要调用 run_code 工具来完成。
执行 skills 时可以结合 SkillToolset 加载远程技能，在技能执行流程中遇到代码或命令执行场景时，优先使用 run_code 在 AIO sandbox 中安全执行。
"""
AIO_SKILLS_INSTRUCTION_EN = """
You are a skill execution assistant, and you have the run_code tool.
If you need to execute skills to complete a task, during skill execution, if you need to run code or execute shell commands, you must use the run_code tool.
When executing skills, you can use SkillToolset to load remote skills. When encountering code or command execution scenarios in the skill execution flow, prioritize using run_code for safe execution in the AIO sandbox.
"""
DEFAULT_CODE_TIMEOUT_SECONDS = 300


class AgentKitRunCodeExecutor(BaseCodeExecutor):
    """Route SkillToolset script execution through AgentKit run_code."""

    def execute_code(
        self,
        invocation_context: InvocationContext,
        code_execution_input: CodeExecutionInput,
    ) -> CodeExecutionResult:
        timeout = min(self.timeout_seconds or DEFAULT_CODE_TIMEOUT_SECONDS, 300)
        output = run_code(
            code=code_execution_input.code,
            language="python3",
            tool_context=ToolContext(invocation_context),
            timeout=timeout,
            hard_timeout=timeout,
        )
        if isinstance(output, str):
            return CodeExecutionResult(stdout=output)
        return CodeExecutionResult(stdout=json.dumps(output, ensure_ascii=False))


def _build_parser() -> argparse.ArgumentParser:
    """Build CLI arguments for the run_code runtime Agent."""
    parser = argparse.ArgumentParser(
        description=(
            "Run a runtime Agent that loads remote-registry skills and uses "
            "run_code for AIO/script sandbox execution."
        ),
    )
    parser.add_argument(
        "--sandbox-profile",
        choices=(SANDBOX_PROFILE,),
        default=SANDBOX_PROFILE,
        help="Compatibility option. This sample uses the skill/AIO sandbox profile.",
    )
    parser.add_argument(
        "--tool-id",
        default=os.getenv(TOOL_ID_ENV) or os.getenv("AGENTKIT_TOOL_ID"),
        help=(
            "AIO/script Sandbox Tool ID. Defaults to AGENTKIT_TOOL_ID_SCRIPT, "
            "then AGENTKIT_TOOL_ID."
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
        help="Runtime Agent session ID. The AIO sandbox session is derived from it.",
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

    registry = VeSkillRegistry(skill_source_id=skill_space_id)
    skill_toolset = SkillToolset(
        registry=registry,
        code_executor=AgentKitRunCodeExecutor(),
    )
    instruction = (
        AIO_SKILLS_INSTRUCTION_EN
        if args.language == "en"
        else AIO_SKILLS_INSTRUCTION_CN
    )
    agent = Agent(
        name="aio_skills_runtime_agent",
        model_name=args.model_name,
        instruction=instruction,
        tools=[skill_toolset, run_code],
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
