"""Shared safety and output helpers for explicit CP OpenAPI domain CLIs."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from cp_api import (
    client_from_env,
    extract_result,
    normalize_workspace_ref,
    redact_value,
    resolve_region,
    write_private_text,
)


def add_region(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--region",
        choices=["cn-beijing", "ap-southeast-1"],
        default=None,
        help="生产地域；默认读取 CP_REGION，否则为 cn-beijing",
    )


def normalize_optional_workspace(
    workspace_id: Optional[str], region: Optional[str]
) -> Tuple[Optional[str], str]:
    if workspace_id:
        return normalize_workspace_ref(workspace_id, region)
    return None, resolve_region(region)


def require_fields(
    payload: Dict[str, Any],
    action: str,
    fields: Iterable[str],
    object_fields: Iterable[str] = (),
) -> None:
    missing = [field for field in fields if field not in payload or payload[field] is None]
    if missing:
        raise SystemExit(f"{action} 请求体缺少必填字段: {', '.join(missing)}")
    invalid_objects = [
        field for field in object_fields if not isinstance(payload.get(field), dict)
    ]
    if invalid_objects:
        raise SystemExit(
            f"{action} 请求体字段必须为 object: {', '.join(invalid_objects)}"
        )


def reject_fields(payload: Dict[str, Any], action: str, fields: Iterable[str]) -> None:
    found = [field for field in fields if field in payload]
    if found:
        raise SystemExit(f"{action} 请求体包含不开放字段: {', '.join(found)}")


def reject_unknown_fields(
    payload: Dict[str, Any], action: str, allowed_fields: Iterable[str]
) -> None:
    unknown = sorted(set(payload) - set(allowed_fields))
    if unknown:
        raise SystemExit(f"{action} 请求体包含未知或不开放字段: {', '.join(unknown)}")


def print_json(value: Any) -> None:
    print(json.dumps(redact_value(value), ensure_ascii=False, indent=2))


def call_safely(client: Any, action: str, body: Dict[str, Any], mutation: bool) -> Dict[str, Any]:
    try:
        return client.call(action, body)
    except Exception as exc:  # noqa: BLE001 - sanitize before presenting API errors
        safe_error = redact_value(str(exc))
        if mutation and (isinstance(exc, TimeoutError) or "timed out" in str(exc).lower()):
            raise SystemExit(
                f"{action} 请求超时，结果不明确；不要自动重试。"
                f"请先调用对应 list/get API 检查资源状态。detail={safe_error}"
            ) from exc
        raise SystemExit(f"{action} failed: {safe_error}") from exc


def paginate_safely(
    paginator: Callable[..., Any],
    client: Any,
    action: str,
    body: Dict[str, Any],
    page_size: int,
    max_results: Optional[int],
    **kwargs: Any,
) -> Any:
    try:
        return paginator(
            client, action, body, page_size, max_results, **kwargs
        )
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - sanitize read errors
        raise SystemExit(f"{action} failed: {redact_value(str(exc))}") from exc


def execute_mutation(
    *,
    args: argparse.Namespace,
    action: str,
    body: Dict[str, Any],
    region: str,
    client_factory: Callable[[str], Any] = client_from_env,
    confirm_target: Optional[str] = None,
    warning: Optional[str] = None,
    input_func: Callable[[str], str] = input,
) -> Dict[str, Any]:
    if warning:
        print(warning, file=sys.stderr)
    if args.dry_run:
        print_json({"DryRun": True, "Action": action, "Region": region, "Body": body})
        return {}
    if not args.yes:
        raise SystemExit(f"{action} 是写操作；请先用 --dry-run 复核，再加 --yes 执行")
    if confirm_target is not None and not getattr(args, "force", False):
        try:
            entered = input_func(f"Enter target {confirm_target} to confirm: ").strip()
        except EOFError as exc:
            raise SystemExit("无法交互确认；确需非交互执行时使用 --force") from exc
        if entered != confirm_target:
            raise SystemExit("目标确认不匹配，已取消操作")
    client = client_factory(region)
    return call_safely(client, action, body, mutation=True)


def print_accepted(
    action: str,
    region: str,
    response: Dict[str, Any],
    target: Optional[str] = None,
) -> None:
    result, request_id = extract_api_result(redact_value(response))
    parts = [f"accepted action={action}", f"region={region}"]
    if target:
        parts.append(f"target={target}")
    if result.get("Id"):
        parts.append(f"id={result['Id']}")
    if request_id:
        parts.append(f"requestId={request_id}")
    print(" ".join(parts))


def extract_api_result(response: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
    """Extract Result when present, or a top-level response payload used by some CP APIs."""
    result, request_id = extract_result(response)
    if not result and "Result" not in response:
        result = {
            key: value for key, value in response.items() if key != "ResponseMetadata"
        }
    return result, request_id


def emit_sensitive_text(
    *,
    label: str,
    value: str,
    request_id: Optional[str],
    output_file: Optional[str],
) -> None:
    if output_file:
        write_private_text(output_file, value)
        print(f"{label}=written path={output_file} mode=0600 requestId={request_id or '-'}")
        return
    print(f"{label}=<redacted> present={str(bool(value)).lower()} requestId={request_id or '-'}")
