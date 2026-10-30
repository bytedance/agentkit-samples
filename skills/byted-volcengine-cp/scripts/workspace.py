"""List and update CP workspaces in allowlisted production regions."""
from __future__ import annotations

import argparse
from typing import Any, Callable, Dict, List, Optional, Tuple

from cp_api import (
    client_from_env,
    load_json_object,
    merge_explicit_fields,
    normalize_workspace_ref,
    paginate_numbered,
    redact_value,
)
from openapi_common import (
    add_region,
    execute_mutation,
    normalize_optional_workspace,
    paginate_safely,
    print_accepted,
    print_json,
    reject_unknown_fields,
)

ACTION_BY_COMMAND = {"list": "ListWorkspaces", "update": "UpdateWorkspace"}


def _normalize_workspace_ids(
    values: Optional[List[str]], region: Optional[str]
) -> Tuple[Optional[List[str]], str]:
    if not values:
        _, resolved_region = normalize_optional_workspace(None, region)
        return None, resolved_region
    ids: List[str] = []
    resolved_region: Optional[str] = None
    for value in values:
        workspace_id, current_region = normalize_workspace_ref(value, region)
        if resolved_region and current_region != resolved_region:
            raise SystemExit("workspace filter 不能混用北京与柔佛生产 ID")
        resolved_region = current_region
        ids.append(workspace_id)
    return ids, resolved_region or "cn-beijing"


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CP 生产环境工作区查询与更新")
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("list")
    add_region(listing)
    listing.add_argument("--name")
    listing.add_argument("--workspace-id", action="append")
    listing.add_argument("--page-size", type=int, default=100)
    listing.add_argument("--max", type=int, default=20)
    listing.add_argument("--all", action="store_true")
    listing.add_argument("--json", action="store_true")

    update = sub.add_parser("update")
    add_region(update)
    update.add_argument("--workspace-id", required=True)
    source = update.add_mutually_exclusive_group(required=True)
    source.add_argument("--body-file")
    source.add_argument("--body-json")
    update.add_argument("--dry-run", action="store_true")
    update.add_argument("--yes", action="store_true")
    return parser.parse_args(argv)


def build_request(args: argparse.Namespace) -> Tuple[str, Dict[str, Any]]:
    if args.command == "list":
        filter_: Dict[str, Any] = {}
        if args.name:
            filter_["Name"] = args.name
        workspace_ids, _ = _normalize_workspace_ids(args.workspace_id, args.region)
        if workspace_ids:
            filter_["Ids"] = workspace_ids
        body: Dict[str, Any] = {}
        if filter_:
            body["Filter"] = filter_
        return ACTION_BY_COMMAND["list"], body

    workspace_id, _ = normalize_optional_workspace(args.workspace_id, args.region)
    payload = load_json_object(args.body_file, args.body_json)
    mutable = {"Name", "Description", "Visibility", "VisibleUsers", "VisibleUserGroups"}
    reject_unknown_fields(payload, "UpdateWorkspace", mutable | {"Id"})
    if not mutable.intersection(payload):
        raise SystemExit("UpdateWorkspace 请求体至少需要一个可更新字段")
    body = merge_explicit_fields(payload, Id=workspace_id)
    return ACTION_BY_COMMAND["update"], body


def execute(
    args: argparse.Namespace,
    client_factory: Callable[[str], Any] = client_from_env,
) -> int:
    if args.command == "list":
        _, region = _normalize_workspace_ids(args.workspace_id, args.region)
        action, body = build_request(args)
        request_ids: List[str] = []
        items, total = paginate_safely(
            paginate_numbered,
            client_factory(region),
            action,
            body,
            args.page_size,
            None if args.all else args.max,
            request_ids=request_ids,
        )
        safe_items = redact_value(items)
        if args.json:
            print_json(
                {
                    "Region": region,
                    "Action": action,
                    "RequestIds": request_ids,
                    "TotalCount": total,
                    "Returned": len(safe_items),
                    "Items": safe_items,
                }
            )
        else:
            print(
                f"action={action} region={region} total={total} "
                f"returned={len(safe_items)} requestIds={','.join(request_ids) or '-'}"
            )
            for item in safe_items:
                print(
                    f"- id={item.get('Id')} name={item.get('Name')} "
                    f"visibility={item.get('Visibility')} updated={item.get('UpdateTime') or '-'}"
                )
        return 0

    workspace_id, region = normalize_optional_workspace(args.workspace_id, args.region)
    action, body = build_request(args)
    response = execute_mutation(
        args=args,
        action=action,
        body=body,
        region=region,
        client_factory=client_factory,
    )
    if not args.dry_run:
        print_accepted(action, region, response, workspace_id)
    return 0


def main() -> int:
    return execute(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
