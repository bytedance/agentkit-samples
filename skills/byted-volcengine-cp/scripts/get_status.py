"""查看生产环境流水线运行状态。

用法：
    # 列出最近运行记录（可按状态过滤）
    VOLC_ACCESSKEY=... VOLC_SECRETKEY=... \
    python get_status.py --workspace-id WS_ID --pipeline-id PID \
        [--status Running --status Succeeded] [--max 10]

    # 查看某次运行的阶段/任务级状态
    python get_status.py --workspace-id WS_ID --pipeline-id PID \
        --run-id RUN_ID --detail

状态枚举：Enqueued/Dequeued/LockWaiting/Queued/Running/InProgress/Canceling/Canceled/Timeout/Failed/Succeeded。
其中 InProgress 展示为 Running，PipelineRun 长时间停留 Canceling 表示取消请求已生效，按 Canceled 处理。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cp_api import (  # noqa: E402
    client_from_env,
    list_pipeline_runs,
    list_stages,
    normalize_workspace_ref,
    normalize_status,
    redact_secret,
)


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
    p.add_argument("--run-id", default=None, help="指定运行记录 ID，配合 --detail 查看阶段")
    p.add_argument("--status", action="append", default=None, help="按运行状态过滤，可多次传入")
    p.add_argument("--max", type=int, default=10, help="最多返回多少条运行记录（默认 10）")
    p.add_argument("--detail", action="store_true", help="展开 stage/task 级状态（需 --run-id）")
    return p.parse_args()


def _fmt_status(raw: str) -> str:
    """展示状态：服务端原值 + 归一化结果（不同则标注）。"""
    norm = normalize_status(raw)
    return raw if norm == raw else f"{raw}(={norm})"


def print_runs(runs: list) -> None:
    for r in runs:
        print(
            f"runId={r.get('Id')} index={r.get('Index')} "
            f"status={_fmt_status(r.get('Status'))} "
            f"start={r.get('StartTime')} finish={r.get('FinishTime')}"
        )
        if r.get("FailedMessage"):
            print(f"    failedMessage={redact_secret(str(r.get('FailedMessage')))}")


def print_detail(stages: list) -> None:
    for s in stages:
        print(f"stage {s.get('Name')} [{_fmt_status(s.get('Status'))}] id={s.get('Id')}")
        for t in s.get("Tasks") or []:
            print(
                f"    task {t.get('Name')} [{_fmt_status(t.get('Status'))}] "
                f"taskId={t.get('Id')} latestTaskRunId={t.get('LatestTaskRunId')}"
            )


def main() -> int:
    args = parse_args()
    args.workspace_id, args.region = normalize_workspace_ref(args.workspace_id, args.region)
    c = client_from_env(args.region)

    if args.detail:
        if not args.run_id:
            raise SystemExit("--detail 需要同时指定 --run-id")
        stages = list_stages(c, args.workspace_id, args.pipeline_id, args.run_id)
        print_detail(stages)
        return 0

    runs = list_pipeline_runs(
        c,
        workspace_id=args.workspace_id,
        pipeline_id=args.pipeline_id,
        statuses=args.status,
        max_results=args.max,
    )
    if args.run_id:
        runs = [r for r in runs if r.get("Id") == args.run_id]
    print_runs(runs)
    print(f"\ntotal: {len(runs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
