"""取消生产环境流水线运行实例（CancelPipelineRun）。

用法：
    VOLC_ACCESSKEY=... VOLC_SECRETKEY=... \
    python cancel_run.py --workspace-id WS_ID --pipeline-id PID --run-id RUN_ID [--dry-run|--yes]

说明：PipelineRun 被取消后可能长时间保持 Canceling；在 CP 语义中这表示取消请求已生效，
上层判定按 Canceled 处理。可继续用 get_status.py --detail 查看 task 是否进入 Canceled。
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
    p = argparse.ArgumentParser()
    p.add_argument("--workspace-id", required=True)
    p.add_argument(
        "--region",
        default="cn-beijing",
        choices=["cn-beijing", "ap-southeast-1"],
        help="生产地域：cn-beijing 或 ap-southeast-1，默认 cn-beijing",
    )
    p.add_argument("--pipeline-id", required=True)
    p.add_argument("--run-id", required=True, help="流水线运行实例 ID")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true", help="确认取消生产流水线运行")
    return p.parse_args()


def build_body(args: argparse.Namespace) -> dict:
    return {
        "WorkspaceId": args.workspace_id,
        "PipelineId": args.pipeline_id,
        "Id": args.run_id,
    }


def main() -> int:
    args = parse_args()
    args.workspace_id, args.region = normalize_workspace_ref(args.workspace_id, args.region)
    body = build_body(args)
    if args.dry_run:
        print(f"[dry-run] CancelPipelineRun body={json.dumps(body, ensure_ascii=False)}")
        return 0
    if not args.yes:
        raise SystemExit("CancelPipelineRun 是生产写操作；请先用 --dry-run 复核，再加 --yes 执行")
    c = client_from_env(args.region)
    call_safely(c, "CancelPipelineRun", body, mutation=True)
    print(f"cancel pipeline run requested runId={args.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
