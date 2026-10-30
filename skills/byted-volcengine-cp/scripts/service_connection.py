"""Manage account-level CP service connections in allowlisted production regions."""
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
    call_safely,
    execute_mutation,
    normalize_optional_workspace,
    paginate_safely,
    print_accepted,
    print_json,
    reject_unknown_fields,
    require_fields,
)

ACTION_BY_COMMAND = {
    "create": "CreateServiceConnection",
    "update": "UpdateServiceConnection",
    "get": "GetServiceConnection",
    "list": "ListServiceConnections",
    "delete": "DeleteServiceConnection",
}
CONNECTION_TYPES = [
    "DockerRegistry",
    "ArtifactRegistry",
    "Github",
    "Gitlab",
    "Gitee",
    "BitbucketCloud",
    "Codeup",
    "PrivateGitLab",
    "BitbucketServer",
    "Gerrit",
    "Git",
    "Perforce",
    "Codebase",
    "Coding",
    "GitCode",
]


def _add_mutation(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")


def _add_body(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--body-file")
    source.add_argument("--body-json")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CP 生产环境服务连接管理")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("create", "update"):
        item = sub.add_parser(command)
        add_region(item)
        item.add_argument("--connection-id", required=True)
        _add_body(item)
        _add_mutation(item)

    get = sub.add_parser("get")
    add_region(get)
    get.add_argument("--connection-id", required=True)
    get.add_argument("--json", action="store_true")

    listing = sub.add_parser("list")
    add_region(listing)
    listing.add_argument("--name")
    listing.add_argument("--category", choices=["Registry", "CodeRepo"])
    listing.add_argument("--type", choices=CONNECTION_TYPES)
    listing.add_argument("--connection-id", action="append")
    listing.add_argument("--workspace-id")
    listing.add_argument("--page-size", type=int, default=100)
    listing.add_argument("--max", type=int, default=20)
    listing.add_argument("--all", action="store_true")
    listing.add_argument("--json", action="store_true")

    delete = sub.add_parser("delete")
    add_region(delete)
    delete.add_argument("--connection-id", required=True)
    delete.add_argument("--force", action="store_true")
    _add_mutation(delete)
    return parser.parse_args(argv)


def build_request(args: argparse.Namespace) -> Tuple[str, Dict[str, Any]]:
    if args.command in {"create", "update"}:
        payload = load_json_object(args.body_file, args.body_json)
        if args.command == "create":
            allowed = {
                "Id", "Name", "Description", "Type", "URL", "Credential",
                "IsAllWsShared", "SharedWorkspaceIds", "DisableNetworkVerify",
            }
            reject_unknown_fields(payload, "CreateServiceConnection", allowed)
            require_fields(
                payload,
                "CreateServiceConnection",
                ("Name", "Type", "Credential", "IsAllWsShared"),
                object_fields=("Credential",),
            )
            if payload["Type"] not in CONNECTION_TYPES:
                raise SystemExit(
                    f"CreateServiceConnection Type 不支持: {payload['Type']}"
                )
        else:
            allowed = {
                "Id", "Name", "Description", "URL", "Credential", "IsAllWsShared",
                "SharedWorkspaceIds", "DisableNetworkVerify",
            }
            reject_unknown_fields(payload, "UpdateServiceConnection", allowed)
            require_fields(
                payload,
                "UpdateServiceConnection",
                ("Name", "IsAllWsShared"),
            )
        body = merge_explicit_fields(payload, Id=args.connection_id)
        return ACTION_BY_COMMAND[args.command], body
    if args.command in {"get", "delete"}:
        return ACTION_BY_COMMAND[args.command], {"Id": args.connection_id}

    filter_: Dict[str, Any] = {}
    if args.name:
        filter_["Name"] = args.name
    type_info: Dict[str, Any] = {}
    if args.category:
        type_info["Category"] = args.category
    if args.type:
        type_info["Type"] = args.type
    if type_info:
        filter_["TypeInfo"] = type_info
    if args.connection_id:
        filter_["Ids"] = list(args.connection_id)
    if args.workspace_id:
        workspace_id, _ = normalize_optional_workspace(args.workspace_id, args.region)
        filter_["WorkspaceId"] = workspace_id
    return ACTION_BY_COMMAND[args.command], {"Filter": filter_} if filter_ else {}


def _print_connection(item: Dict[str, Any]) -> None:
    print(
        f"id={item.get('Id')} name={item.get('Name')} category={item.get('Category')} "
        f"type={item.get('Type')} allWs={item.get('IsAllWsShared')}"
    )


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
                _print_connection(item)
        return 0
    if args.command == "get":
        response = call_safely(client_factory(region), action, body, mutation=False)
        safe = redact_value(response)
        if args.json:
            print_json(safe)
        else:
            item = safe.get("Result") or safe
            _print_connection(item)
        return 0

    response = execute_mutation(
        args=args,
        action=action,
        body=body,
        region=region,
        client_factory=client_factory,
        confirm_target=args.connection_id if args.command == "delete" else None,
        warning="WARNING: pipelines may reference this account-level service connection."
        if args.command == "delete"
        else None,
        input_func=input_func,
    )
    if not args.dry_run:
        print_accepted(action, region, response, args.connection_id)
    return 0


def main() -> int:
    return execute(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
