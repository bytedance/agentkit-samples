"""批量更新生产环境工作区下流水线 Spec（ListPipelines + UpdatePipeline）。

典型用于批量修复流水线 YAML / Dockerfile content。脚本默认先 dry-run；正式执行需加
--yes。替换逻辑是幂等的，old -> old+suffix 场景不会重复追加 suffix。

用法：
    python bulk_update_pipelines.py --workspace-id WS_ID \
        --replace-from 'old' --replace-to 'new' --dry-run
    python bulk_update_pipelines.py --workspace-id WS_ID \
        --replace-from 'old' --replace-to 'new' --yes --max-workers 20
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cp_api import (  # noqa: E402
    client_from_env,
    list_pipelines,
    normalize_workspace_ref,
    redact_secret,
    replace_once_idempotent,
    update_pipeline_spec,
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
    p.add_argument("--replace-from", required=True, help="待替换的原始字符串")
    p.add_argument("--replace-to", required=True, help="替换后的字符串")
    p.add_argument("--include-name-regex", default=None, help="只更新名称匹配该正则的流水线")
    p.add_argument("--exclude-name-regex", default=None, help="排除名称匹配该正则的流水线")
    p.add_argument("--limit", type=int, default=None, help="最多处理 N 条（排障/灰度用）")
    p.add_argument("--max-workers", type=int, default=20, help="并发更新 worker 数，默认 20")
    p.add_argument("--dry-run", action="store_true", help="仅统计命中，不实际更新")
    p.add_argument("--yes", action="store_true", help="确认执行批量写操作")
    p.add_argument("--json", action="store_true", help="输出 JSON summary")
    return p.parse_args()


def _selected(item: dict, include: re.Pattern | None, exclude: re.Pattern | None) -> bool:
    name = item.get("Name") or ""
    if include and not include.search(name):
        return False
    if exclude and exclude.search(name):
        return False
    return True


def plan_updates(items: list[dict], args: argparse.Namespace) -> tuple[list[dict], dict]:
    include = re.compile(args.include_name_regex) if args.include_name_regex else None
    exclude = re.compile(args.exclude_name_regex) if args.exclude_name_regex else None
    stats = {
        "total": len(items),
        "selected": 0,
        "need_update": 0,
        "already_updated": 0,
        "no_target": 0,
        "mixed_specs": 0,
    }
    targets: list[dict] = []
    for item in items:
        if not _selected(item, include, exclude):
            continue
        stats["selected"] += 1
        spec = item.get("Spec") or ""
        new_spec, count, already = replace_once_idempotent(
            spec, args.replace_from, args.replace_to
        )
        if count:
            stats["need_update"] += 1
            if already:
                stats["mixed_specs"] += 1
            targets.append(
                {
                    "Id": item.get("Id"),
                    "Name": item.get("Name"),
                    "Spec": new_spec,
                    "Replacements": count,
                }
            )
        elif already:
            stats["already_updated"] += 1
        else:
            stats["no_target"] += 1
        if args.limit is not None and stats["selected"] >= args.limit:
            break
    return targets, stats


def update_one(workspace_id: str, region: str, target: dict) -> dict:
    c = client_from_env(region)
    try:
        update_pipeline_spec(c, workspace_id, target["Id"], target["Spec"])
        return {
            "ok": True,
            "Id": target["Id"],
            "Name": target["Name"],
            "Replacements": target["Replacements"],
        }
    except Exception as exc:  # noqa: BLE001 - 批量脚本需聚合失败
        return {
            "ok": False,
            "Id": target["Id"],
            "Name": target["Name"],
            "Error": redact_secret(str(exc)),
            "Ambiguous": "timeout" in str(exc).lower() or "timed out" in str(exc).lower(),
        }


def verify(c, workspace_id: str, args: argparse.Namespace) -> dict:
    items, total = list_pipelines(c, workspace_id, page_size=100)
    targets, stats = plan_updates(items, args)
    return {
        "TotalCount": total,
        "VerifiedUpdated": stats["already_updated"],
        "RemainingNeedUpdate": len(targets),
        "NoTarget": stats["no_target"],
        "MixedSpecs": stats["mixed_specs"],
        "RemainingSample": [{"Id": t["Id"], "Name": t["Name"]} for t in targets[:10]],
    }


def main() -> int:
    args = parse_args()
    if args.max_workers < 1:
        raise SystemExit("--max-workers 必须 >= 1")
    workspace_id, region = normalize_workspace_ref(args.workspace_id, args.region)
    c = client_from_env(region)
    items, total = list_pipelines(c, workspace_id, page_size=100)
    targets, plan = plan_updates(items, args)
    summary = {
        "WorkspaceId": workspace_id,
        "Region": region,
        "TotalCount": total,
        "Plan": plan,
        "Updated": 0,
        "Failed": 0,
        "FailedSample": [],
        "Verify": None,
    }

    if args.dry_run or not targets:
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print("[dry-run] " + json.dumps(summary, ensure_ascii=False))
        return 0
    if not args.yes:
        raise SystemExit("批量 UpdatePipeline 是写操作，请加 --yes 确认，或先用 --dry-run 复核")

    results = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as ex:
        futs = [ex.submit(update_one, workspace_id, region, t) for t in targets]
        for idx, fut in enumerate(as_completed(futs), start=1):
            r = fut.result()
            results.append(r)
            if not args.json and (idx % 50 == 0 or idx == len(futs)):
                ok = sum(1 for x in results if x.get("ok"))
                print(f"progress={idx}/{len(futs)} ok={ok} fail={len(results)-ok}", flush=True)

    failed = [r for r in results if not r.get("ok")]
    summary["Updated"] = len(results) - len(failed)
    summary["Failed"] = len(failed)
    summary["FailedSample"] = failed[:10]
    summary["Verify"] = verify(c, workspace_id, args)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
