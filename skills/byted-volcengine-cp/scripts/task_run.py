"""List task runs and retrieve protected task-run log download URIs."""
from __future__ import annotations

import argparse
from typing import Any, Callable, Dict, List, Optional, Tuple

from cp_api import client_from_env, paginate_numbered, redact_value
from openapi_common import (
    add_region,
    call_safely,
    emit_sensitive_text,
    extract_api_result,
    normalize_optional_workspace,
    paginate_safely,
    print_json,
)

ACTION_BY_COMMAND = {
    "list": "ListTaskRuns",
    "download-uri": "GetTaskRunLogDownloadURI",
}


def _add_targets(parser: argparse.ArgumentParser) -> None:
    add_region(parser)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--pipeline-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-id", required=True)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CP 生产环境 taskRun 查询与日志 URI")
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list")
    _add_targets(listing)
    listing.add_argument("--task-run-id", action="append")
    listing.add_argument("--status", action="append")
    listing.add_argument("--page-size", type=int, default=100)
    listing.add_argument("--max", type=int, default=20)
    listing.add_argument("--all", action="store_true")
    listing.add_argument("--json", action="store_true")

    download = sub.add_parser("download-uri")
    _add_targets(download)
    download.add_argument("--task-run-id", required=True)
    download.add_argument("--step-name", required=True)
    download.add_argument("--output-file")
    return parser.parse_args(argv)


def build_request(args: argparse.Namespace) -> Tuple[str, Dict[str, Any]]:
    workspace_id, _ = normalize_optional_workspace(args.workspace_id, args.region)
    body: Dict[str, Any] = {
        "WorkspaceId": workspace_id,
        "PipelineId": args.pipeline_id,
        "PipelineRunId": args.run_id,
        "TaskId": args.task_id,
    }
    if args.command == "list":
        filter_: Dict[str, Any] = {}
        if args.task_run_id:
            filter_["Ids"] = list(args.task_run_id)
        if args.status:
            filter_["Statuses"] = list(args.status)
        if filter_:
            body["Filter"] = filter_
    else:
        body["TaskRunId"] = args.task_run_id
        body["StepName"] = args.step_name
    return ACTION_BY_COMMAND[args.command], body


def execute(
    args: argparse.Namespace,
    client_factory: Callable[[str], Any] = client_from_env,
) -> int:
    workspace_id, region = normalize_optional_workspace(args.workspace_id, args.region)
    action, body = build_request(args)
    client = client_factory(region)
    if args.command == "list":
        request_ids: List[str] = []
        items, total = paginate_safely(
            paginate_numbered,
            client,
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
                    "WorkspaceId": workspace_id,
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
                f"action={action} total={total} returned={len(safe_items)} "
                f"requestIds={','.join(request_ids) or '-'}"
            )
            for item in safe_items:
                print(
                    f"- id={item.get('Id')} name={item.get('Name')} "
                    f"status={item.get('Status')} retry={item.get('Retry', False)}"
                )
        return 0

    response = call_safely(client, action, body, mutation=False)
    result, request_id = extract_api_result(response)
    uri = result.get("Url") or result.get("URI") or result.get("Uri") or ""
    emit_sensitive_text(
        label="logDownloadURI",
        value=uri,
        request_id=request_id,
        output_file=args.output_file,
    )
    return 0


def main() -> int:
    return execute(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
