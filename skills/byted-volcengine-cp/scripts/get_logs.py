"""查看生产环境流水线运行日志。

日志读取需要定位到 step 级别。本脚本自动沿
ListStages -> (Task) -> ListTaskRuns -> (TaskRunStep) -> GetTaskRunLog 链路下钻。

用法：
    # 拉取某次运行下所有 step 的日志
    VOLC_ACCESSKEY=... VOLC_SECRETKEY=... \
    python get_logs.py --workspace-id WS_ID --pipeline-id PID --run-id RUN_ID

    # 只看指定 task / step
    python get_logs.py --workspace-id WS_ID --pipeline-id PID --run-id RUN_ID \
        --task-id TASK_ID --step-name build

GetTaskRunLog 单次最大返回 256KB，本脚本按 Offset/More 循环翻页直到读完。
日志中的 access token / 临时 registry token / authorization 等敏感字段始终脱敏。
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cp_api import (  # noqa: E402
    client_from_env,
    list_stages,
    list_task_runs,
    normalize_workspace_ref,
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
    p.add_argument("--run-id", required=True, help="流水线运行实例 ID")
    p.add_argument("--task-id", default=None, help="仅拉取该 task（默认全部）")
    p.add_argument("--step-name", default=None, help="仅拉取该 step（默认全部）")
    p.add_argument("--limit", type=int, default=256 * 1024, help="单次读取上限（<=256KB）")
    return p.parse_args()


_SENSITIVE_PATTERNS = [
    (re.compile(r'("token"\s*:\s*")[^"]+(")', re.IGNORECASE), r'\1<redacted>\2'),
    (re.compile(r'("access[_-]?token"\s*:\s*")[^"]+(")', re.IGNORECASE), r'\1<redacted>\2'),
    (re.compile(r'("authorization"\s*:\s*")[^"]+(")', re.IGNORECASE), r'\1<redacted>\2'),
    (re.compile(r'(Authorization:\s*)\S+', re.IGNORECASE), r'\1<redacted>'),
    (re.compile(r'(Bearer\s+)[A-Za-z0-9._~+/-]+=*', re.IGNORECASE), r'\1<redacted>'),
    # CR 临时 token 常为 JWT；保留短字符串，避免误伤普通日志，只脱敏明显很长的 JWT。
    (re.compile(r'eyJ[A-Za-z0-9_-]{40,}\.[A-Za-z0-9_-]{40,}\.[A-Za-z0-9_-]{20,}'), '<redacted-jwt>'),
]


def redact_log_line(line: object) -> str:
    """脱敏日志行，避免把 CR 临时 token / access token 写入终端或文档证据。"""
    text = redact_secret(str(line))
    for pattern, repl in _SENSITIVE_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def fetch_step_log(
    c,
    ws_id: str,
    pid: str,
    run_id: str,
    task_id: str,
    task_run_id: str,
    step_name: str,
    limit: int,
) -> None:
    offset = 0
    while True:
        resp = c.call(
            "GetTaskRunLog",
            {
                "WorkspaceId": ws_id,
                "PipelineId": pid,
                "PipelineRunId": run_id,
                "TaskId": task_id,
                "TaskRunId": task_run_id,
                "StepName": step_name,
                "Offset": offset,
                "Limit": min(limit, 256 * 1024),
            },
        )
        result = resp.get("Result", {})
        for line in result.get("LogLines") or []:
            print(redact_log_line(line))
        if not result.get("More"):
            break
        next_offset = result.get("NextOffset")
        if next_offset is None or next_offset == offset:
            break
        offset = next_offset


def main() -> int:
    args = parse_args()
    args.workspace_id, args.region = normalize_workspace_ref(args.workspace_id, args.region)
    c = client_from_env(args.region)

    stages = list_stages(c, args.workspace_id, args.pipeline_id, args.run_id)
    for s in stages:
        for t in s.get("Tasks") or []:
            task_id = t.get("Id")
            if args.task_id and task_id != args.task_id:
                continue
            task_runs = list_task_runs(
                c, args.workspace_id, args.pipeline_id, args.run_id, task_id
            )
            for tr in task_runs:
                task_run_id = tr.get("Id")
                for step in tr.get("Steps") or []:
                    step_name = step.get("Name")
                    if args.step_name and step_name != args.step_name:
                        continue
                    header = (
                        f"===== stage={s.get('Name')} task={t.get('Name')} "
                        f"taskRun={task_run_id} step={step_name} "
                        f"status={step.get('Status')} ====="
                    )
                    print(header)
                    fetch_step_log(
                        c,
                        args.workspace_id,
                        args.pipeline_id,
                        args.run_id,
                        task_id,
                        task_run_id,
                        step_name,
                        args.limit,
                    )
                    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
