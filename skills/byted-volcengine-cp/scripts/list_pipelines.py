"""查询生产环境工作区下的流水线列表（ListPipelines）。

用法：
    VOLC_ACCESSKEY=... VOLC_SECRETKEY=... \
    python list_pipelines.py --workspace-id WS_ID --all --json

支持自然语言工作区引用，如 --workspace-id 北京prod9237...；脚本会自动拆成
region=cn-beijing 和真实 32 位 workspace id。明确的 pre 引用会被拒绝。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cp_api import (  # noqa: E402
    build_pipeline_filter,
    client_from_env,
    list_pipelines,
    normalize_workspace_ref,
    redact_secret,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--workspace-id", required=True, help="生产工作区 ID，支持 北京prod<32hex> 写法")
    p.add_argument(
        "--region",
        default="cn-beijing",
        choices=["cn-beijing", "ap-southeast-1"],
        help="生产地域：cn-beijing 或 ap-southeast-1，默认 cn-beijing",
    )
    p.add_argument("--page-size", type=int, default=100, help="分页大小，1~100，默认 100")
    p.add_argument("--max", type=int, default=20, help="最多输出条数；--all 时忽略")
    p.add_argument("--all", action="store_true", help="拉取并输出全部流水线")
    p.add_argument("--name", default=None, help="按流水线名称过滤")
    p.add_argument("--pipeline-id", action="append", default=None, help="按流水线 ID 过滤，可重复")
    p.add_argument("--pipeline-group-id", default=None, help="按流水线分组 ID 过滤")
    p.add_argument("--json", action="store_true", help="输出 JSON，便于脚本消费")
    p.add_argument("--show-spec", action="store_true", help="输出脱敏后的完整 Spec（默认仅输出长度）")
    return p.parse_args()


def summarize_pipeline(item: dict, show_spec: bool = False) -> dict:
    spec = item.get("Spec") or ""
    out = {
        "Id": item.get("Id"),
        "Name": item.get("Name"),
        "WorkspaceId": item.get("WorkspaceId"),
        "Description": item.get("Description"),
        "SpecLength": len(spec),
        "CreateTime": item.get("CreateTime"),
        "UpdateTime": item.get("UpdateTime"),
    }
    if show_spec:
        out["Spec"] = redact_secret(spec)
    return out


def main() -> int:
    args = parse_args()
    workspace_id, region = normalize_workspace_ref(args.workspace_id, args.region)
    max_results = None if args.all else args.max
    filter_ = build_pipeline_filter(
        ids=args.pipeline_id,
        name=args.name,
        pipeline_group_id=args.pipeline_group_id,
    )

    c = client_from_env(region)
    items, total = list_pipelines(
        c,
        workspace_id,
        page_size=args.page_size,
        max_results=max_results,
        filter_=filter_,
    )
    rows = [summarize_pipeline(i, args.show_spec) for i in items]
    if args.json:
        print(
            json.dumps(
                {
                    "WorkspaceId": workspace_id,
                    "Region": region,
                    "TotalCount": total,
                    "Returned": len(rows),
                    "Items": rows,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(f"workspaceId={workspace_id} region={region} total={total} returned={len(rows)}")
    for r in rows:
        print(
            f"- id={r['Id']} name={r['Name']} specLen={r['SpecLength']} "
            f"updated={r.get('UpdateTime') or '-'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
