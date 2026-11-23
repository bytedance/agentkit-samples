#!/usr/bin/env python3
"""创建 self-hosted Environment 上的定时 Deployment。"""

from __future__ import annotations

from _clients import TopClient
from _common import emit, load_state, parser, run, update_resource
from _config import validated_config
from _deployment import (
    create_deployment,
    deployment_spec,
    ensure_self_hosted_environment,
)

DEFAULT_PROMPT = (
    "请使用 bash 工具执行 echo DEPLOYMENT_CRON_OK，然后只回复工具实际输出，不要直接猜。"
)


def _resource(state: dict, name: str) -> dict:
    value = state.get("resources", {}).get(name) or {}
    if not value.get("id"):
        raise RuntimeError(
            f"{name} is missing from state; run 01_create_resources.py first"
        )
    return value


def main() -> None:
    cli = parser(__doc__)
    cli.add_argument("--name", default="", help="Deployment 名称；默认按配置前缀生成")
    cli.add_argument("--cron", default="* * * * *", help="5 段 POSIX cron，默认每分钟")
    cli.add_argument("--timezone", default="Asia/Shanghai", help="IANA 时区")
    cli.add_argument(
        "--prompt", default=DEFAULT_PROMPT, help="每次触发的初始 user.message"
    )
    cli.add_argument(
        "--no-schedule",
        action="store_true",
        help="只创建手动触发的 Deployment，不配置 cron",
    )
    args = cli.parse_args()
    config = validated_config(require_model_key_name=True)
    client = TopClient(config.control)
    state = load_state(client)
    harness = _resource(state, "harness")
    environment = _resource(state, "environment")
    runtime = _resource(state, "runtime")
    recorded_mode = (
        str(state.get("environment_type") or "").strip().lower().replace("_", "")
    )
    if recorded_mode and recorded_mode != "selfhosted":
        raise RuntimeError(
            "Deployment Cloud mode is not supported; use a self-hosted Environment"
        )
    if not args.dry_run:
        ensure_self_hosted_environment(client, environment["id"])
    name = args.name.strip() or f"{state['names']['harness']}-deployment"
    version = harness.get("version")
    body = deployment_spec(
        name=name,
        harness_id=harness["id"],
        harness_version=version if isinstance(version, int) else None,
        environment_id=environment["id"],
        runtime_id=runtime["id"],
        ark_api_key_name=config.model_api_key_name,
        prompt=args.prompt,
        cron=None if args.no_schedule else args.cron,
        timezone=args.timezone,
        metadata={"owner": "resource-to-chat-tutorial", "mode": "deployment"},
    )
    if args.dry_run:
        emit(
            "dry_run",
            "创建 Deployment 计划",
            json_output=args.json_output,
            actions=[
                "CreateDeployment（冻结当前 Harness 版本）",
                "每次 RunDeployment / cron 触发创建新 Session 和 DeploymentRun",
                "归档前不会删除任何资源",
            ],
            request=body,
            status="dry_run（未访问网络）",
        )
        return
    created = create_deployment(client, body)
    deployment_id = created.get("DeploymentId")
    if not isinstance(deployment_id, str) or not deployment_id:
        raise RuntimeError("CreateDeployment returned no DeploymentId")
    update_resource(
        state,
        "deployment",
        {
            "id": deployment_id,
            "name": created.get("Name") or name,
            "status": created.get("Status"),
            "revision": created.get("Revision"),
            "schedule": created.get("Schedule"),
            "runtime_id": created.get("RuntimeId"),
        },
    )
    emit(
        "deployment",
        "Deployment 已创建",
        json_output=args.json_output,
        deployment_id=deployment_id,
        status=created.get("Status"),
        schedule=created.get("Schedule"),
        next="运行 05_run_deployment.py 手动触发，或等待 cron",
    )


if __name__ == "__main__":
    run(main)
