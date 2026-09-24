"""CLI, output, resource ID cache and polling helpers for the five examples."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from _http_client import (
    EnvironmentResourceHttpClient,
    _positive_int_env,
    endpoint_scope,
    request_url,
)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if (
                re.search(r"key|secret|token|authorization|password", key, re.I)
                and key != "client_token"
            ):
                result[key] = "<redacted>"
            elif key == "env_vars" and isinstance(item, dict):
                result[key] = {name: "<redacted>" for name in item}
            else:
                result[key] = redact(item)
        return result
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)(Authorization=)[^&\s]+", r"\1<redacted>", value)
        for name, secret in os.environ.items():
            if secret and re.search(r"KEY|SECRET|TOKEN|PASSWORD", name):
                value = value.replace(secret, "<redacted>")
    return value


def print_json(value: Any) -> None:
    print(json.dumps(redact(value), indent=2, ensure_ascii=False), flush=True)


STATUS_LABELS = {
    "creating": "创建中",
    "ready": "已就绪",
    "updating": "更新中",
    "deleting": "删除中",
    "deleted": "已删除",
    "failed": "失败",
    "delete_failed": "删除失败",
}
ACTION_LABELS = {
    "CreateEnvironmentResource": "创建",
    "GetEnvironmentResource": "查询",
    "ListEnvironmentResources": "查询列表",
    "UpdateEnvironmentResource": "更新",
    "DeleteEnvironmentResource": "删除",
}


def hint(message: str) -> None:
    print(redact(message), flush=True)


def status_label(value: Any) -> str:
    return f"{STATUS_LABELS.get(value, '未知')} ({value or '-'})"


def operation_failed(value: dict[str, Any]) -> bool:
    operation = value.get("last_operation") or {}
    return value.get("status") in {"failed", "delete_failed"} or str(
        operation.get("status", "")
    ).startswith("failed")


def operation_completed(value: dict[str, Any], wanted: str) -> bool:
    operation = value.get("last_operation") or {}
    return (
        value.get("status") == wanted
        and operation.get("status") == "completed"
        and (
            wanted == "deleted"
            or operation.get("step") == "metadata"
            or value.get("desired_generation") == value.get("observed_generation")
        )
    )


def emit(event: dict[str, Any], *, json_output: bool = False) -> None:
    """Show concise user-facing progress, or the full redacted JSON event."""
    if json_output:
        print_json(event)
        return
    phase = event["phase"]
    action = event.get("action", "GetEnvironmentResource")
    label = ACTION_LABELS[action]
    if phase in {"request", "dry_run"}:
        body = event["body"]
        task = (
            "查询环境资源列表"
            if action == "ListEnvironmentResources"
            else f"{label}环境资源"
        )
        hint(
            f"[预览] {task}；不会发送请求或修改状态文件。"
            if phase == "dry_run"
            else f"[请求] 正在{task}..."
        )
        if body.get("resource_id"):
            hint(f"资源 ID: {body['resource_id']}")
        if body.get("expected_revision") is not None:
            hint(f"本次使用版本 (revision): {body['expected_revision']}")
        if body.get("target", {}).get("environment_id"):
            hint(
                f"目标环境: {body['target']['environment_id']} ({body['target']['type']})"
            )
        if body.get("update_mask"):
            hint(f"更新字段: {', '.join(body['update_mask'])}")
        if body.get("client_token"):
            hint(f"本次请求 token: {body['client_token']}（重试时复用）")
        if phase == "dry_run":
            hint("查看完整请求: 添加 --json")
        return
    if phase == "page":
        response = event["response"]
        items = response["data"]
        hint(
            f"[查询完成] 第 {event['page_number']} 页，{len(items)} 条资源，累计 {event['total']} 条。"
        )
        if not items:
            hint("本页没有符合条件的资源。")
        for item in items:
            hint(
                f"  {item['resource_id']} | {status_label(item.get('status'))} | 版本 {item.get('revision', '-')} | 环境 {item.get('environment_id') or item.get('target', {}).get('environment_id', '-')}"
            )
            operation = item.get("last_operation") or {}
            if operation_failed(item):
                hint(
                    f"    最近操作失败: {operation.get('error_code') or operation.get('status') or item.get('status')}"
                )
        if response.get("next_page"):
            hint(
                "还有下一页，正在继续查询..."
                if event.get("all_pages")
                else "还有下一页；添加 --all 查询全部，或用 --json 查看分页游标。"
            )
        return
    response = event.get("response", event)
    operation = response.get("last_operation") or {}
    if phase == "poll":
        prefix = "[失败]" if operation_failed(response) else "[进度]"
        hint(
            f"{prefix} {response['resource_id']} | {status_label(response.get('status'))} | 操作: {operation.get('status', '-')}"
            + (
                f" | 错误: {operation['error_code']}"
                if operation.get("error_code")
                else ""
            )
        )
        return
    wanted = "deleted" if action == "DeleteEnvironmentResource" else "ready"
    if operation_failed(response):
        hint("[失败] 资源操作失败；当前资源可能已回滚。")
    elif phase == "completed" or (
        action != "GetEnvironmentResource" and operation_completed(response, wanted)
    ):
        hint(
            f"[成功] 环境资源{label}成功。"
            if action != "GetEnvironmentResource"
            else "[完成] 资源已达到等待的目标状态。"
        )
    elif action == "GetEnvironmentResource":
        hint("[查询完成] 已获取资源当前信息。")
    else:
        hint(f"[已受理] {label}请求已提交，尚未确认操作完成。")
    hint(f"资源 ID: {response['resource_id']}")
    hint(f"当前状态: {status_label(response.get('status'))}")
    hint(f"当前版本 (revision): {response.get('revision', '-')}")
    for key, name in (("tool_id", "Sandbox Tool ID"), ("runtime_id", "Runtime ID")):
        if response.get(key):
            hint(f"{name}: {response[key]}")
    if operation_failed(response):
        hint(
            f"失败原因: {operation.get('error_code') or operation.get('status') or response.get('status')}"
        )
        if operation.get("status") == "failed_clean":
            hint("操作已回滚；请排查失败原因后再发起新操作。")
        hint("查看组件详情: python 02_get_environment_resource.py --json")
    if event.get("state_file"):
        hint(f"状态已保存: {event['state_file']}")
    if (
        phase == "response"
        and not event.get("waiting")
        and response.get("status") in {"creating", "updating", "deleting"}
    ):
        wanted = "deleted" if response["status"] == "deleting" else "ready"
        hint(
            f"继续等待: python 02_get_environment_resource.py --resource-id {response['resource_id']} --wait {wanted}"
        )


def run(main: Callable[[], None]) -> None:
    try:
        main()
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"[错误] {redact(str(exc))}", file=sys.stderr)
        raise SystemExit(1) from None


def parser(
    description: str,
    *,
    resource: bool = False,
    mutation: bool = False,
) -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=description)
    result.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Show full redacted JSON events instead of the Chinese summary",
    )
    result.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the redacted HTTP request; no network or state writes",
    )
    if resource:
        result.add_argument(
            "--resource-id",
            help="Resource ID (or AGENTKIT_RESOURCE_ID, then the local state file)",
        )
    if mutation:
        result.add_argument(
            "--client-token",
            default=uuid.uuid4().hex,
            type=client_token,
            help="Optional; generated when omitted. Reuse the printed token when retrying",
        )
        result.add_argument(
            "--wait",
            action="store_true",
            help="Poll Get after submitting the operation",
        )
    return result


def client_token(value: str) -> str:
    if not re.fullmatch(r"[\x21-\x7e]{1,64}", value):
        raise argparse.ArgumentTypeError(
            "client_token must be 1-64 visible ASCII characters, without spaces"
        )
    return value


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def add_target_argument(result: argparse.ArgumentParser) -> None:
    result.add_argument(
        "--target-type",
        choices=("ark", "agentkit"),
        default=os.getenv("AGENTKIT_RESOURCE_TARGET", "ark"),
        help="Target type (default: AGENTKIT_RESOURCE_TARGET or ark)",
    )


def required_env(name: str, *, dry_run: bool = False) -> str:
    value = os.getenv(name, "").strip()
    if not value and dry_run:
        return f"<{name}>"
    if not value:
        raise RuntimeError(f"set {name}")
    return value


def json_object(value: str) -> dict[str, Any]:
    """Accept a JSON object or @path/to/file.json."""
    try:
        raw = (
            Path(value[1:]).expanduser().read_text() if value.startswith("@") else value
        )
        result = json.loads(raw)
    except (ValueError, OSError):
        raise argparse.ArgumentTypeError(
            "expected a JSON object or @path/to/file.json"
        ) from None
    if not isinstance(result, dict):
        raise argparse.ArgumentTypeError("expected a JSON object")
    return result


def validate_env_vars(value: dict[str, Any]) -> dict[str, str]:
    if not all(isinstance(item, str) for item in value.values()):
        raise RuntimeError("sandbox.env_vars values must be strings")
    return value


def state_path() -> Path:
    configured = os.getenv("AGENTKIT_RESOURCE_STATE", "").strip()
    return (
        Path(configured).expanduser().resolve()
        if configured
        else Path(__file__).with_name(".environment_resource_state.json")
    )


def load_state() -> dict[str, Any]:
    path = state_path()
    if not path.is_file():
        raise RuntimeError(
            "state file is missing; run Create/Get first, or pass --resource-id "
            "and --expected-revision for Update/Delete"
        )
    state = json.loads(path.read_text())
    if not isinstance(state, dict) or state.get("endpoint") != endpoint_scope():
        raise RuntimeError(
            "state belongs to another endpoint; select another AGENTKIT_RESOURCE_STATE "
            "or supply the resource ID and revision explicitly"
        )
    return state


def resource_id(args: argparse.Namespace, state: dict[str, Any] | None = None) -> str:
    value = args.resource_id or os.getenv("AGENTKIT_RESOURCE_ID", "").strip()
    if not value:
        if state is None:
            state = load_state()
        value = state.get("resource_id")
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value
    ):
        raise RuntimeError("invalid resource_id")
    return value


def mutation_resource(args: argparse.Namespace) -> dict[str, Any]:
    """Resolve ID and revision from one state snapshot, with explicit overrides."""
    selected_id = args.resource_id or os.getenv("AGENTKIT_RESOURCE_ID", "").strip()
    state = load_state() if not selected_id or args.expected_revision is None else None
    rid = resource_id(args, state)
    revision = args.expected_revision
    if revision is None:
        assert state is not None
        if state.get("resource_id") != rid:
            raise RuntimeError(
                "selected resource_id does not match state; run Get for that resource "
                "or pass --expected-revision explicitly"
            )
        revision = state.get("revision")
        if type(revision) is not int or revision < 1:
            raise RuntimeError(
                "state revision must be a positive integer; run Get to refresh it "
                "or pass --expected-revision explicitly"
            )
    return {"resource_id": rid, "expected_revision": revision}


def save_resource(response: dict[str, Any]) -> None:
    if not response.get("resource_id"):
        raise RuntimeError(
            "response is missing resource_id; check the endpoint and API contract"
        )
    # Store identifiers and progress only, never requests, env_vars or credentials.
    state = {
        key: response.get(key)
        for key in (
            "resource_id",
            "revision",
            "status",
            "operation_id",
            "desired_generation",
            "observed_generation",
        )
    }
    state["endpoint"] = endpoint_scope()
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n")
    temporary.replace(path)


def preview(
    action: str, body: dict[str, Any], dry_run: bool, *, json_output: bool = False
) -> None:
    emit(
        {
            "phase": "dry_run" if dry_run else "request",
            "action": action,
            "method": "POST",
            "url": request_url(action),
            "body": body,
        },
        json_output=json_output,
    )


def wait_for_resource(
    client: EnvironmentResourceHttpClient,
    rid: str,
    wanted: str,
    initial: dict[str, Any] | None = None,
    *,
    json_output: bool = False,
) -> dict[str, Any]:
    timeout = _positive_int_env("AGENTKIT_WAIT_TIMEOUT_SECONDS", 20 * 60)
    interval = _positive_int_env("AGENTKIT_POLL_INTERVAL_SECONDS", 5)
    deadline = time.monotonic() + timeout
    value = initial
    operation_id = (initial or {}).get("operation_id")
    while True:
        if value is None:
            value = client.get_environment_resource({"resource_id": rid})
        save_resource(value)
        operation = value.get("last_operation") or {}
        emit(
            {
                "phase": "poll",
                "resource_id": rid,
                "status": value.get("status"),
                "revision": value.get("revision"),
                "desired_generation": value.get("desired_generation"),
                "observed_generation": value.get("observed_generation"),
                "last_operation": operation,
            },
            json_output=json_output,
        )
        if operation_id and value.get("operation_id") != operation_id:
            raise RuntimeError(
                "another operation replaced the submitted operation; inspect Get before continuing"
            )
        if operation_failed(value):
            raise RuntimeError(
                "resource operation failed (possibly rolled back); inspect last_operation and components.history"
            )
        # A rolled-back update can return ready while its operation failed and
        # observed_generation still refers to the previous working generation.
        if operation_completed(value, wanted):
            return value
        if value.get("status") == "deleted" and wanted != "deleted":
            raise RuntimeError("resource was deleted before reaching ready")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                "polling timed out; the server operation may still be running. Resume with 02_get_environment_resource.py --wait "
                + wanted
            )
        time.sleep(min(interval, remaining))
        value = None


def submit(
    action: str, body: dict[str, Any], args: argparse.Namespace, wanted: str = "ready"
) -> None:
    preview(action, body, args.dry_run, json_output=args.json_output)
    if args.dry_run:
        return
    client = EnvironmentResourceHttpClient()
    response = client.call(action, body)
    save_resource(response)
    emit(
        {
            "phase": "response",
            "action": action,
            "waiting": args.wait,
            "state_file": str(state_path()),
            "response": response,
        },
        json_output=args.json_output,
    )
    if args.wait:
        response = wait_for_resource(
            client,
            response["resource_id"],
            wanted,
            response,
            json_output=args.json_output,
        )
        emit(
            {"phase": "completed", "action": action, "response": response},
            json_output=args.json_output,
        )
