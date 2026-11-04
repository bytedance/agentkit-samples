"""RuntimeTemplate 示例共享的参数、输出、配置状态与轮询逻辑。"""

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

from _config import (
    DEFAULT_CONFIG_PATH,
    clear_runtime_state,
    load_config,
    persist_runtime_state,
)
from _http_client import (
    AgentKitHttpError,
    RuntimeTemplateHttpClient,
    endpoint_scope,
    request_url,
)

TERMINAL_FAILURE = {"Failed"}
TRANSITIONAL = {"Building", "Updating", "Deleting"}
VISIBLE_TOKEN_FIELDS = {"ClientToken", "NextToken"}


def redact(value: Any) -> Any:
    """递归隐藏凭据和 Envs；模板环境变量会由服务明文保存。"""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if (
                re.search(r"key|secret|token|authorization|password", key, re.I)
                and key not in VISIBLE_TOKEN_FIELDS
            ):
                result[key] = "<redacted>"
            elif key == "Envs" and isinstance(item, dict):
                result[key] = {name: "<redacted>" for name in item}
            else:
                result[key] = redact(item)
        return result
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        for name, secret in os.environ.items():
            if secret and re.search(r"KEY|SECRET|TOKEN|PASSWORD", name):
                value = value.replace(secret, "<redacted>")
    return value


def print_json(value: Any) -> None:
    print(json.dumps(redact(value), indent=2, ensure_ascii=False), flush=True)


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
        "--workspace-id", help="Workspace ID；省略时由服务端选择 DEFAULT"
    )
    result.add_argument(
        "--config",
        default=os.getenv(
            "AGENTKIT_RUNTIME_TEMPLATE_CONFIG",
            str(DEFAULT_CONFIG_PATH),
        ),
        help="YAML 配置文件路径",
    )
    result.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="输出脱敏后的完整 JSON 事件",
    )
    result.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览请求，不访问网络或写入状态",
    )
    if resource:
        result.add_argument(
            "--runtime-template-id",
            help=("模板 ID；默认依次读取 AGENTKIT_RUNTIME_TEMPLATE_ID 和 config.yaml"),
        )
    if mutation:
        result.add_argument(
            "--client-token",
            type=client_token,
            default=uuid.uuid4().hex,
            help="幂等 token；重试原请求时必须复用",
        )
        result.add_argument(
            "--wait",
            action="store_true",
            help="提交后轮询到稳定状态",
        )
    return result


def client_token(value: str) -> str:
    trimmed = value.strip()
    if (
        not trimmed
        or len(trimmed.encode("ascii", errors="ignore")) != len(trimmed)
        or len(trimmed) > 64
        or any(ord(char) < 32 or ord(char) == 127 for char in trimmed)
    ):
        raise argparse.ArgumentTypeError(
            "client token must be 1-64 ASCII characters without control characters"
        )
    return trimmed


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def non_negative_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a non-negative integer") from None
    if number < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return number


def json_object(value: str) -> dict[str, Any]:
    """读取内联 JSON 对象或 @path/to/file.json。"""
    try:
        raw = (
            Path(value[1:]).expanduser().read_text() if value.startswith("@") else value
        )
        result = json.loads(raw)
    except (OSError, ValueError):
        raise argparse.ArgumentTypeError(
            "expected a JSON object or @path/to/file.json"
        ) from None
    if not isinstance(result, dict):
        raise argparse.ArgumentTypeError("expected a JSON object")
    return result


def string_map(value: dict[str, Any], name: str) -> dict[str, str]:
    if not all(
        isinstance(key, str) and key.strip() and isinstance(item, str)
        for key, item in value.items()
    ):
        raise RuntimeError(
            f"{name} must contain non-empty string keys and string values"
        )
    return value


def save_state(template: dict[str, Any]) -> Path:
    """将最小运行时状态写回 config.yaml。"""
    return persist_runtime_state(
        template["RuntimeTemplateId"],
        str(template.get("Status") or ""),
        endpoint_scope(),
        workspace_id=template.get("WorkspaceId"),
    )


