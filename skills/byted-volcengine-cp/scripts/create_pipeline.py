"""在 CP 生产环境创建流水线。

用法：
    VOLC_ACCESSKEY=... VOLC_SECRETKEY=... \
    python create_pipeline.py --workspace-id WS_ID --name NAME \
        [--spec-file path/to/spec.yaml] [--auto-agent-pool] [--description TEXT] \
        [--parameters-json '[{"Key":"k","Value":"v"}]'] [--dry-run|--yes]

Spec 默认原样使用。加 --auto-agent-pool 时，会把 spec 里的 public/ 公共构建集群行
按 --region 自动改写为生产公共池 `public/prod-v2-public`，
private/ 私有池保持不变。这样直接复用 examples/ 模板时不必手动改 agentPool。
Parameters/Caches/Notification 如需配置，通过对应 JSON 参数传入原始结构。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cp_api import (  # noqa: E402
    client_from_env,
    normalize_workspace_ref,
    redact_value,
    rewrite_agent_pool,
)
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
    p.add_argument("--name", required=True, help="流水线名称（2~50 字符，工作区内唯一）")
    p.add_argument("--description", default=None)
    p.add_argument("--spec-file", default=None, help="流水线 spec YAML 文件路径")
    p.add_argument(
        "--auto-agent-pool",
        action="store_true",
        help="按 --region 自动改写 spec 里的 public/ 公共构建集群（agentPool）",
    )
    p.add_argument(
        "--parameters-json",
        default=None,
        help='PipelineParameter JSON 数组，如 [{"Key":"k","Value":"v"}]',
    )
    p.add_argument("--caches-json", default=None, help="PipelineCache JSON 数组")
    p.add_argument("--notification-json", default=None, help="PipelineNotification JSON 对象")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true", help="确认执行生产写操作")
    return p.parse_args()


def build_body(args: argparse.Namespace) -> dict:
    body = {"WorkspaceId": args.workspace_id, "Name": args.name}
    if args.description:
        body["Description"] = args.description
    if args.spec_file:
        with open(args.spec_file, "r", encoding="utf-8") as f:
            spec = f.read()
        if args.auto_agent_pool:
            spec, changes = rewrite_agent_pool(spec, args.region)
            for ch in changes:
                print(f"[auto-agent-pool] {ch['from']} -> {ch['to']}")
        body["Spec"] = spec
    if args.parameters_json:
        body["Parameters"] = json.loads(args.parameters_json)
    if args.caches_json:
        body["Caches"] = json.loads(args.caches_json)
    if args.notification_json:
        body["Notification"] = json.loads(args.notification_json)
    return body


def main() -> int:
    args = parse_args()
    args.workspace_id, args.region = normalize_workspace_ref(args.workspace_id, args.region)
    body = build_body(args)
    if args.dry_run:
        printable = {k: (v if k != "Spec" else f"<{len(v)} chars>") for k, v in body.items()}
        print(f"[dry-run] CreatePipeline body={json.dumps(redact_value(printable), ensure_ascii=False)}")
        return 0
    if not args.yes:
        raise SystemExit("CreatePipeline 是生产写操作；请先用 --dry-run 复核，再加 --yes 执行")
    c = client_from_env(args.region)
    resp = call_safely(c, "CreatePipeline", body, mutation=True)
    pid = (resp.get("Result") or {}).get("Id")
    print(f"created pipeline name={args.name} id={pid} workspaceId={args.workspace_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
