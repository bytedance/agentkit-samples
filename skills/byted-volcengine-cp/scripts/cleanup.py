"""删除生产环境的工作区 / 流水线。

两个删除接口都是不可逆操作，因此默认需 --yes 确认（或先 --dry-run 复核）。

除 --yes 外，删除流水线或工作区都要求交互式二次确认（手动输入目标 ID）。
非交互场景可加 --force 跳过该二次确认；删除工作区会连带其下所有流水线，风险更高。

底层 OpenAPI：
- DeletePipeline（WorkspaceId + Id）
- DeleteWorkspace（Id，可选 Option.DeleteAppClusterResources）

用法：
    # 删除单条流水线（--yes + 交互式输入 pipeline ID）
    CP_ACCESS_KEY=... CP_SECRET_KEY=... \
    python cleanup.py pipeline --workspace-id WS_ID --pipeline-id PID --yes

    # 删除工作区（--yes + 交互式二次确认；可选连带应用集群资源）
    python cleanup.py workspace --workspace-id WS_ID --yes [--delete-app-cluster-resources]

    # 删除工作区且跳过交互式二次确认（非交互/CI 场景）
    python cleanup.py workspace --workspace-id WS_ID --yes --force

    # 任何子命令加 --dry-run 仅打印将要调用的请求体
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cp_api import client_from_env, normalize_workspace_ref  # noqa: E402
from openapi_common import call_safely  # noqa: E402


def parse_args() -> argparse.Namespace:
    # 公共参数放在 parent parser，挂到每个子命令上，这样 --dry-run/--yes/--region
    # 既可写在子命令前，也可写在子命令后，避免「unrecognized arguments」踩坑。
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--region",
        default="cn-beijing",
        choices=["cn-beijing", "ap-southeast-1"],
        help="生产地域：cn-beijing 或 ap-southeast-1，默认 cn-beijing",
    )
    common.add_argument("--dry-run", action="store_true")
    common.add_argument("--yes", action="store_true", help="确认执行删除（不可逆）")

    p = argparse.ArgumentParser(parents=[common])
    sub = p.add_subparsers(dest="target", required=True)

    pp = sub.add_parser("pipeline", parents=[common], help="删除流水线")
    pp.add_argument("--workspace-id", required=True)
    pp.add_argument("--pipeline-id", required=True)
    pp.add_argument(
        "--force",
        action="store_true",
        help="跳过流水线 ID 的交互式二次确认（非交互场景）",
    )

    pw = sub.add_parser("workspace", parents=[common], help="删除工作区")
    pw.add_argument("--workspace-id", required=True)
    pw.add_argument(
        "--delete-app-cluster-resources",
        action="store_true",
        help="连带删除工作区下所有应用集群资源",
    )
    pw.add_argument(
        "--force",
        action="store_true",
        help="跳过删除工作区的交互式二次确认（非交互/CI 场景）",
    )
    return p.parse_args()


def build_request(args: argparse.Namespace) -> "tuple[str, dict]":
    """返回 (action, body)。"""
    if args.target == "pipeline":
        return "DeletePipeline", {
            "WorkspaceId": args.workspace_id,
            "Id": args.pipeline_id,
        }
    body = {"Id": args.workspace_id}
    if args.delete_app_cluster_resources:
        body["Option"] = {"DeleteAppClusterResources": True}
    return "DeleteWorkspace", body


def confirm_target_delete(target_kind: str, target_id: str) -> None:
    """删除目标的交互式二次确认：要求用户原样输入目标 ID。

    输入不匹配则中止删除。非交互式 stdin（管道/CI）下应改用 --force 跳过。
    """
    scope = "（含其下所有流水线）" if target_kind == "workspace" else ""
    prompt = (
        f"⚠️  即将删除{target_kind} {target_id}{scope}，此操作不可逆。\n"
        f"请输入目标 ID 以二次确认: "
    )
    try:
        entered = input(prompt).strip()
    except EOFError:
        raise SystemExit(
            "无法进行交互式二次确认（非交互 stdin）；如确需删除请加 --force"
        )
    if entered != target_id:
        raise SystemExit("二次确认未通过（输入与目标 ID 不一致），已取消删除")


def main() -> int:
    args = parse_args()
    args.workspace_id, args.region = normalize_workspace_ref(args.workspace_id, args.region)
    action, body = build_request(args)

    if args.dry_run:
        print(f"[dry-run] {action} body={json.dumps(body, ensure_ascii=False)}")
        return 0
    if not args.yes:
        raise SystemExit(
            f"{action} 是不可逆删除操作，请加 --yes 确认，或先用 --dry-run 复核"
        )

    if not args.force:
        target_id = args.pipeline_id if args.target == "pipeline" else args.workspace_id
        confirm_target_delete(args.target, target_id)

    c = client_from_env(args.region)
    call_safely(c, action, body, mutation=True)
    if args.target == "pipeline":
        print(f"deleted pipeline id={args.pipeline_id} workspaceId={args.workspace_id}")
    else:
        print(f"deleted workspace id={args.workspace_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
