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

"""创建或复用 AIO 技能沙箱会话并通过 A2A 接口发起调用。

本脚本面向的场景：AIO 沙箱通过 `SkillToolset` + 远程注册表从 Skill Space
加载技能，同时支持 `run_code` 工具在沙箱内安全执行任意代码或 Shell 命令，
适合需要在技能执行流程中穿插代码运行的场景。

注意：本脚本使用 `skill` profile，CreateSession 时不会注入任何
环境变量；模型配置由 Skill Tool 自身负责管理，无需在客户端侧传入。

使用示例：
    python3 advanced/a2a/aio_skills_a2a_invoke.py \
        --sandbox-profile skill \
        --tool-id t-yes0m2osg0k6ee1en4ke \
        --session-id aio-skills-demo-session \
        --prompt "请用 Python 打印 Hello World 并执行"
"""

from __future__ import annotations

import argparse
import json
import sys

from agentkit.toolkit.cli.sandbox.a2a_client import (
    DEFAULT_A2A_HISTORY_LENGTH,
    DEFAULT_A2A_PATH,
    DEFAULT_A2A_POLL_INTERVAL_SECONDS,
    DEFAULT_A2A_TIMEOUT_SECONDS,
    poll_task_until_terminal,
    send_message_nonblocking,
)
from agentkit.toolkit.cli.sandbox.cli_invoke import (
    _error_payload,
    _task_output,
)
from agentkit.toolkit.cli.sandbox.session_create import ensure_sandbox_session
from agentkit.toolkit.cli.sandbox.tool_resolve import SandboxToolType

# 日志来源标识，用于在输出结果中标记脚本来源
SOURCE = "aio-skills-a2a-invoke"
# 本脚本对应 AIO 技能沙箱场景，使用 skill profile（不注入环境变量）
SANDBOX_PROFILE = "skill"


def _build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description=(
            "创建或复用 AIO 技能沙箱会话（SkillToolset 远程注册表 + run_code）"
            "，并通过 A2A 接口同步发起调用。"
        ),
    )
    parser.add_argument(
        "--sandbox-profile",
        choices=(SANDBOX_PROFILE,),
        default=SANDBOX_PROFILE,
        help="沙箱运行 profile，仅支持 skill，CreateSession 不注入环境变量。",
    )
    parser.add_argument(
        "--tool-id",
        required=True,
        help="AIO 技能沙箱对应的 Sandbox Tool ID。",
    )
    parser.add_argument(
        "--session-id",
        required=True,
        help="用户会话 ID，用于创建新沙箱实例或复用已存在的实例。",
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="发送给 AIO 技能沙箱 A2A Agent 的用户请求。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """主入口：解析参数 → 创建/复用 Session → 发送 A2A 消息 → 轮询结果 → 输出。"""
    args = _build_parser().parse_args(argv)

    # 去除首尾空白并校验 prompt 非空
    resolved_prompt = args.prompt.strip()
    if not resolved_prompt:
        print(json.dumps(_error_payload(ValueError("--prompt is required"))))
        return 1

    try:
        # 步骤 1：根据 session-id + tool-id 创建新的沙箱会话，或复用已存在的会话
        # envs=None 表示 CreateSession 不注入会话级环境变量
        session = ensure_sandbox_session(
            session_id=args.session_id,
            tool_id=args.tool_id,
            tool_type=SandboxToolType.SKILL_ENV.value,
            envs=None,
            resolve_tool=False,
            include_tos_mount_points=False,
        )

        # 步骤 2：通过 A2A 接口异步发送 prompt，获取任务 ID
        task_start = send_message_nonblocking(
            endpoint=session.get("endpoint"),
            prompt=resolved_prompt,
            a2a_path=DEFAULT_A2A_PATH,
            request_metadata={
                "session_id": str(session.get("session_id") or ""),
                "user_id": "agentkit-aio-skills-sandbox",
            },
            history_length=DEFAULT_A2A_HISTORY_LENGTH,
            timeout=min(60, DEFAULT_A2A_TIMEOUT_SECONDS),
        )

        # 步骤 3：轮询 A2A 任务，直到进入终态（成功/失败/取消）
        task = poll_task_until_terminal(
            endpoint=session.get("endpoint"),
            task_id=task_start.task_id,
            a2a_path=DEFAULT_A2A_PATH,
            history_length=DEFAULT_A2A_HISTORY_LENGTH,
            timeout=DEFAULT_A2A_TIMEOUT_SECONDS,
            interval=DEFAULT_A2A_POLL_INTERVAL_SECONDS,
        )

        # 步骤 4：格式化并打印任务结果
        output = _task_output(
            task=task,
            session=session,
            source=SOURCE,
        )
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0 if output.get("ok") else 1

    except Exception as exc:
        # 发生任何异常时，以统一 JSON 格式输出错误信息到 stderr
        print(
            json.dumps(_error_payload(exc), ensure_ascii=False, indent=2),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
