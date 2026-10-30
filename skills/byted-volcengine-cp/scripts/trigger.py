"""Manage pipeline Webhook URLs and trigger lifecycle in CP production."""
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
    emit_sensitive_text,
    execute_mutation,
    extract_api_result,
    normalize_optional_workspace,
    paginate_safely,
    print_accepted,
    print_json,
    reject_unknown_fields,
    require_fields,
)

ACTION_BY_COMMAND = {
    "webhook-url": "CreatePipelineWebhookURL",
    "create": "CreateTrigger",
    "list": "ListTriggers",
    "update": "UpdateTrigger",
    "delete": "DeleteTrigger",
}
TRIGGER_TYPES = ["Webhook", "GitWebhook", "PerforceWebhook", "CRWebhook", "Schedule"]


def _add_target(parser: argparse.ArgumentParser) -> None:
    add_region(parser)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--pipeline-id", required=True)


def _add_mutation(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")


def _add_json_source(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--body-file")
    source.add_argument("--body-json")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CP 生产环境流水线触发器管理")
    sub = parser.add_subparsers(dest="command", required=True)

    webhook = sub.add_parser("webhook-url")
    _add_target(webhook)
    webhook.add_argument("--resource-id")
    webhook.add_argument("--type", choices=TRIGGER_TYPES)
    webhook.add_argument("--output-file")
    _add_mutation(webhook)

    create = sub.add_parser("create")
    _add_target(create)
    _add_json_source(create)
    _add_mutation(create)

    listing = sub.add_parser("list")
    _add_target(listing)
    listing.add_argument("--trigger-id", action="append")
    listing.add_argument("--name")
    listing.add_argument("--page-size", type=int, default=100)
    listing.add_argument("--max", type=int, default=20)
    listing.add_argument("--all", action="store_true")
    listing.add_argument("--json", action="store_true")

    update = sub.add_parser("update")
    _add_target(update)
    update.add_argument("--trigger-id", required=True)
    _add_json_source(update)
    _add_mutation(update)

    delete = sub.add_parser("delete")
    _add_target(delete)
    delete.add_argument("--trigger-id", required=True)
    delete.add_argument("--force", action="store_true")
    _add_mutation(delete)
    return parser.parse_args(argv)


def build_request(args: argparse.Namespace) -> Tuple[str, Dict[str, Any]]:
    workspace_id, _ = normalize_optional_workspace(args.workspace_id, args.region)
    targets: Dict[str, Any] = {
        "WorkspaceId": workspace_id,
        "PipelineId": args.pipeline_id,
    }
    if args.command == "webhook-url":
        if args.resource_id:
            targets["ResourceId"] = args.resource_id
        if args.type:
            targets["Type"] = args.type
        return ACTION_BY_COMMAND[args.command], targets
    if args.command == "create":
        payload = load_json_object(args.body_file, args.body_json)
        allowed = {
            "WorkspaceId", "PipelineId", "Name", "Description", "Type",
            "Configuration", "Parameters", "Resources", "Sources",
        }
        reject_unknown_fields(payload, "CreateTrigger", allowed)
        require_fields(
            payload,
            "CreateTrigger",
            ("Name", "Type", "Configuration"),
            object_fields=("Configuration",),
        )
        if payload["Type"] not in TRIGGER_TYPES:
            raise SystemExit(f"CreateTrigger Type 不支持: {payload['Type']}")
        return ACTION_BY_COMMAND[args.command], merge_explicit_fields(payload, **targets)
    if args.command == "list":
        filter_: Dict[str, Any] = {}
        if args.trigger_id:
            filter_["Ids"] = list(args.trigger_id)
        if args.name:
            filter_["Name"] = args.name
        if filter_:
            targets["Filter"] = filter_
        return ACTION_BY_COMMAND[args.command], targets
    if args.command == "update":
        payload = load_json_object(args.body_file, args.body_json)
        mutable = {"Name", "Description", "Configuration", "Parameters", "Resources", "Sources"}
        reject_unknown_fields(
            payload,
            "UpdateTrigger",
            mutable | {"WorkspaceId", "PipelineId", "Id"},
        )
        if not mutable.intersection(payload):
            raise SystemExit("UpdateTrigger 请求体至少需要一个可更新字段")
        targets["Id"] = args.trigger_id
        return ACTION_BY_COMMAND[args.command], merge_explicit_fields(payload, **targets)
    targets["Id"] = args.trigger_id
    return ACTION_BY_COMMAND[args.command], targets


def execute(
    args: argparse.Namespace,
    client_factory: Callable[[str], Any] = client_from_env,
    input_func: Callable[[str], str] = input,
) -> int:
    workspace_id, region = normalize_optional_workspace(args.workspace_id, args.region)
    action, body = build_request(args)
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
                    f"- id={item.get('Id')} name={item.get('Name')} "
                    f"type={item.get('Type')} updated={item.get('UpdateTime') or '-'}"
                )
        return 0

    confirm_target = args.trigger_id if args.command == "delete" else None
    response = execute_mutation(
        args=args,
        action=action,
        body=body,
        region=region,
        client_factory=client_factory,
        confirm_target=confirm_target,
        warning="WARNING: deleting a pipeline trigger." if confirm_target else None,
        input_func=input_func,
    )
    if args.dry_run:
        return 0
    if args.command == "webhook-url":
        result, request_id = extract_api_result(response)
        url = result.get("WebhookURL") or result.get("Url") or ""
        emit_sensitive_text(
            label="webhookURL",
            value=url,
            request_id=request_id,
            output_file=args.output_file,
        )
    else:
        print_accepted(action, region, response, getattr(args, "trigger_id", None))
    return 0


def main() -> int:
    return execute(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
