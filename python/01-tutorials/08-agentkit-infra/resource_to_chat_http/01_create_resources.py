#!/usr/bin/env python3
"""创建控制面资源、Environment API Key 和 Session。"""

import re
import sys
from dataclasses import replace

from _clients import TopClient
from _common import emit, new_state, parser, run
from _config import (
    config_path,
    validated_config,
)
from _workflow import create_resources


def choose_environment_type(mode: str | None, *, json_output: bool) -> str:
    if mode:
        return "Cloud" if mode == "cloud" else "SelfHosted"
    if json_output or not sys.stdin.isatty():
        return ""
    while True:
        try:
            answer = (
                input("是否使用 Cloud Environment？[Y/n]（n 为 SelfHosted）：")
                .strip()
                .lower()
            )
        except EOFError:
            raise RuntimeError("操作已取消，尚未创建资源") from None
        if answer in {"", "y", "yes"}:
            return "Cloud"
        if answer in {"n", "no"}:
            return "SelfHosted"
        print("请输入 y 或 n，回车默认 Cloud。", flush=True)


def main() -> None:
    cli = parser(__doc__)
    cli.add_argument(
        "--prefix",
        default="harness-chat",
        help="本轮资源名称前缀，默认 harness-chat",
    )
    cli.add_argument(
        "--endpoint-id",
        default="",
        help="账号存在多个 Endpoint 时显式选择",
    )
    cli.add_argument(
        "--model-id",
        help="模型 ID；默认读取 config.yaml",
    )
    cli.add_argument(
        "--model-base-url",
        help="模型 BaseUrl；默认读取 config.yaml",
    )
    cli.add_argument(
        "--agent-loop",
        choices=("adk", "codex", "piagent"),
        help="Harness AgentLoop；默认读取 config.yaml",
    )
    cli.add_argument(
        "--env-mode",
        choices=("cloud", "selfhost"),
        help="直接选择 Env 模式；终端运行未指定时交互选择，非交互读取 YAML",
    )
    args = cli.parse_args()

    prefix = args.prefix.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", prefix):
        cli.error("--prefix must match [a-z0-9][a-z0-9-]{0,39}")
    config = validated_config(
        environment_type=choose_environment_type(
            args.env_mode, json_output=args.json_output
        ),
        model_id=args.model_id or "",
        model_base_url=args.model_base_url or "",
        require_model_key_name=not args.dry_run,
        require_credentials=not args.dry_run,
    )
    agent_loop = args.agent_loop or config.harness.agent_loop
    if agent_loop != config.harness.agent_loop:
        config = replace(
            config,
            harness=replace(config.harness, agent_loop=agent_loop),
        )
    if args.dry_run:
        emit(
            "dry_run",
            "资源创建计划",
            json_output=args.json_output,
            actions=[
                "准备 Endpoint（选择已有或创建）",
                (
                    "创建 Cloud Environment，等待 Environment 和 Cloud Sandbox 就绪"
                    if config.environment.type == "Cloud"
                    else "创建 SelfHosted Environment，不创建或等待 Cloud Sandbox"
                ),
                "创建 Harness",
                "创建 SERVERLESS_PG SessionStore 并等待就绪",
                "准备 Runtime IAM Role（复用或创建并授权），创建 RuntimeTemplate 并等待就绪",
                "创建 Environment API Key 并保存到 config.yaml",
                "创建 Session，保存到 config.yaml 并回填两个固定 shell 脚本的连接配置",
            ],
            config_file=str(config_path()),
            model_id=config.model_id,
            model_base_url=config.model_base_url,
            role_name=config.runtime_role_name,
            agent_loop=agent_loop,
            environment_type=config.environment.type,
            status="dry_run（未创建资源，名称和 ID 尚未生成）",
        )
        return

    client = TopClient(config.control)
    state = new_state(
        client,
        prefix=prefix,
        model_id=config.model_id,
        model_base_url=config.model_base_url,
        role_name=config.runtime_role_name,
        agent_loop=agent_loop,
        environment_type=config.environment.type,
    )
    create_resources(
        client,
        state,
        config,
        endpoint_id=args.endpoint_id.strip() or config.environment.endpoint_id,
        json_output=args.json_output,
    )


if __name__ == "__main__":
    run(main)
