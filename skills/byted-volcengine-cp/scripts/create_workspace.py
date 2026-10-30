"""在 CP 生产环境创建工作区。

用法：
    VOLC_ACCESSKEY=... VOLC_SECRETKEY=... \
    python create_workspace.py --name NAME [--description TEXT] \
        [--visibility Account|Specified] [--dry-run|--yes]

默认 Visibility=Account（所有用户可见）。Specified 模式下需通过 --visible-user
传入主账号在内的可见用户（go.tag 要求 IAMUser 结构），本 skill 暂不内置复杂用户解析，
如需指定用户请直接传 --visible-user-json 原始 JSON 数组。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cp_api import client_from_env, redact_value  # noqa: E402
from openapi_common import call_safely  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True, help="工作区名称（2~50 字符，账号内唯一）")
    p.add_argument(
        "--region",
        default="cn-beijing",
        choices=["cn-beijing", "ap-southeast-1"],
        help="生产地域：cn-beijing 或 ap-southeast-1，默认 cn-beijing",
    )
    p.add_argument("--description", default=None)
    p.add_argument(
        "--visibility",
        default="Account",
        choices=["Account", "Specified"],
        help="Account：所有用户可见（默认）；Specified：指定用户可见",
    )
    p.add_argument(
        "--visible-user-json",
        default=None,
        help='Specified 模式下的 VisibleUsers JSON 数组，必须含主账号',
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true", help="确认执行生产写操作")
    return p.parse_args()


def build_body(args: argparse.Namespace) -> dict:
    body = {"Name": args.name, "Visibility": args.visibility}
    if args.description:
        body["Description"] = args.description
    if args.visibility == "Specified":
        if not args.visible_user_json:
            raise SystemExit("Visibility=Specified 必须提供 --visible-user-json")
        body["VisibleUsers"] = json.loads(args.visible_user_json)
    return body


def main() -> int:
    args = parse_args()
    body = build_body(args)
    if args.dry_run:
        print(f"[dry-run] CreateWorkspace body={json.dumps(redact_value(body), ensure_ascii=False)}")
        return 0
    if not args.yes:
        raise SystemExit("CreateWorkspace 是生产写操作；请先用 --dry-run 复核，再加 --yes 执行")
    c = client_from_env(args.region)
    resp = call_safely(c, "CreateWorkspace", body, mutation=True)
    ws_id = (resp.get("Result") or {}).get("Id")
    print(f"created workspace name={args.name} id={ws_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
