#!/usr/bin/env python3
"""手动触发 Deployment，并等待 SessionId 或异步派发 Error。"""

from __future__ import annotations

from _clients import TopClient
from _common import emit, load_state, parser, print_json, run, update_resource
from _config import validated_config
from _deployment import trigger_deployment, wait_for_run


def main() -> None:
    cli = parser(__doc__)
    cli.add_argument(
        "--deployment-id", default="", help="缺省读取状态文件中的 Deployment"
    )
    cli.add_argument("--no-wait", action="store_true", help="只触发，不等待 Run 结果")
    args = cli.parse_args()
    config = validated_config(require_model_key_name=False)
    client = TopClient(config.control)
    state = load_state(client)
    deployment_id = args.deployment_id.strip() or (
        (state.get("resources", {}).get("deployment") or {}).get("id") or ""
    )
    if not deployment_id:
        raise RuntimeError(
            "deployment id is missing; run 04_create_deployment.py first"
        )
    if args.dry_run:
        emit(
            "dry_run",
            "触发 Deployment 计划",
            json_output=args.json_output,
            deployment_id=deployment_id,
            actions=["RunDeployment", "等待 DeploymentRun 写入 SessionId 或 Error"],
            status="dry_run（未访问网络）",
        )
        return
    triggered = trigger_deployment(client, deployment_id)
    run_id = triggered.get("DeploymentRunId")
    if not isinstance(run_id, str) or not run_id:
        raise RuntimeError("RunDeployment returned no DeploymentRunId")
    if args.no_wait:
        print_json(triggered)
        return
    result = wait_for_run(client, run_id, json_output=args.json_output)
    session_id = result.get("SessionId")
    if not isinstance(session_id, str) or not session_id:
        raise RuntimeError("DeploymentRun completed without SessionId")
    update_resource(
        state,
        "deployment_run",
        {
            "id": run_id,
            "deployment_id": deployment_id,
            "session_id": session_id,
            "trigger_type": (result.get("TriggerContext") or {}).get("type"),
        },
    )
    emit(
        "deployment_run",
        "DeploymentRun 已派发",
        json_output=args.json_output,
        deployment_run_id=run_id,
        session_id=session_id,
        next="运行 07_verify_deployment_run.py 验证已派发 Session 的真实执行结果",
    )
    print_json(result)


if __name__ == "__main__":
    run(main)
