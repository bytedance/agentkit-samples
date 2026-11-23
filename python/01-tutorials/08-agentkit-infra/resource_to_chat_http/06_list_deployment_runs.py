#!/usr/bin/env python3
"""列出 Deployment 的历史 Run，便于核对定时触发与 Session。"""

from __future__ import annotations

from _clients import TopClient
from _common import emit, load_state, parser, print_json, run
from _config import validated_config
from _deployment import list_runs


def main() -> None:
    cli = parser(__doc__)
    cli.add_argument("--deployment-id", default="", help="缺省读取状态文件")
    cli.add_argument("--limit", type=int, default=20, help="1～100，默认 20")
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
    if not 1 <= args.limit <= 100:
        raise RuntimeError("--limit must be between 1 and 100")
    if args.dry_run:
        emit(
            "dry_run",
            "列出 DeploymentRun 计划",
            json_output=args.json_output,
            deployment_id=deployment_id,
            limit=args.limit,
            status="dry_run（未访问网络）",
        )
        return
    items = list_runs(client, deployment_id, limit=args.limit)
    print_json({"DeploymentId": deployment_id, "Items": items})


if __name__ == "__main__":
    run(main)
