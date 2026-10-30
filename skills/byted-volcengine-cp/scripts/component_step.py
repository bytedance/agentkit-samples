"""Manage account-level custom component steps in CP production."""
from __future__ import annotations

import argparse
from typing import Any, Callable, Dict, List, Optional, Tuple

from cp_api import client_from_env, paginate_numbered, redact_value
from openapi_common import (
    add_region,
    execute_mutation,
    normalize_optional_workspace,
    paginate_safely,
    print_accepted,
    print_json,
)

ACTION_BY_COMMAND = {
    "list": "ListComponentStep",
    "create": "CreateComponentStep",
    "update": "UpdateComponentStep",
    "upgrade": "UpgradeComponentStep",
    "delete": "DeleteComponentStep",
}


def _read_yaml(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as stream:
            content = stream.read()
    except OSError as exc:
        raise SystemExit(f"无法读取 component-step YAML {path!r}: {exc}") from exc
    if not content.strip():
        raise SystemExit("component-step YAML 不能为空")
    return content


def _add_mutation(parser: argparse.ArgumentParser) -> None:
    add_region(parser)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CP 生产环境账号级自定义步骤管理")
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list")
    add_region(listing)
    builtin = listing.add_mutually_exclusive_group()
    builtin.add_argument("--builtin", dest="is_builtin", action="store_true")
    builtin.add_argument("--custom", dest="is_builtin", action="store_false")
    listing.set_defaults(is_builtin=False)
    listing.add_argument("--status", choices=["Enabled", "Disabled"])
    listing.add_argument("--name")
    listing.add_argument("--exact-name")
    listing.add_argument("--category")
    listing.add_argument("--component-id", action="append")
    listing.add_argument("--version")
    listing.add_argument("--page-size", type=int, default=100)
    listing.add_argument("--max", type=int, default=20)
    listing.add_argument("--all", action="store_true")
    listing.add_argument("--json", action="store_true")

    for command in ("create", "upgrade"):
        item = sub.add_parser(command)
        _add_mutation(item)
        item.add_argument("--yaml-file", required=True)

    update = sub.add_parser("update")
    _add_mutation(update)
    update.add_argument("--identifier", required=True)
    update.add_argument("--yaml-file")
    update.add_argument("--status", choices=["Enabled", "Disabled"])

    delete = sub.add_parser("delete")
    _add_mutation(delete)
    delete.add_argument("--identifier", required=True)
    delete.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def build_request(args: argparse.Namespace) -> Tuple[str, Dict[str, Any]]:
    if args.command == "list":
        filter_: Dict[str, Any] = {}
        mapping = {
            "IsBuiltin": args.is_builtin,
            "Status": args.status,
            "Name": args.name,
            "ExactStepName": args.exact_name,
            "Category": args.category,
            "Ids": args.component_id,
            "Version": args.version,
        }
        for key, value in mapping.items():
            if value is not None:
                filter_[key] = value
        return ACTION_BY_COMMAND[args.command], {"Filter": filter_} if filter_ else {}
    if args.command in {"create", "upgrade"}:
        return ACTION_BY_COMMAND[args.command], {"ComponentStepYaml": _read_yaml(args.yaml_file)}
    if args.command == "update":
        body: Dict[str, Any] = {"Identifier": args.identifier}
        if args.yaml_file:
            body["ComponentStepYaml"] = _read_yaml(args.yaml_file)
        if args.status:
            body["Status"] = args.status
        if len(body) == 1:
            raise SystemExit("UpdateComponentStep 至少需要 --yaml-file 或 --status")
        return ACTION_BY_COMMAND[args.command], body
    return ACTION_BY_COMMAND[args.command], {"Identifier": args.identifier}


def execute(
    args: argparse.Namespace,
    client_factory: Callable[[str], Any] = client_from_env,
    input_func: Callable[[str], str] = input,
) -> int:
    action, body = build_request(args)
    _, region = normalize_optional_workspace(None, args.region)
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
                    "TotalCount": total,
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
                    f"- identifier={item.get('Identifier')} name={item.get('Name')} "
                    f"version={item.get('Version')} status={item.get('Status')}"
                )
        return 0

    identifier = getattr(args, "identifier", None)
    response = execute_mutation(
        args=args,
        action=action,
        body=body,
        region=region,
        client_factory=client_factory,
        confirm_target=identifier if args.command == "delete" else None,
        warning="WARNING: deleting an account-level custom component step."
        if args.command == "delete"
        else None,
        input_func=input_func,
    )
    if not args.dry_run:
        print_accepted(action, region, response, identifier)
    return 0


def main() -> int:
    return execute(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
