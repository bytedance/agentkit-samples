"""功能 5：自动审批流水线人工卡点（ManualApproval）。

人工卡点任务会让流水线停在 Running/等待人工确认状态，本脚本通过 DoTaskAction
对指定 task 执行 ManualApproval 操作，自动批准或拒绝，避免流水线一直卡住。

底层 OpenAPI：DoTaskAction（IDL: v2/idl/task.thrift DoTaskActionReq，
api.post='/DoTaskAction'）。ActionConfig 是 map<string,string>，因此 IsApproved
必须以字符串 "true"/"false" 传递。

用法：
    # 批准
    VOLC_ACCESSKEY=... VOLC_SECRETKEY=... \
    python approve_task.py --workspace-id WS_ID --pipeline-id PID \
        --run-id RUN_ID --task-id TASK_ID --approve

    # 拒绝（必须给出原因）
    python approve_task.py --workspace-id WS_ID --pipeline-id PID \
        --run-id RUN_ID --task-id TASK_ID --reject --comment "原因"

对应请求示例：
    {
        "WorkspaceId": "...", "PipelineId": "...", "PipelineRunId": "...",
        "TaskId": "...", "ActionName": "ManualApproval",
        "ActionConfig": {"IsApproved": "true"}
    }
    {
        ..., "ActionConfig": {"IsApproved": "false", "Comment": "1"}
    }
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cp_api import client_from_env, normalize_workspace_ref, redact_value  # noqa: E402
from openapi_common import call_safely  # noqa: E402

# 人工卡点审批固定的 action 名称。
MANUAL_APPROVAL_ACTION = "ManualApproval"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--workspace-id", required=True)
    p.add_argument(
        "--region",
        default="cn-beijing",
        choices=["cn-beijing", "ap-southeast-1"],
        help="生产地域：cn-beijing 或 ap-southeast-1，默认 cn-beijing",
    )
    p.add_argument("--pipeline-id", required=True)
    p.add_argument("--run-id", required=True, help="流水线运行实例 ID（PipelineRunId）")
    p.add_argument("--task-id", required=True, help="人工卡点所在的任务 ID")
    decision = p.add_mutually_exclusive_group(required=True)
    decision.add_argument("--approve", action="store_true", help="批准卡点")
    decision.add_argument("--reject", action="store_true", help="拒绝卡点（需 --comment）")
    p.add_argument("--comment", default=None, help="拒绝原因；拒绝时必填")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true", help="确认执行生产人工卡点操作")
    return p.parse_args()


def build_body(args: argparse.Namespace) -> dict:
    """构造 DoTaskAction 请求体并做参数校验。

    校验规则：
    - 批准/拒绝二选一（argparse 互斥组已保证）。
    - 拒绝时 Comment 必填，用于说明拒绝原因。
    - ActionConfig 为 map<string,string>，IsApproved 以字符串布尔值传递。
    """
    is_approved = bool(args.approve)
    if not is_approved and not args.comment:
        raise SystemExit("拒绝人工卡点（--reject）时必须通过 --comment 提供拒绝原因")

    action_config = {"IsApproved": "true" if is_approved else "false"}
    if args.comment:
        action_config["Comment"] = args.comment

    return {
        "WorkspaceId": args.workspace_id,
        "PipelineId": args.pipeline_id,
        "PipelineRunId": args.run_id,
        "TaskId": args.task_id,
        "ActionName": MANUAL_APPROVAL_ACTION,
        "ActionConfig": action_config,
    }


def main() -> int:
    args = parse_args()
    args.workspace_id, args.region = normalize_workspace_ref(args.workspace_id, args.region)
    body = build_body(args)
    if args.dry_run:
        print(f"[dry-run] DoTaskAction body={json.dumps(redact_value(body), ensure_ascii=False)}")
        return 0
    if not args.yes:
        raise SystemExit("DoTaskAction 是生产写操作；请先用 --dry-run 复核，再加 --yes 执行")
    c = client_from_env(args.region)
    call_safely(c, "DoTaskAction", body, mutation=True)
    decision = "approved" if args.approve else "rejected"
    print(
        f"manual approval {decision} taskId={args.task_id} "
        f"pipelineRunId={args.run_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
