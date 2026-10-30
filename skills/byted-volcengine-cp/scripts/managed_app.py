"""Safely operate the ten allowlisted CP managed-app OpenAPI actions in production."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cp_api import (  # noqa: E402
    client_from_env,
    extract_result,
    list_managed_app_change_records,
    load_json_object,
    merge_target_identifiers,
    normalize_workspace_ref,
    redact_secret,
    redact_value,
)

ACTION_BY_COMMAND = {
    "create": "CreateManagedApp",
    "deploy": "TriggerManagedAppDeploy",
    "scale": "TriggerManagedAppScaling",
    "rollback": "TriggerManagedAppRollback",
    "records": "ListManagedAppChangeRecords",
    "cancel": "CancelManagedAppChangeRecord",
    "steps": "ListManagedAppChangeSteps",
    "pods": "ListManagedAppPods",
    "logs": "GetManagedAppPodLog",
    "delete": "DeleteApp",
}
MUTATION_COMMANDS = {"create", "deploy", "scale", "rollback", "cancel", "delete"}
RECORD_TYPES = ("Deploy", "Scaling", "Rollback")
RECORD_STATUSES = ("Pending", "Running", "Succeeded", "Failed", "Canceled", "NotDeploy")
TERMINAL_RECORD_STATUSES = {"Succeeded", "Failed", "Canceled"}


def build_create_body(
    workspace_id: str, body_file: Optional[str], body_json: Optional[str]
) -> Dict[str, Any]:
    payload = load_json_object(body_file, body_json)
    for field in ("MetaInfo", "BasicConfig"):
        if not isinstance(payload.get(field), dict):
            raise SystemExit(f"CreateManagedApp 请求体缺少 object 字段 {field}")
    return merge_target_identifiers(payload, workspace_id)


def build_deploy_body(
    workspace_id: str, app_id: str, body_file: Optional[str], body_json: Optional[str]
) -> Dict[str, Any]:
    payload = load_json_object(body_file, body_json)
    for field in ("BasicConfig", "AdvancedConfig"):
        if not isinstance(payload.get(field), dict):
            raise SystemExit(f"TriggerManagedAppDeploy 请求体缺少 object 字段 {field}")
    return merge_target_identifiers(payload, workspace_id, app_id)


def build_scale_body(
    workspace_id: str,
    app_id: str,
    new_scale: int,
    description: Optional[str],
    deploy_resource_type: Optional[str],
    scale_type: Optional[str],
) -> Dict[str, Any]:
    if new_scale < 0:
        raise SystemExit("--new-scale 必须大于或等于 0")
    body: Dict[str, Any] = {
        "WorkspaceId": workspace_id, "AppId": app_id, "NewScale": new_scale
    }
    if description is not None:
        body["Description"] = description
    if deploy_resource_type is not None:
        body["DeployResourceType"] = deploy_resource_type
    if scale_type is not None:
        body["ScaleType"] = scale_type
    return body


def build_rollback_body(
    workspace_id: str, app_id: str, target_record_id: str, description: Optional[str]
) -> Dict[str, Any]:
    body = {
        "WorkspaceId": workspace_id,
        "AppId": app_id,
        "TargetChangeRecordId": target_record_id,
    }
    if description is not None:
        body["Description"] = description
    return body


def build_cancel_body(
    workspace_id: str, app_id: str, target_record_id: str
) -> Dict[str, Any]:
    return {
        "WorkspaceId": workspace_id,
        "AppId": app_id,
        "TargetChangeRecordId": target_record_id,
    }


def build_steps_body(workspace_id: str, app_id: str, record_id: str) -> Dict[str, Any]:
    return {"WorkspaceId": workspace_id, "AppId": app_id, "ChangeRecordId": record_id}


def build_pods_body(workspace_id: str, app_id: str, record_id: str) -> Dict[str, Any]:
    return build_steps_body(workspace_id, app_id, record_id)


def build_logs_body(
    workspace_id: str,
    app_id: str,
    record_id: str,
    pod_name: str,
    line_number: Optional[int],
) -> Dict[str, Any]:
    if line_number is not None and not 1 <= line_number <= 500:
        raise SystemExit("--line-number 必须在 1~500 之间")
    body = {
        "WorkspaceId": workspace_id,
        "AppId": app_id,
        "ChangeRecordId": record_id,
        "PodName": pod_name,
    }
    if line_number is not None:
        body["LineNumber"] = line_number
    return body


def build_delete_body(
    workspace_id: str, app_id: str, delete_cluster_resources: bool
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"WorkspaceId": workspace_id, "Id": app_id}
    if delete_cluster_resources:
        body["DeleteClusterResourceOrNot"] = True
    return body


def build_record_filter(
    ids: Optional[List[str]], types: Optional[List[str]], statuses: Optional[List[str]]
) -> Optional[Dict[str, Any]]:
    filter_: Dict[str, Any] = {}
    if ids:
        filter_["Ids"] = list(ids)
    if types:
        filter_["Types"] = list(types)
    if statuses:
        filter_["Statuses"] = list(statuses)
    return filter_ or None


def cancellation_settled(record_status: str, steps: List[Dict[str, Any]]) -> Optional[bool]:
    """Return settlement only for a terminal Canceled change record."""
    if record_status != "Canceled":
        return None
    return not any(step.get("Status") == "Cancelling" for step in steps)


def _add_target(parser: argparse.ArgumentParser, app_required: bool = True) -> None:
    parser.add_argument(
        "--workspace-id",
        required=True,
        help="32 位生产工作区 ID，支持 北京prod/柔佛prod 前缀",
    )
    parser.add_argument(
        "--region",
        choices=["cn-beijing", "ap-southeast-1"],
        default=None,
    )
    if app_required:
        parser.add_argument("--app-id", required=True)


def _add_mutation_safety(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dry-run", action="store_true", help="仅输出脱敏请求，不调用 OpenAPI")
    parser.add_argument("--yes", action="store_true", help="确认执行写操作")


def _add_json_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="输出脱敏 JSON")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CP 生产环境托管应用生命周期命令（仅含十个白名单 Action）"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="创建托管应用")
    _add_target(create, app_required=False)
    source = create.add_mutually_exclusive_group(required=True)
    source.add_argument("--body-file")
    source.add_argument("--body-json")
    _add_mutation_safety(create)

    deploy = sub.add_parser("deploy", help="触发托管应用部署")
    _add_target(deploy)
    source = deploy.add_mutually_exclusive_group(required=True)
    source.add_argument("--body-file")
    source.add_argument("--body-json")
    _add_mutation_safety(deploy)

    scale = sub.add_parser("scale", help="触发扩缩容")
    _add_target(scale)
    scale.add_argument("--new-scale", type=int, required=True)
    scale.add_argument("--description")
    scale.add_argument("--deploy-resource-type", choices=["K8sYaml"])
    scale.add_argument("--scale-type", choices=["ScaleUp", "ScaleDown"])
    _add_mutation_safety(scale)

    rollback = sub.add_parser("rollback", help="回滚到指定变更记录")
    _add_target(rollback)
    rollback.add_argument("--target-change-record-id", required=True)
    rollback.add_argument("--description")
    _add_mutation_safety(rollback)

    records = sub.add_parser("records", help="列出变更记录")
    _add_target(records)
    records.add_argument("--page-size", type=int, default=100)
    records.add_argument("--max", type=int, default=20)
    records.add_argument("--all", action="store_true")
    records.add_argument("--record-id", action="append")
    records.add_argument("--type", action="append", choices=RECORD_TYPES)
    records.add_argument("--status", action="append", choices=RECORD_STATUSES)
    _add_json_output(records)

    cancel = sub.add_parser("cancel", help="取消变更记录")
    _add_target(cancel)
    cancel.add_argument("--target-change-record-id", required=True)
    _add_mutation_safety(cancel)

    steps = sub.add_parser("steps", help="列出有序变更步骤")
    _add_target(steps)
    steps.add_argument("--change-record-id", required=True)
    steps.add_argument("--record-status", choices=RECORD_STATUSES)
    _add_json_output(steps)

    pods = sub.add_parser("pods", help="列出变更记录对应 Pod")
    _add_target(pods)
    pods.add_argument("--change-record-id", required=True)
    _add_json_output(pods)

    logs = sub.add_parser("logs", help="读取 Pod 日志")
    _add_target(logs)
    logs.add_argument("--change-record-id", required=True)
    logs.add_argument("--pod-name", required=True)
    logs.add_argument("--line-number", type=int)
    _add_json_output(logs)

    delete = sub.add_parser("delete", help="删除托管应用")
    _add_target(delete)
    delete.add_argument("--delete-cluster-resources", action="store_true")
    delete.add_argument("--force", action="store_true", help="跳过应用 ID 交互确认")
    _add_mutation_safety(delete)

    return parser.parse_args(argv)


def _build_request(args: argparse.Namespace, workspace_id: str) -> Tuple[str, Dict[str, Any]]:
    command = args.command
    action = ACTION_BY_COMMAND[command]
    if command == "create":
        body = build_create_body(workspace_id, args.body_file, args.body_json)
    elif command == "deploy":
        body = build_deploy_body(
            workspace_id, args.app_id, args.body_file, args.body_json
        )
    elif command == "scale":
        body = build_scale_body(
            workspace_id,
            args.app_id,
            args.new_scale,
            args.description,
            args.deploy_resource_type,
            args.scale_type,
        )
    elif command == "rollback":
        body = build_rollback_body(
            workspace_id, args.app_id, args.target_change_record_id, args.description
        )
    elif command == "cancel":
        body = build_cancel_body(workspace_id, args.app_id, args.target_change_record_id)
    elif command == "steps":
        body = build_steps_body(workspace_id, args.app_id, args.change_record_id)
    elif command == "pods":
        body = build_pods_body(workspace_id, args.app_id, args.change_record_id)
    elif command == "logs":
        body = build_logs_body(
            workspace_id,
            args.app_id,
            args.change_record_id,
            args.pod_name,
            args.line_number,
        )
    elif command == "delete":
        body = build_delete_body(workspace_id, args.app_id, args.delete_cluster_resources)
    else:
        raise AssertionError(f"records 使用分页路径，不应构造单请求: {command}")
    return action, body


def _print_json(value: Any) -> None:
    print(json.dumps(redact_value(value), ensure_ascii=False, indent=2))


def _print_mutation_result(
    action: str,
    region: str,
    workspace_id: str,
    app_id: Optional[str],
    response: Dict[str, Any],
) -> None:
    result, request_id = extract_result(response)
    returned_id = result.get("Id")
    label = "appId" if action == "CreateManagedApp" else "changeRecordId"
    fields = [
        f"accepted action={action}", f"region={region}", f"workspaceId={workspace_id}"
    ]
    if app_id:
        fields.append(f"appId={app_id}")
    if returned_id:
        fields.append(f"{label}={returned_id}")
    if request_id:
        fields.append(f"requestId={request_id}")
    print(" ".join(fields))
    if action in {
        "CreateManagedApp",
        "TriggerManagedAppDeploy",
        "TriggerManagedAppScaling",
        "TriggerManagedAppRollback",
    }:
        print(
            "request accepted only; deployment health is not proven. "
            "Inspect records, steps, Pods, and logs."
        )


def _print_records(
    workspace_id: str,
    region: str,
    items: List[Dict[str, Any]],
    total: int,
    as_json: bool,
) -> None:
    safe_items = redact_value(items)
    if as_json:
        _print_json(
            {
                "WorkspaceId": workspace_id,
                "Region": region,
                "TotalCount": total,
                "Returned": len(safe_items),
                "Items": safe_items,
            }
        )
        return
    print(
        f"workspaceId={workspace_id} region={region} "
        f"total={total} returned={len(safe_items)}"
    )
    for item in safe_items:
        status = item.get("Status")
        terminal = status in TERMINAL_RECORD_STATUSES
        print(
            f"- id={item.get('Id')} type={item.get('Type')} status={status} "
            f"terminal={str(terminal).lower()} version={item.get('AppVersion') or '-'} "
            f"updated={item.get('UpdateTime') or '-'}"
        )


def _print_items(
    kind: str,
    result: Dict[str, Any],
    as_json: bool,
    record_status: Optional[str] = None,
) -> None:
    safe_result = redact_value(result)
    if as_json:
        output: Dict[str, Any] = dict(safe_result)
        if kind == "steps" and record_status:
            output["CancellationSettled"] = cancellation_settled(
                record_status, safe_result.get("Items") or []
            )
        _print_json(output)
        return
    items = safe_result.get("Items") or []
    print(f"{kind}={len(items)}")
    if kind == "steps":
        for index, item in enumerate(items, 1):
            print(
                f"- order={index} id={item.get('ID') or item.get('Id')} "
                f"type={item.get('Type')} status={item.get('Status')} "
                f"phase={item.get('Phase') or '-'} message={item.get('Message') or '-'}"
            )
        if record_status == "Canceled":
            settled = cancellation_settled(record_status, items)
            print(f"cancellationSettled={str(settled).lower()}")
    else:
        for item in items:
            print(
                f"- name={item.get('Name')} status={item.get('Status')} "
                f"ip={item.get('Ip') or '-'} version={item.get('Version') or '-'}"
            )


def _confirm_delete(app_id: str, input_func: Callable[[str], str]) -> None:
    try:
        entered = input_func(f"Enter application ID {app_id} to confirm: ").strip()
    except EOFError as exc:
        raise SystemExit("无法进行交互式应用 ID 确认；确需非交互删除时使用 --force") from exc
    if entered != app_id:
        raise SystemExit("应用 ID 确认不匹配，已取消删除")


def _warn_delete_scope(delete_cluster_resources: bool) -> None:
    if delete_cluster_resources:
        warning = (
            "WARNING: deleting the CP application record and its runtime cluster resources."
        )
    else:
        warning = (
            "WARNING: deleting the CP application record; "
            "runtime resource deletion is not enabled."
        )
    print(warning, file=sys.stderr)


def execute(
    args: argparse.Namespace,
    client_factory: Callable[[str], Any] = client_from_env,
    input_func: Callable[[str], str] = input,
) -> int:
    workspace_id, region = normalize_workspace_ref(args.workspace_id, args.region)

    if args.command == "records":
        filter_ = build_record_filter(args.record_id, args.type, args.status)
        max_results = None if args.all else args.max
        client = client_factory(region)
        try:
            items, total = list_managed_app_change_records(
                client, workspace_id, args.app_id, args.page_size, max_results, filter_
            )
        except Exception as exc:  # noqa: BLE001 - sanitize read errors too
            raise SystemExit(
                f"ListManagedAppChangeRecords failed: {redact_value(str(exc))}"
            ) from exc
        _print_records(workspace_id, region, items, total, args.json)
        return 0

    action, body = _build_request(args, workspace_id)
    if args.command in MUTATION_COMMANDS:
        if args.command == "delete":
            _warn_delete_scope(args.delete_cluster_resources)
        if args.dry_run:
            _print_json(
                {
                    "DryRun": True,
                    "Action": action,
                    "Region": region,
                    "WorkspaceId": workspace_id,
                    "AppId": getattr(args, "app_id", None),
                    "Body": body,
                }
            )
            return 0
        if not args.yes:
            raise SystemExit(f"{action} 是写操作；请先用 --dry-run 复核，再加 --yes 执行")
        if args.command == "delete" and not args.force:
            _confirm_delete(args.app_id, input_func)

    client = client_factory(region)
    try:
        response = client.call(action, body)
    except Exception as exc:  # noqa: BLE001 - sanitize before presenting API/transport errors
        safe_error = str(redact_value(str(exc)))
        if args.command in MUTATION_COMMANDS and (
            isinstance(exc, TimeoutError) or "timed out" in str(exc).lower()
        ):
            raise SystemExit(
                f"{action} 请求超时，结果不明确；不要自动重试。"
                f"请先查询应用状态或变更记录。detail={safe_error}"
            ) from exc
        raise SystemExit(f"{action} failed: {safe_error}") from exc

    if args.command in MUTATION_COMMANDS:
        _print_mutation_result(
            action,
            region,
            workspace_id,
            getattr(args, "app_id", None),
            redact_value(response),
        )
        return 0

    result, request_id = extract_result(response)
    if args.command in {"steps", "pods"}:
        _print_items(args.command, result, args.json, getattr(args, "record_status", None))
        if request_id and not args.json:
            print(f"requestId={request_id}")
        return 0

    content = str(result.get("Content") or "")
    safe_content = redact_secret(content)
    if args.json:
        output = {"Content": safe_content, "RequestId": request_id}
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(safe_content)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    return execute(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