def clear_state(runtime_template_id: str) -> None:
    clear_runtime_state(runtime_template_id)


def resolve_template_id(explicit: str | None, *, dry_run: bool) -> str:
    if explicit:
        return explicit
    from_env = os.getenv("AGENTKIT_RUNTIME_TEMPLATE_ID", "").strip()
    if from_env:
        return from_env
    runtime = load_config().runtime_template
    if runtime.id:
        if runtime.endpoint != endpoint_scope():
            raise RuntimeError(
                "config runtime state belongs to another endpoint; pass "
                "--runtime-template-id explicitly"
            )
        return runtime.id
    if dry_run:
        return "<runtime-template-id>"
    raise RuntimeError(
        "pass --runtime-template-id, set AGENTKIT_RUNTIME_TEMPLATE_ID, "
        "or create a template first"
    )


def validate_template(value: dict[str, Any]) -> dict[str, Any]:
    required = {"RuntimeTemplateId", "Name", "Status"}
    missing = sorted(required - value.keys())
    if missing:
        raise RuntimeError(
            "invalid RuntimeTemplate response; missing " + ", ".join(missing)
        )
    return value


def event(
    action: str,
    phase: str,
    body: dict[str, Any],
    *,
    response: dict[str, Any] | None = None,
    json_output: bool,
) -> None:
    if action in {
        "CreateRuntimeTemplate",
        "GetRuntimeTemplate",
        "ListRuntimeTemplates",
    }:
        workspace = os.getenv(
            "HARNESS_INFRA_WORKSPACE_ID", os.getenv("AGENTKIT_WORKSPACE_ID", "")
        ).strip()
        if workspace:
            body = {**body, "WorkspaceId": workspace}
    value: dict[str, Any] = {
        "Action": action,
        "Phase": phase,
        "Url": request_url(action),
        "Body": body,
    }
    if response is not None:
        value["Response"] = response
    if json_output:
        print_json(value)
        return
    labels = {
        "CreateRuntimeTemplate": "创建",
        "GetRuntimeTemplate": "查询",
        "ListRuntimeTemplates": "列出",
        "UpdateRuntimeTemplate": "更新",
        "DeleteRuntimeTemplate": "删除",
    }
    if phase == "dry-run":
        print(f"[预览] {labels[action]}模板，不发送请求。")
        print_json({"Url": value["Url"], "Body": body})
    elif phase == "request":
        print(f"[请求] 正在{labels[action]} RuntimeTemplate...")
        if body.get("ClientToken"):
            print(f"ClientToken: {body['ClientToken']}（重试原请求时复用）")
    elif response is not None:
        template_id = response.get("RuntimeTemplateId", "-")
        if action == "DeleteRuntimeTemplate":
            print(f"[完成] 已删除 RuntimeTemplate：{template_id}")
            return
        status = response.get("Status", "-")
        print(f"[完成] {labels[action]} RuntimeTemplate：{template_id}，状态 {status}")


def poll_template(
    client: RuntimeTemplateHttpClient,
    runtime_template_id: str,
    *,
    wanted: str,
    deleting: bool = False,
) -> dict[str, Any]:
    timeout = int(os.getenv("AGENTKIT_POLL_TIMEOUT_SECONDS", "900"))
    interval = int(os.getenv("AGENTKIT_POLL_INTERVAL_SECONDS", "5"))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = validate_template(
                client.call(
                    "GetRuntimeTemplate",
                    {"RuntimeTemplateId": runtime_template_id},
                )
            )
        except AgentKitHttpError as exc:
            if deleting and exc.status_code == 404:
                return {
                    "RuntimeTemplateId": runtime_template_id,
                    "Status": "Deleted",
                }
            raise
        print(
            f"[进度] {runtime_template_id}，状态 {value['Status']}",
            flush=True,
        )
        if value["Status"] == wanted:
            return value
        if value["Status"] in TERMINAL_FAILURE:
            raise RuntimeError(
                f"RuntimeTemplate entered terminal status {value['Status']}"
            )
        time.sleep(interval)
    raise RuntimeError(f"timed out waiting for RuntimeTemplate status {wanted}")
