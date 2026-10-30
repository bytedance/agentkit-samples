"""更新生产环境单条流水线（UpdatePipeline）。

默认仅更新 Spec 字段，避免误覆盖名称、资源、参数等其他配置。

用法：
    # 使用本地 spec 文件更新
    python update_pipeline.py --workspace-id WS_ID --pipeline-id PID --spec-file pipeline.yaml --yes

    # 拉取当前 spec 后做幂等字符串替换
    python update_pipeline.py --workspace-id WS_ID --pipeline-id PID \
        --replace-from 'old' --replace-to 'new' --yes
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cp_api import (  # noqa: E402
    client_from_env,
    get_pipeline,
    normalize_workspace_ref,
    replace_once_idempotent,
)
from openapi_common import call_safely  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--workspace-id", required=True, help="生产工作区 ID，支持 北京prod<32hex> 写法")
    p.add_argument("--pipeline-id", required=True)
    p.add_argument(
        "--region",
        default="cn-beijing",
        choices=["cn-beijing", "ap-southeast-1"],
        help="生产地域：cn-beijing 或 ap-southeast-1，默认 cn-beijing",
    )
    p.add_argument("--spec-file", default=None, help="用该文件内容更新流水线 Spec")
    p.add_argument("--replace-from", default=None, help="从当前 Spec 中替换的原始字符串")
    p.add_argument("--replace-to", default=None, help="替换后的字符串")
    p.add_argument("--dry-run", action="store_true", help="仅展示更新计划，不实际调用 UpdatePipeline")
    p.add_argument("--yes", action="store_true", help="确认执行写操作")
    p.add_argument("--json", action="store_true", help="输出 JSON summary")
    return p.parse_args()


def build_new_spec(args: argparse.Namespace, current_spec: str) -> tuple[str, dict]:
    if args.spec_file and (args.replace_from or args.replace_to):
        raise SystemExit("--spec-file 与 --replace-from/--replace-to 不能同时使用")
    if args.spec_file:
        with open(args.spec_file, "r", encoding="utf-8") as f:
            spec = f.read()
        return spec, {"mode": "spec-file", "replacements": None, "already_has_new": False}
    if args.replace_from is not None or args.replace_to is not None:
        if args.replace_from is None or args.replace_to is None:
            raise SystemExit("--replace-from 与 --replace-to 必须同时提供")
        spec, count, already = replace_once_idempotent(
            current_spec, args.replace_from, args.replace_to
        )
        return spec, {"mode": "replace", "replacements": count, "already_has_new": already}
    raise SystemExit("必须提供 --spec-file，或同时提供 --replace-from/--replace-to")


def main() -> int:
    args = parse_args()
    workspace_id, region = normalize_workspace_ref(args.workspace_id, args.region)
    c = client_from_env(region)
    pipeline = get_pipeline(c, workspace_id, args.pipeline_id)
    current_spec = pipeline.get("Spec") or ""
    new_spec, detail = build_new_spec(args, current_spec)
    changed = new_spec != current_spec
    summary = {
        "WorkspaceId": workspace_id,
        "Region": region,
        "PipelineId": args.pipeline_id,
        "Name": pipeline.get("Name"),
        "Mode": detail["mode"],
        "Changed": changed,
        "OldSpecLength": len(current_spec),
        "NewSpecLength": len(new_spec),
        "Replacements": detail["replacements"],
        "AlreadyHasNew": detail["already_has_new"],
        "Updated": False,
    }

    if args.dry_run or not changed:
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            prefix = "[dry-run] " if args.dry_run else "[noop] "
            print(prefix + json.dumps(summary, ensure_ascii=False))
        return 0
    if not args.yes:
        raise SystemExit("UpdatePipeline 是写操作，请加 --yes 确认，或先用 --dry-run 复核")

    call_safely(
        c,
        "UpdatePipeline",
        {"WorkspaceId": workspace_id, "Id": args.pipeline_id, "Spec": new_spec},
        mutation=True,
    )
    summary["Updated"] = True
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"updated pipeline id={args.pipeline_id} name={pipeline.get('Name')} workspaceId={workspace_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
