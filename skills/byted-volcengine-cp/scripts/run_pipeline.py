"""在 CP 生产环境运行已有流水线。

用法：
    VOLC_ACCESSKEY=... VOLC_SECRETKEY=... \
    python run_pipeline.py --workspace-id WS_ID --pipeline-id PID \
        [--description TEXT] \
        [--parameters-json '[{"Key":"k","Value":"v"}]'] \
        [--resources-json '[...]'] [--sources-json '[...]'] [--dry-run|--yes]

不传 Parameters/Resources 时使用流水线默认值；若流水线必须代码源会失败。
返回的 RunId 可用于 get_status.py / get_logs.py 查询。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cp_api import client_from_env, normalize_workspace_ref, redact_value  # noqa: E402
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
    p.add_argument("--description", default="skill byted-volcengine-cp run")
    p.add_argument(
        "--parameters-json",
        default=None,
        help='TriggerParameter JSON 数组，如 [{"Key":"k","Value":"v"}]',
    )
    p.add_argument("--resources-json", default=None, help="TriggerResource JSON 数组")
    p.add_argument("--sources-json", default=None, help="TriggerSource JSON 数组")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true", help="确认触发生产流水线")
    return p.parse_args()


def build_body(args: argparse.Namespace) -> dict:
    body = {
        "WorkspaceId": args.workspace_id,
        "Id": args.pipeline_id,
        "Description": args.description,
    }
    if args.parameters_json:
        body["Parameters"] = json.loads(args.parameters_json)
    if args.resources_json:
        body["Resources"] = json.loads(args.resources_json)
    if args.sources_json:
        body["Sources"] = json.loads(args.sources_json)
    return body


def main() -> int:
    args = parse_args()
    args.workspace_id, args.region = normalize_workspace_ref(args.workspace_id, args.region)
    body = build_body(args)
    if args.dry_run:
        print(f"[dry-run] RunPipeline body={json.dumps(redact_value(body), ensure_ascii=False)}")
        return 0
    if not args.yes:
        raise SystemExit("RunPipeline 是生产写操作；请先用 --dry-run 复核，再加 --yes 执行")
    c = client_from_env(args.region)
    resp = call_safely(c, "RunPipeline", body, mutation=True)
    run_id = (resp.get("Result") or {}).get("Id")
    print(f"triggered pipelineId={args.pipeline_id} runId={run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
