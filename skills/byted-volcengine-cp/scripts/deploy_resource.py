"""Manage account-level CP deploy resources in allowlisted production regions."""
from __future__ import annotations

import argparse
from typing import Any, Callable, Dict, List, Optional, Tuple

from cp_api import (
    client_from_env,
    load_json_object,
    merge_explicit_fields,
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
    reject_fields,
    reject_unknown_fields,
    require_fields,
)

ACTION_BY_COMMAND = {
    "create": "CreateDeployResource",
    "list": "ListDeployResources",
    "update": "UpdateDeployResource",
    "delete": "DeleteDeployResource",
}


def _add_mutation(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")


def _add_body(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--body-file")
    source.add_argument("--body-json")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CP 生产环境部署资源管理")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    add_region(create)
    _add_body(create)
    _add_mutation(create)

    listing = sub.add_parser("list")
    add_region(listing)
    listing.add_argument("--name")
    listing.add_argument("--resource-region", action="append")
    listing.add_argument("--source", choices=["VKE", "DCP_BASE", "DCP_FED", "K8S"])
    listing.add_argument("--workspace-id")
    listing.add_argument("--resource-id", action="append")
    listing.add_argument("--page-size", type=int, default=100)
    listing.add_argument("--max", type=int, default=20)
    listing.add_argument("--all", action="store_true")
    listing.add_argument("--json", action="store_true")

    update = sub.add_parser("update")
    add_region(update)
    update.add_argument("--resource-id", required=True)
    _add_body(update)
    _add_mutation(update)

    delete = sub.add_parser("delete")
    add_region(delete)
    delete.add_argument("--resource-id", required=True)
    delete.add_argument("--force", action="store_true")
    _add_mutation(delete)
    return parser.parse_args(argv)


def build_request(args: argparse.Namespace) -> Tuple[str, Dict[str, Any]]:
    if args.command == "create":
        payload = load_json_object(args.body_file, args.body_json)
        allowed = {
            "Name", "Source", "VkeClusterId", "Kubeconfig", "Region", "Description",
            "OnlyForSpecifiedWorkspaces", "SpecifiedWorkspaceIds", "Identifier",
        }
        reject_unknown_fields(payload, "CreateDeployResource", allowed | {"Tags", "ClusterId"})
        require_fields(payload, "CreateDeployResource", ("Name", "Source"))
        if payload["Source"] not in {"VKE", "K8S"}:
            raise SystemExit("CreateDeployResource Source 仅支持 VKE 或 K8S")
        reject_fields(payload, "CreateDeployResource", ("Tags", "ClusterId"))
        return ACTION_BY_COMMAND[args.command], payload
    if args.command == "update":
        payload = load_json_object(args.body_file, args.body_json)
        allowed = {
            "Id", "Name", "Source", "VkeClusterId", "Kubeconfig", "Region",
            "Description", "OnlyForSpecifiedWorkspaces", "SpecifiedWorkspaceIds", "Identifier",
        }
        reject_unknown_fields(payload, "UpdateDeployResource", allowed | {"Tags", "ClusterId"})
        reject_fields(payload, "UpdateDeployResource", ("Tags", "ClusterId"))
        if not (set(payload) - {"Id"}):
            raise SystemExit("UpdateDeployResource 请求体至少需要一个可更新字段")
        return ACTION_BY_COMMAND[args.command], merge_explicit_fields(
            payload, Id=args.resource_id
        )
    if args.command == "delete":
        return ACTION_BY_COMMAND[args.command], {"Id": args.resource_id}

    filter_: Dict[str, Any] = {}
    mapping = {
        "Name": args.name,
        "Regions": args.resource_region,
        "Source": args.source,
        "WorkspaceId": normalize_optional_workspace(args.workspace_id, args.region)[0]
        if args.workspace_id
        else None,
        "Ids": args.resource_id,
    }
    for key, value in mapping.items():
        if value is not None:
            filter_[key] = value
    body: Dict[str, Any] = {"HideKubeconfig": True}
    if filter_:
        body["Filter"] = filter_
    return ACTION_BY_COMMAND[args.command], body


def execute(
    args: argparse.Namespace,
    client_factory: Callable[[str], Any] = client_from_env,
    input_func: Callable[[str], str] = input,
) -> int:
    action, body = build_request(args)
    workspace_filter = args.workspace_id if args.command == "list" else None
    _, region = normalize_optional_workspace(workspace_filter, args.region)
    if args.command == "list":
        request_ids: List[str] = []
        items, total = paginate_safely(
            paginate_numbered,
            client_factory(region),
            action,
            body,
            args.page_size,
            None if args.all else args.max,
            total_keys=("Total", "TotalCount"),
            request_ids=request_ids,
        )
        safe_items = redact_value(items)
        if args.json:
            print_json(
                {
                    "Action": action,
                    "RequestIds": request_ids,
                    "Total": total,
                    "Returned": len(safe_items),
                    "Items": safe_items,
                }
            )
        else:
            print(
                f"action={action} total={total} returned={len(safe_items)} "
                f"requestIds={','.join(request_ids) or '-'}"
            )
            for item in safe_items:
                print(
                    f"- id={item.get('Id')} name={item.get('Name')} "
                    f"source={item.get('Source')} region={item.get('Region')}"
                )
        return 0

    target = getattr(args, "resource_id", None)
    response = execute_mutation(
        args=args,
        action=action,
        body=body,
        region=region,
        client_factory=client_factory,
        confirm_target=target if args.command == "delete" else None,
        warning=(
            "WARNING: deleting this deploy resource may affect applications "
            "in multiple workspaces."
            if args.command == "delete"
            else None
        ),
        input_func=input_func,
    )
    if not args.dry_run:
        print_accepted(action, region, response, target)
    return 0


def main() -> int:
    return execute(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
