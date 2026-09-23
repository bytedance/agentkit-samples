# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Command entry point for external-customer domestic SMS workflows."""

from __future__ import annotations

import argparse
import calendar
import csv
import datetime
import hashlib
import hmac
import io
import json
import math
import os
import pathlib
import re
import signal
import subprocess
import sys
import threading
import uuid
from typing import Any, Dict, List, Mapping, Optional, Sequence, TextIO, Tuple
from urllib import parse, request

from action_contracts import PUBLIC_QUERY_ACTIONS
import batch_confirmation
import runtime_environment
from api_client import (
    LOGIN_PROCESS_LEASE_SECONDS,
    SmsApiClient,
    cleanup_private_auth_home,
    emit_json,
    prepare_cli_process_environment,
    select_cli_auth_home,
    ve_login_flow,
)
from qualification_display import qualification_display_adapter
from qualification_upload import QualificationUploadError
from qualification_wizard import run_qualification_wizard


PROCESS_TERMINATION_GRACE_SECONDS = 5
MESSAGE_GROUP_ID_HELP = "消息组 ID，取 list-message-groups 返回的 SubAccount"


class CliError(ValueError):
    def __init__(
        self,
        message: str,
        code: str = "validation_error",
        *,
        request_id: Optional[str] = None,
        log_id: Optional[str] = None,
        retryable: bool = False,
        outcome_unknown: bool = False,
        remediation: Optional[Mapping[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.request_id = request_id
        self.log_id = log_id
        self.retryable = retryable
        self.outcome_unknown = outcome_unknown
        self.remediation = dict(remediation) if remediation else None


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliError(message, "argument_error")


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=PROCESS_TERMINATION_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _run_login_process(argv: Sequence[str], env: Mapping[str, str]) -> None:
    process = subprocess.Popen(argv, env=dict(env))
    interrupted = False
    previous_handlers: Dict[int, Any] = {}

    def interrupt(signum: int, frame: Any) -> None:
        nonlocal interrupted
        interrupted = True
        _stop_process(process)

    if threading.current_thread() is threading.main_thread():
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, interrupt)
    try:
        try:
            return_code = process.wait(timeout=LOGIN_PROCESS_LEASE_SECONDS)
        except subprocess.TimeoutExpired as exc:
            _stop_process(process)
            raise CliError(
                "Volcengine login session expired before authorization completed",
                "auth_login_expired",
            ) from exc
        if interrupted:
            raise CliError("Volcengine login was cancelled", "auth_login_cancelled")
        if return_code != 0:
            raise CliError(
                "Volcengine login exited before authentication completed",
                "auth_login_failed",
            )
    finally:
        _stop_process(process)
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


def _local_error(action: str, exc: CliError) -> Dict[str, Any]:
    error_value: Dict[str, Any] = {
        "code": exc.code,
        "message": str(exc),
        "retryable": exc.retryable,
        "outcome_unknown": exc.outcome_unknown,
    }
    if exc.remediation:
        error_value["remediation"] = exc.remediation
    return {
        "success": False,
        "action": action,
        "request_id": exc.request_id,
        "log_id": exc.log_id,
        "result": None,
        "error": error_value,
    }


def _local_success(action: str, result: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "success": True,
        "action": action,
        "request_id": result.get("requestId"),
        "log_id": result.get("logId"),
        "result": dict(result),
        "error": None,
    }


def canonical_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize_signature(value: str) -> str:
    text = value.strip()
    bracket_pairs = (("【", "】"), ("[", "]"), ("［", "］"))
    for left, right in bracket_pairs:
        if text.startswith(left) and text.endswith(right):
            text = text[len(left) : -len(right)].strip()
            break
    if not 2 <= len(text) <= 25:
        raise CliError("signature content must contain 2 to 25 characters")
    return text


def _items(envelope: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    if not envelope.get("success"):
        return []
    result = envelope.get("result")
    if not isinstance(result, Mapping):
        return []
    values = (
        result.get("List")
        or result.get("list")
        or result.get("Items")
        or result.get("items")
        or []
    )
    return [value for value in values if isinstance(value, Mapping)]


def _require_query_success(envelope: Mapping[str, Any]) -> None:
    if not envelope.get("success"):
        error_value = envelope.get("error")
        message = (
            error_value.get("message")
            if isinstance(error_value, Mapping)
            else "resource query failed"
        )
        code = (
            error_value.get("code")
            if isinstance(error_value, Mapping)
            else "resource_query_failed"
        )
        remediation = (
            error_value.get("remediation")
            if isinstance(error_value, Mapping)
            and isinstance(error_value.get("remediation"), Mapping)
            else None
        )
        raise CliError(
            str(message),
            str(code or "resource_query_failed"),
            request_id=(
                str(envelope.get("request_id"))
                if envelope.get("request_id") is not None
                else None
            ),
            log_id=envelope.get("log_id"),
            retryable=(
                bool(error_value.get("retryable"))
                if isinstance(error_value, Mapping)
                else False
            ),
            outcome_unknown=(
                bool(error_value.get("outcome_unknown"))
                if isinstance(error_value, Mapping)
                else False
            ),
            remediation=remediation,
        )


_VARIABLE_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_MOBILE_RE = re.compile(r"^1[3-9]\d{9}$")
MAX_DIRECT_RECIPIENTS = 200
MAX_BATCH_FILE_BYTES = 50 * 1024 * 1024
MAX_BATCH_ROWS = 1_000_000
MAX_TEMPLATE_MATCH_PAGES = 100
CHINA_TZ = datetime.timezone(datetime.timedelta(hours=8))
CANCEL_LEAD_TIME = datetime.timedelta(minutes=1)


def _normalize_mobile(value: str) -> str:
    mobile = value.strip()
    if mobile.startswith("+86"):
        mobile = mobile[3:]
    if not _MOBILE_RE.fullmatch(mobile):
        raise CliError("invalid mainland China mobile number")
    return mobile


def _mask_mobile(value: str) -> str:
    return "{}****{}".format(value[:3], value[-4:])


def _send_local_inputs(
    args: argparse.Namespace,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    if len(args.mobile) > MAX_DIRECT_RECIPIENTS:
        raise CliError(
            "direct send accepts at most {} recipients".format(MAX_DIRECT_RECIPIENTS)
        )
    original = [_normalize_mobile(value) for value in args.mobile]
    try:
        variables = json.loads(args.template_params)
    except json.JSONDecodeError as exc:
        raise CliError("template-params must be a JSON object") from exc
    if not isinstance(variables, dict):
        raise CliError("template-params must be a JSON object")
    if any(not isinstance(key, str) for key in variables):
        raise CliError("template parameter names must be strings")

    seen = set()
    recipients: List[str] = []
    duplicates: List[str] = []
    for mobile in original:
        if mobile in seen:
            duplicates.append(mobile)
            continue
        seen.add(mobile)
        recipients.append(mobile)
    if duplicates and args.dedupe_policy == "reject":
        raise CliError("duplicate mobile numbers require dedupe-policy keep-first")
    return original, recipients, variables


def _template_param_names(item: Mapping[str, Any]) -> List[str]:
    raw = item.get("TemplateParams") or item.get("templateParams") or []
    names: List[str] = []
    for value in raw:
        if isinstance(value, Mapping):
            name = value.get("name") or value.get("Name") or value.get("ParamName")
        else:
            name = value
        if name is not None:
            names.append(str(name))
    return names


def _template_value(item: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        value = item.get(name)
        if value not in (None, "", []):
            return value
    return None


def _template_relationship_values(item: Mapping[str, Any], *names: str) -> set:
    values = _template_value(item, *names)
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple, set)):
        return set()
    return {str(value) for value in values if value not in (None, "")}


def _template_supports_sub_account(
    item: Mapping[str, Any], sub_account: str
) -> bool:
    values = _template_relationship_values(item, "SubAccounts", "subAccounts")
    return bool(values.intersection({sub_account, "*", "All"}))


def _normalized_template_signatures(
    item: Mapping[str, Any],
) -> Optional[set]:
    singular_names = ("Signature", "signature")
    plural_names = ("Signatures", "signatures")
    present = [name for name in singular_names + plural_names if name in item]
    if not present:
        return None

    normalized: Dict[str, set] = {}
    for name in present:
        raw = item[name]
        values = [raw] if isinstance(raw, str) else raw
        if not isinstance(values, (list, tuple, set)):
            values = []
        normalized[name] = {
            _normalize_signature(str(value))
            for value in values
            if value not in (None, "")
        }

    for names in (singular_names, plural_names):
        family = [normalized[name] for name in names if name in normalized]
        if len(family) > 1 and any(value != family[0] for value in family[1:]):
            raise CliError(
                "template signature aliases conflict", "contract_conflict"
            )

    singular = next(
        (normalized[name] for name in singular_names if name in normalized), None
    )
    plural = next(
        (normalized[name] for name in plural_names if name in normalized), None
    )
    if singular is not None and plural is not None:
        if singular != plural:
            raise CliError(
                "template signature aliases conflict", "contract_conflict"
            )
        return singular
    return singular if singular is not None else plural


def _template_supports_signature(
    item: Mapping[str, Any], signature: str
) -> bool:
    values = _normalized_template_signatures(item)
    return True if values is None else signature in values


def _template_content_body(content: str, signature: str) -> str:
    wrapper = "【{}】".format(signature)
    return content[len(wrapper) :] if content.startswith(wrapper) else content


def _query_pages(client: SmsApiClient, action: str, params: Mapping[str, Any], *, page_key: str = "Page", size_key: str = "PageSize"):
    """Read the complete catalog with the existing bounded pagination checks."""
    seen_page_fingerprints = set()
    received = 0
    page_size = params[size_key]
    for page in range(1, MAX_TEMPLATE_MATCH_PAGES + 1):
        response = client.call(action, {**params, page_key: page})
        _require_query_success(response)
        items = _items(response)
        fingerprint = canonical_digest({"items": items})
        if fingerprint in seen_page_fingerprints:
            raise CliError("resource pagination repeated a page", "resource_query_failed")
        seen_page_fingerprints.add(fingerprint)
        yield response
        total = response["result"].get("Total", response["result"].get("total"))
        if isinstance(total, str) and total.strip().isdigit():
            total = int(total.strip())
        received += len(items)
        if type(total) is int:
            if received >= total:
                return
            if not items:
                raise CliError("resource pagination ended before Total", "resource_query_failed")
        elif len(items) < page_size:
            return
    raise CliError("resource pagination exceeded the safe page limit", "resource_query_failed")


def _list_templates(client: SmsApiClient, args: argparse.Namespace) -> Dict[str, Any]:
    action, params = _query_params(args)
    if args.page is not None:
        if args.keyword:
            raise CliError("关键词匹配需要完整目录，不能同时指定 --page", "argument_error")
        return client.call(action, params)
    pages = list(_query_pages(client, action, params))
    items = [item for page in pages for item in _items(page)]
    scanned_total = len(items)
    if args.keyword:
        items = [
            item for item in items
            if any(
                word in str(item.get(field) or "")
                for word in args.keyword
                for field in ("TemplateName", "TemplateContent", "Description")
            )
        ]
    return {
        **pages[-1],
        "result": {"List": items, "Total": len(items), "ScannedTotal": scanned_total},
    }


def _match_template(client: SmsApiClient, args: argparse.Namespace) -> Dict[str, Any]:
    """逐条返回精确命中及原始记录；查询完整性与业务选择分别交给调用方。"""
    signature = _normalize_signature(args.signature)
    template_ids = set()
    errors = []
    try:
        for templates in _query_pages(client, "ListBatchTemplatesForAgent", {
            "SubAccounts": [args.sub_account], "Signatures": [signature], "PageSize": 100,
        }):
            for item in _items(templates):
                if not item.get("TemplateId") or item.get("BatchOnly") is True:
                    continue
                channel = item.get("ChannelType")
                if args.channel_type is not None and channel and channel != args.channel_type:
                    continue
                template_ids.add(str(item["TemplateId"]))
    except CliError as exc:
        errors.append(_local_error("ListBatchTemplatesForAgent", exc))

    candidates = []
    for template_id in sorted(template_ids):
        response = client.call("ListSecondTemplate", {
            "templateId": template_id, "signatures": signature,
            "subAccounts": [args.sub_account],
        })
        if not response.get("success"):
            errors.append({"templateId": template_id, **response})
            continue
        records = [
            item for item in _items(response)
            if _template_value(item, "TemplateId", "templateId") == template_id
            and _template_supports_signature(item, signature)
            and _template_supports_sub_account(item, args.sub_account)
        ]
        matching_records = []
        for item in records:
            channel = _template_value(item, "ChannelType", "channelType")
            if args.channel_type is not None and channel != args.channel_type:
                continue
            content = _template_value(item, "TemplateContent", "Content", "content")
            if isinstance(content, str) and _template_content_body(content, signature) == args.content:
                matching_records.append(item)
        if matching_records:
            candidates.append({
                "templateId": template_id, "signature": signature,
                "subAccount": args.sub_account, "templateRecords": records,
                "matchingRecords": matching_records,
            })
    # 失败仍是失败；保留已有候选供 Agent 继续查询，不把不完整查询解释成无匹配。
    classification = None
    if not errors:
        classification = "none" if not candidates else "single" if len(candidates) == 1 else "ambiguous"
    envelope = _local_success(args.command, {
        "classification": classification, "candidates": candidates,
        "complete": not errors, "errors": errors,
    })
    if errors:
        envelope.update(
            success=False, error=errors[0]["error"],
            request_id=errors[0].get("request_id"), log_id=errors[0].get("log_id"),
        )
    return envelope


def _render_content(content: str, variables: Mapping[str, Any]) -> str:
    return _VARIABLE_RE.sub(lambda match: str(variables[match.group(1)]), content)


def _segments(content: str, signature: str) -> int:
    length = len("【{}】{}".format(signature, content))
    return 1 if length <= 70 else int(math.ceil(length / 67.0))


def _template_for_preview(client: SmsApiClient, action: str, template_id: str,
                          signature: str, sub_account: str) -> Mapping[str, Any]:
    if action == "ListSecondTemplate":
        params = {"templateId": template_id, "signatures": signature, "subAccounts": [sub_account]}
    else:
        params = {"TemplateId": template_id, "SubAccounts": [sub_account], "Signatures": [signature], "Page": 1, "PageSize": 100}
    response = client.call(action, params)
    _require_query_success(response)
    records = [item for item in _items(response)
               if _template_value(item, "TemplateId", "templateId") == template_id
               and _template_supports_signature(item, signature)
               and _template_supports_sub_account(item, sub_account)]
    if not records:
        raise CliError("查询未取得该模板、签名和消息组的预览信息", "template_preview_unavailable")
    candidates = {}
    for item in records:
        content = _template_value(item, "TemplateContent", "Content", "content")
        variable_field = next((key for key in ("TemplateParams", "templateParams") if key in item), None)
        variables = item[variable_field] if variable_field is not None else None
        # 现有 Go DTO 的无变量切片可序列化为 null；原始记录仍完整保留。
        if variable_field is not None and variables is None and isinstance(content, str) and not _VARIABLE_RE.search(content):
            variables = []
        channel = _template_value(item, "ChannelType", "channelType")
        if not isinstance(content, str) or not isinstance(variables, list) or not isinstance(channel, str):
            raise CliError("接口返回的模板正文、变量或短信类型不完整", "invalid_response")
        # 审核记录保留原结构；只有用于内容预览的字段完全相同时才共用一个预览。
        view = {"TemplateId": template_id, "Signature": signature, "SubAccounts": [sub_account],
                "TemplateName": _template_value(item, "TemplateName", "Name", "name") or "",
                "TemplateContent": content, "TemplateParams": variables, "ChannelType": channel,
                "BatchOnly": item.get("BatchOnly", False)}
        for key in ("TaskFields", "Description"):
            if key in item:
                view[key] = item[key]
        key = canonical_digest({field: view.get(field) for field in (
            "TemplateContent", "TemplateParams", "ChannelType", "BatchOnly", "TaskFields")})
        candidates[key] = view
    if len(candidates) != 1:
        raise CliError("查询到多种正文、变量或短信类型，请先核对各条模板记录", "ambiguous_template_preview")
    # 具体消息组以模板返回的绑定为准；全消息组范围通过列表确认所选 ID。
    explicit_group = any(sub_account in _template_relationship_values(item, "SubAccounts", "subAccounts") for item in records)
    if not explicit_group:
        groups = client.call("GetSubAccountListForAgent", {
            "subAccount": sub_account, "pageIndex": 1, "pageSize": 100,
        })
        _require_query_success(groups)
        if not any(item.get("subAccountId") == sub_account and str(item.get("status")) == "1" for item in _items(groups)):
            raise CliError("所选消息组未出现在当前账号的启用列表中", "message_group_unavailable")
    view = next(iter(candidates.values()))
    view["TemplateRecords"] = records
    return view


def _send_summary(
    client: SmsApiClient,
    args: argparse.Namespace,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str], Dict[str, Any]]:
    original, recipients, variables = _send_local_inputs(args)
    signature = _normalize_signature(args.signature)

    selected_template = dict(_template_for_preview(
        client, "ListSecondTemplate", args.template_id, signature, args.sub_account,
    ))
    channel = selected_template.get("ChannelType")
    if channel not in {"CN_OTP", "CN_NTC", "CN_MKT"}:
        raise CliError("template channel type is not supported for SMS")
    selected_template["Content"] = _template_content_body(selected_template["TemplateContent"], signature)

    expected_variables = _template_param_names(selected_template)
    if len(set(expected_variables)) != len(expected_variables):
        raise CliError("template metadata contains duplicate variables")
    if set(variables) != set(expected_variables):
        raise CliError(
            "template parameter values must exactly match template variables"
        )
    content = str(
        selected_template.get("Content") or selected_template.get("content") or ""
    )
    if set(_VARIABLE_RE.findall(content)) != set(expected_variables):
        raise CliError("template content and variable metadata do not match")
    rendered = _render_content(content, variables)
    estimated_each = _segments(rendered, signature)
    duplicates = [
        value for index, value in enumerate(original) if value in original[:index]
    ]
    canonical: Dict[str, Any] = {
        "subAccount": args.sub_account,
        "signature": signature,
        "templateId": args.template_id,
        "originalRecipients": original,
        "dedupePolicy": args.dedupe_policy,
        "duplicates": duplicates,
        "recipients": recipients,
        "recipientVariables": [
            {"mobile": mobile, "variables": variables} for mobile in recipients
        ],
        "templateContentSha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "renderedContentSha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        "estimatedSegments": estimated_each * len(recipients),
    }
    preview: Dict[str, Any] = {
        "templateRecords": selected_template["TemplateRecords"],
        "subAccount": args.sub_account,
        "signature": signature,
        "templateId": args.template_id,
        "originalRecipients": [_mask_mobile(value) for value in original],
        "recipients": [_mask_mobile(value) for value in recipients],
        "recipientCount": len(recipients),
        "dedupePolicy": args.dedupe_policy,
        "duplicates": [_mask_mobile(value) for value in duplicates],
        "variableNames": sorted(variables),
        "contentSummary": {
            "templateSha256": canonical["templateContentSha256"],
            "renderedSha256": canonical["renderedContentSha256"],
        },
        "estimatedSegments": canonical["estimatedSegments"],
    }
    return canonical, preview, recipients, variables


def _sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with pathlib.Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_batch_snapshot(path: pathlib.Path) -> bytes:
    try:
        with pathlib.Path(path).open("rb") as stream:
            data = stream.read(MAX_BATCH_FILE_BYTES + 1)
    except OSError as exc:
        raise CliError("cannot read batch CSV") from exc
    if len(data) > MAX_BATCH_FILE_BYTES:
        raise CliError("batch CSV exceeds 50 MB")
    return data


def precheck_batch_csv(
    path_value: Any,
    template_variables: Sequence[str],
) -> Dict[str, Any]:
    if isinstance(path_value, (bytes, bytearray)):
        snapshot = bytes(path_value)
        file_size = len(snapshot)
        file_sha256 = hashlib.sha256(snapshot).hexdigest()
        stream = io.TextIOWrapper(
            io.BytesIO(snapshot), encoding="utf-8-sig", newline=""
        )
    else:
        path = pathlib.Path(path_value)
        if path.suffix.lower() != ".csv":
            raise CliError("batch v1 supports CSV files only")
        try:
            file_size = path.stat().st_size
            file_sha256 = _sha256_file(path)
            stream = path.open("r", encoding="utf-8-sig", newline="")
        except OSError as exc:
            raise CliError("cannot read batch CSV") from exc
    if not file_size:
        stream.close()
        raise CliError("batch CSV is empty")
    if file_size > MAX_BATCH_FILE_BYTES:
        stream.close()
        raise CliError("batch CSV exceeds 50 MB")
    try:
        rows = csv.DictReader(stream)
        columns = rows.fieldnames
    except (csv.Error, UnicodeDecodeError, OSError) as exc:
        stream.close()
        raise CliError("batch CSV is invalid") from exc
    expected = ["phone"] + list(template_variables)
    if columns != expected:
        stream.close()
        raise CliError(
            "batch CSV columns must exactly be: {}".format(",".join(expected))
        )
    seen = set()
    count = 0
    try:
        for row in rows:
            if None in row or any(value is None for value in row.values()):
                raise CliError("batch CSV contains an invalid or extra column")
            if not any(str(value).strip() for value in row.values()):
                raise CliError("batch CSV contains a blank row")
            mobile = _normalize_mobile(str(row["phone"]))
            if mobile in seen:
                raise CliError("batch CSV contains duplicate mobile numbers")
            seen.add(mobile)
            if any(not str(row[name]).strip() for name in template_variables):
                raise CliError("batch CSV contains an empty template variable")
            count += 1
            if count > MAX_BATCH_ROWS:
                raise CliError("batch CSV exceeds 1,000,000 rows")
    except UnicodeDecodeError as exc:
        raise CliError("batch CSV must be UTF-8") from exc
    except csv.Error as exc:
        raise CliError("batch CSV is invalid") from exc
    finally:
        stream.close()
    if count == 0:
        raise CliError("batch CSV has no recipients")
    return {
        "fileSha256": file_sha256,
        "fileSize": file_size,
        "columns": expected,
        "totalCount": count,
        "validCount": count,
        "invalidCount": 0,
        "dupCount": 0,
    }


def _next_month(value: datetime.datetime) -> datetime.datetime:
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def validate_batch_schedule(
    scheduled: bool,
    send_time: Optional[str],
    now: datetime.datetime,
) -> int:
    current = now.astimezone(CHINA_TZ)
    if not scheduled:
        if not datetime.time(8, 0) <= current.time() <= datetime.time(21, 30):
            raise CliError("immediate batch send is outside 08:00-21:30 Asia/Shanghai")
        return 0
    if not send_time:
        raise CliError("scheduled batch task requires send-time")
    try:
        parsed = datetime.datetime.fromisoformat(send_time)
    except ValueError as exc:
        raise CliError("send-time must be ISO 8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CHINA_TZ)
    parsed = parsed.astimezone(CHINA_TZ)
    if parsed <= current:
        raise CliError("scheduled send-time must be in the future")
    if parsed > _next_month(current):
        raise CliError("scheduled send-time must be no more than one month ahead")
    if not datetime.time(8, 0) <= parsed.time() <= datetime.time(21, 30):
        raise CliError("scheduled send-time must be within 08:00-21:30 Asia/Shanghai")
    return int(parsed.timestamp())


def _task_send_time(value: Any) -> Optional[datetime.datetime]:
    if value in (None, "", 0, "0"):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.datetime.fromtimestamp(float(value), tz=CHINA_TZ)
    try:
        parsed = datetime.datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise CliError("batch task send time is invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CHINA_TZ)
    return parsed.astimezone(CHINA_TZ)


def _default_uploader(url: str, source: Any) -> None:
    parsed = parse.urlsplit(url)
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or not any(
            hostname.endswith(host) if host.startswith(".") else hostname == host
            for host in runtime_environment.UPLOAD_HOSTS
        )
    ):
        raise CliError("batch upload URL is not an approved Volcengine TOS URL")

    class _NoRedirect(request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise CliError("batch upload redirect is not allowed")

    data = (
        bytes(source)
        if isinstance(source, (bytes, bytearray))
        else pathlib.Path(source).read_bytes()
    )
    upload = request.Request(url, data=data, method="PUT")
    upload.add_header("Content-Length", str(len(data)))
    with request.build_opener(_NoRedirect).open(upload, timeout=60) as response:
        if not 200 <= int(response.getcode()) < 300:
            raise CliError("batch file upload failed")


def _batch_task_fields(template: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    fields = template.get("TaskFields", [])
    if not isinstance(fields, list) or any(not isinstance(field, Mapping) for field in fields):
        raise CliError("模板任务字段格式无效", "invalid_response")
    names = [field.get("Name") for field in fields]
    if any(name != "content" for name in names) or len(names) != len(set(names)):
        raise CliError("当前版本不支持模板要求的任务字段，请升级 Skill", "unsupported_task_fields")
    return fields


def _batch_content_fields(template: Mapping[str, Any], content: Optional[str]) -> Dict[str, str]:
    fields = _batch_task_fields(template)
    if not fields:
        if content is not None:
            raise CliError("该模板不接受任务级正文，请按名单模板填写逐行变量", "argument_error")
        return {}
    field = fields[0]
    if content is None or content == "":
        if field.get("Required") is True:
            raise CliError("请先补齐模板要求的任务正文", "argument_error")
        return {}
    if not isinstance(content, str) or _VARIABLE_RE.search(content):
        raise CliError("请提供不含未填写变量的完整正文", "invalid_batch_content")
    limit = field.get("MaxLength")
    if isinstance(limit, int) and not isinstance(limit, bool) and limit > 0 and len(content) > limit:
        raise CliError("正文超过模板规定的长度", "invalid_batch_content")
    return {"content": content}


def _check_batch_content(client: SmsApiClient, args: argparse.Namespace, template: Mapping[str, Any], *, scope: Optional[str] = None) -> Mapping[str, Any]:
    fields = _batch_content_fields(template, args.content)
    if not fields:
        return {"Approved": True, "Reason": ""}
    body = {"subAccount": args.sub_account, "signature": template["Signature"], "templateId": args.template_id, **fields}
    options = {"expected_credential_scope": scope} if scope is not None else {}
    review = _batch_task_data(client.call("ValidateBatchTaskContentForAgent", body, **options))
    if review.get("Approved") is not True:
        reason = review.get("Reason")
        message = "正文审核未通过，请修改正文后重新预览"
        if isinstance(reason, str) and reason:
            message += "。审核原因：" + reason
        raise CliError(message, "batch_content_rejected")
    return review


def _batch_demo(client: SmsApiClient, sub_account: str, template_id: str, *, scope: Optional[str] = None) -> Mapping[str, Any]:
    options = {"expected_credential_scope": scope} if scope is not None else {}
    return _batch_task_data(client.call("TemplateUploadDemoForAgent", {"subAccount": sub_account, "templateId": template_id}, **options))


def _batch_demo_columns(demo: Mapping[str, Any]) -> List[str]:
    value = demo.get("value")
    if not isinstance(value, str) or not value:
        raise CliError("名单模板内容无效", "invalid_response")
    try:
        columns = next(csv.reader(io.StringIO(value.lstrip("\ufeff"))))
    except (csv.Error, StopIteration) as exc:
        raise CliError("名单模板表头无效", "invalid_response") from exc
    if not columns or columns[0] != "phone":
        raise CliError("名单模板表头无效", "invalid_response")
    return columns


def _batch_creation_result(result: Mapping[str, Any]) -> Dict[str, Any]:
    task_id = result.get("taskId")
    if not isinstance(task_id, str) or not task_id:
        raise CliError("任务创建结果缺少 taskId", "invalid_response", outcome_unknown=True)
    counts = {}
    for name in ("totalCount", "dupCount"):
        value = result.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise CliError("任务创建结果缺少有效的 {}".format(name), "invalid_response", outcome_unknown=True)
        counts[name] = value
    return {"taskId": task_id, **counts}


def _create_batch_task(args: argparse.Namespace, client: SmsApiClient, *, uploader: Any, now: Any, batch_snapshot: Optional[bytes] = None, expected_scope: Optional[str] = None, expected_batch_resources: Optional[str] = None) -> Dict[str, Any]:
    template, _ = _batch_resources(client, args.sub_account, args.signature, args.template_id)
    if expected_batch_resources is not None and canonical_digest(template) != expected_batch_resources:
        raise CliError("模板信息已变化，请重新预览", "resource_changed")
    scope = client.credential_scope
    if not scope:
        raise CliError("无法绑定当前登录身份，请检查授权", "confirmation_identity_unavailable")
    if expected_scope is not None and expected_scope != scope:
        raise CliError("登录身份已变化，请重新预览", "confirmation_identity_changed")
    fields = _batch_content_fields(template, args.content)
    _check_batch_content(client, args, template, scope=scope)
    demo = _batch_demo(client, args.sub_account, args.template_id, scope=scope)
    columns = _batch_demo_columns(demo)
    current = (now or (lambda: datetime.datetime.now(CHINA_TZ)))()
    send_time = validate_batch_schedule(args.scheduled, args.send_time, current)
    if batch_snapshot is None:
        source = pathlib.Path(args.file)
        if source.suffix.lower() != ".csv":
            raise CliError("batch v1 supports CSV files only")
        batch_snapshot = _read_batch_snapshot(source)
    report = precheck_batch_csv(batch_snapshot, columns[1:])
    body = {
        "subAccount": args.sub_account, "name": args.task_name,
        "signature": template["Signature"], "templateId": args.template_id,
        "scheduled": args.scheduled, "sendTime": send_time, **fields,
    }
    fingerprint = canonical_digest({"scope": scope, "action": "SetBatchTaskForAgent", "request": body, "fileSha256": report["fileSha256"]})
    upload = _batch_task_data(client.call("GetUploadTosURL", {"suffix": "csv"}, expected_credential_scope=scope))
    file_key, upload_url = upload.get("file"), upload.get("url")
    if not isinstance(file_key, str) or not file_key or not isinstance(upload_url, str) or not upload_url:
        raise CliError("upload authorization is incomplete", "invalid_response")
    uploader(upload_url, batch_snapshot)
    digest = canonical_digest({"fingerprint": fingerprint, "fileKey": file_key})
    store = batch_confirmation.ConfirmationStore()
    store.save_preview(digest, scope, fingerprint, file_key)
    prior_task_id = store.reserve(digest, scope, fingerprint)
    if prior_task_id:
        prior = store.task(scope, prior_task_id)
        return _local_success(args.command, {**prior["summary"], "taskId": prior_task_id, "alreadyCreated": True})
    body["fileUrl"] = file_key
    # 复用已保存的提交标识；未知结果由确认记录阻止重复创建。
    body["idempotencyKey"] = digest
    try:
        created = client.call("SetBatchTaskForAgent", body, expected_credential_scope=scope)
    except Exception as exc:
        raise CliError("任务创建结果待确认，请先查询任务，勿重复创建", "submission_outcome_unknown", outcome_unknown=True) from exc
    result = created.get("result")
    if not created.get("success") or not isinstance(result, Mapping):
        error = dict(created.get("error") or {})
        if error.get("request_sent") is False or (error.get("code") in batch_confirmation.CREATE_REJECTION_CODES and error.get("outcome_unknown") is not True):
            store.discard_rejected(digest)
            return created
        error.update({"outcome_unknown": True, "retryable": False})
        return {**created, "success": False, "result": None, "error": error}
    validated = _batch_creation_result(result)
    content = fields.get("content", template["Content"])
    summary = {
        "subAccount": args.sub_account, "taskName": args.task_name,
        "signature": template["Signature"], "templateId": args.template_id,
        "templateName": template["TemplateName"], "channelType": template["ChannelType"],
        "contentSha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "fileSha256": report["fileSha256"], "scheduled": args.scheduled, "sendTime": send_time,
        "totalCount": validated["totalCount"], "dupCount": validated["dupCount"],
    }
    saved = True
    try:
        store.save_task(scope, validated["taskId"], digest, summary)
        store.finish(digest, validated["taskId"])
    except batch_confirmation.BatchConfirmationError:
        saved = False
    return _local_success(args.command, {**summary, **validated, "status": "awaiting_confirmation", "localConfirmationSaved": saved})


def _batch_resources(
    client: SmsApiClient,
    sub_account: str,
    signature_value: str,
    template_id: str,
) -> Tuple[Mapping[str, Any], List[str]]:
    signature = _normalize_signature(signature_value)
    template = dict(_template_for_preview(
        client, "ListBatchTemplatesForAgent", template_id, signature, sub_account,
    ))
    content = _template_value(template, "TemplateContent", "Content", "content")
    if not isinstance(content, str) or not content:
        raise CliError("模板详情不完整，请检查接口版本", "invalid_response")
    template["Content"] = content
    channel = str(template.get("ChannelType") or "")
    if channel == "CN_OTP":
        raise CliError("OTP templates cannot be used for batch tasks")
    if channel not in {"CN_NTC", "CN_MKT"}:
        raise CliError("batch task requires a notification or marketing template")
    return template, _template_param_names(template)

def _batch_task_data(envelope: Mapping[str, Any]) -> Mapping[str, Any]:
    _require_query_success(envelope)
    result = envelope.get("result")
    if not isinstance(result, Mapping):
        raise CliError("batch task detail is missing")
    return result


def _query_params(args: argparse.Namespace) -> Tuple[str, Dict[str, Any]]:
    if args.command == "list-message-groups":
        params = {"pageIndex": args.page or 1, "pageSize": args.page_size}
        if args.name:
            params["subAccountName"] = args.name
        if args.all_status:
            params["allStatus"] = True
        return "GetSubAccountListForAgent", params
    if args.command == "message-group-detail":
        return "GetSubAccountDetail", {"subAccount": args.sub_account}
    if args.command == "list-qualifications":
        params: Dict[str, Any] = {
            "pageIndex": args.page,
            "pageSize": args.page_size,
        }
        if args.qualification_id is not None:
            params["id"] = args.qualification_id
        if args.material_name:
            params["materialName"] = args.material_name
        if args.status:
            params["status"] = args.status
        return "GetSignatureIdentificationList", params
    if args.command == "list-signatures":
        params = {"Page": args.page, "PageSize": args.page_size}
        if args.signature:
            params["Signature"] = _normalize_signature(args.signature)
        if args.exact_match:
            params["ExactMatch"] = True
        if args.project is not None:
            params["ProjectName"] = args.project
        for name, values in (
            ("SubAccounts", args.sub_account), ("ChannelTypes", args.channel_type),
            ("Industries", args.industry), ("Statuses", args.status),
        ):
            if values:
                params[name] = values
        return "ListSignaturesForAgent", params
    if args.command == "list-templates":
        params = {"Page": args.page if args.page is not None else 1, "PageSize": args.page_size}
        if args.template_id:
            params["TemplateId"] = args.template_id
        if args.sub_account:
            params["SubAccounts"] = args.sub_account
        if args.signature:
            params["Signatures"] = [
                _normalize_signature(value) for value in args.signature
            ]
        return "ListBatchTemplatesForAgent", params
    raise CliError("unknown query command")


def _cancel_batch_task(args: argparse.Namespace, client: SmsApiClient, *, now: Any) -> Dict[str, Any]:
    detail = client.call(
        "GetBatchTaskDetail",
        {"subAccount": args.sub_account, "taskId": args.task_id},
    )
    task = _batch_task_data(detail)
    summary = {
        "taskId": str(task.get("taskId") or task.get("TaskId") or ""),
        "subAccount": str(task.get("subAccount") or task.get("SubAccount") or ""),
        "sendTime": task.get("sendTime") or task.get("SendTime"),
    }
    if (
        summary["taskId"] != args.task_id
        or summary["subAccount"] != args.sub_account
    ):
        raise CliError("batch task identity does not match")
    status = int(task.get("status", task.get("Status", -1)))
    if status == 7:
        return _local_success(
            args.command,
            {"alreadyCanceled": True, "status": 7, "taskId": args.task_id},
        )
    if status not in {0, 1, 2, 3, 4, 5}:
        raise CliError("batch task can no longer be canceled")
    if bool(task.get("scheduled", task.get("Scheduled", False))):
        send_at = _task_send_time(summary["sendTime"])
        current = (now or (lambda: datetime.datetime.now(CHINA_TZ)))().astimezone(
            CHINA_TZ
        )
        if send_at is None or send_at <= current + CANCEL_LEAD_TIME:
            raise CliError(
                "batch task is inside the one-minute cancellation cutoff"
            )
    canceled = client.call(
        "DeleteBatchTask",
        {"subAccount": args.sub_account, "taskId": args.task_id},
    )
    if (
        not canceled.get("success")
        and isinstance(canceled.get("error"), Mapping)
        and canceled["error"].get("outcome_unknown")
    ):
        reconciled = client.call(
            "GetBatchTaskDetail",
            {"subAccount": args.sub_account, "taskId": args.task_id},
        )
        if reconciled.get("success"):
            reconciled_task = _batch_task_data(reconciled)
            if (
                int(
                    reconciled_task.get("status", reconciled_task.get("Status", -1))
                )
                == 7
            ):
                return _local_success(
                    args.command,
                    {"reconciled": True, "status": 7, "taskId": args.task_id},
                )
    return canceled


def _batch_launch(args: argparse.Namespace, client: SmsApiClient, *, now: Any) -> Dict[str, Any]:
    # 用本次任务查询绑定签名身份；后续确认仍使用同一身份和本地授权记录。
    task = _batch_task_data(client.call(
        "GetBatchTaskDetail",
        {"subAccount": args.sub_account, "taskId": args.task_id},
        use_cli=False,
    ))
    scope = client.credential_scope
    if not scope:
        raise CliError("无法绑定当前登录身份，请检查授权", "confirmation_identity_unavailable")
    store = batch_confirmation.ConfirmationStore()
    record = store.task(scope, args.task_id)
    if task.get("taskId") != args.task_id or task.get("subAccount") != args.sub_account:
        raise CliError("任务身份不匹配", "resource_changed")
    status = task.get("status")
    if isinstance(status, bool) or not isinstance(status, int):
        raise CliError("任务状态无效", "invalid_response")
    if status in {3, 4, 5, 6}:
        try:
            store.finish_launch(scope, args.task_id)
        except batch_confirmation.BatchConfirmationError:
            pass  # A local record failure cannot erase the authoritative task status.
        return _local_success(args.command, {"taskId": args.task_id, "alreadyStarted": True, "status": status})
    if status != 2:
        raise CliError("任务尚未通过校验或已结束，不能确认发送", "task_not_ready")
    created = record["summary"]
    content = task.get("sendContent")
    if not isinstance(content, str) or not content:
        template_id = str(task.get("templateId") or "")
        if not template_id or template_id != created.get("templateId"):
            raise CliError("任务模板信息缺失或已变化", "resource_changed")
        template, _ = _batch_resources(client, args.sub_account, created["signature"], template_id)
        content = template["Content"]
    scheduled = task.get("scheduled")
    if not isinstance(scheduled, bool):
        raise CliError("任务发送时间类型无效", "invalid_response")
    current = (now or (lambda: datetime.datetime.now(CHINA_TZ)))()
    send_at = _task_send_time(task.get("sendTime"))
    send_time = validate_batch_schedule(
        scheduled, send_at.isoformat() if send_at is not None else None, current
    )
    checked = {
        "subAccount": args.sub_account,
        "signature": task.get("signature"),
        "contentSha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "scheduled": scheduled,
        "sendTime": send_time,
        "totalCount": task.get("totalCount"),
    }
    if any(checked[key] != created[key] for key in checked):
        raise CliError("任务内容、人数或发送时间已变化，请重新创建并确认", "resource_changed")
    file_key = task.get("fileUrl")
    if not isinstance(file_key, str) or not file_key:
        raise CliError("任务名单信息缺失，不能确认发送", "invalid_response")
    summary = {
        **checked,
        "taskId": args.task_id,
        "taskName": task.get("taskName") or task.get("name"),
        "templateId": created.get("templateId"),
        "templateName": created.get("templateName"),
        "fileKeySha256": hashlib.sha256(file_key.encode("utf-8")).hexdigest(),
        "fileSha256": created["fileSha256"],
        "dupCount": created["dupCount"],
    }
    snapshot_digest = canonical_digest(summary)
    digest = canonical_digest({"scope": scope, "task": summary})
    if args.command == "batch-launch-preview":
        store.preview_launch(scope, args.task_id, digest, snapshot_digest)
        return _local_success(args.command, {
            "preview": {**summary, "content": content, "renderedContent": "【{}】{}".format(summary["signature"], content)},
            "digest": digest,
        })
    if args.authorization_text != "确认启动任务 {}".format(args.task_id):
        raise CliError("请明确确认启动当前任务", "authorization_mismatch")
    if (
        record["snapshotDigest"] != snapshot_digest
        or not hmac.compare_digest(record["digest"], args.preview_digest)
        or not hmac.compare_digest(digest, args.preview_digest)
    ):
        raise CliError("任务或确认摘要已变化，请重新预览", "digest_mismatch")
    store.reserve_launch(scope, args.task_id, digest)
    try:
        launched = client.call(
            "ConsentBatchTask",
            {"subAccount": args.sub_account, "taskId": args.task_id},
            expected_credential_scope=scope,
        )
    except Exception as exc:
        raise CliError("确认结果未知，请查询同一任务，勿重新创建", "submission_outcome_unknown", outcome_unknown=True) from exc
    if launched.get("success"):
        try:
            store.finish_launch(scope, args.task_id)
        except batch_confirmation.BatchConfirmationError:
            pass  # The known response and task ID remain authoritative.
        return _local_success(args.command, {"taskId": args.task_id, "subAccount": args.sub_account, "confirmed": True})
    error = launched.get("error") or {}
    if error.get("request_sent") is False:
        store.reject_launch(scope, args.task_id)
        return launched
    try:
        reconciled = client.call(
            "GetBatchTaskDetail",
            {"subAccount": args.sub_account, "taskId": args.task_id},
            expected_credential_scope=scope,
        )
    except Exception:
        reconciled = {"success": False}
    task = reconciled.get("result") if reconciled.get("success") else None
    if (
        isinstance(task, Mapping)
        and task.get("taskId") == args.task_id
        and task.get("subAccount") == args.sub_account
        and task.get("status") in {3, 4, 5, 6}
    ):
        try:
            store.finish_launch(scope, args.task_id)
        except batch_confirmation.BatchConfirmationError:
            pass
        return _local_success(args.command, {"taskId": args.task_id, "subAccount": args.sub_account, "confirmed": True, "reconciled": True})
    return {
        **launched, "success": False,
        "error": {**error, "outcome_unknown": True, "retryable": False},
    }


def _report_form_ready() -> None:
    print('LOCAL_FORM_STATUS {"state":"ready"}', file=sys.stderr, flush=True)


def execute(
    args: argparse.Namespace,
    client: SmsApiClient,
    *,
    uploader: Any = _default_uploader,
    now: Any = None,
    batch_snapshot: Optional[bytes] = None,
    expected_scope: Optional[str] = None,
    expected_batch_resources: Optional[str] = None,
) -> Dict[str, Any]:
    if args.command in {"batch-create", "batch-launch-preview", "batch-launch-submit"}:
        try:
            if args.command == "batch-create":
                return _create_batch_task(args, client, uploader=uploader, now=now, batch_snapshot=batch_snapshot, expected_scope=expected_scope, expected_batch_resources=expected_batch_resources)
            return _batch_launch(args, client, now=now)
        except batch_confirmation.BatchConfirmationError as exc:
            raise CliError(str(exc), exc.code, outcome_unknown=exc.outcome_unknown) from exc
    if args.command == "account-info":
        return client.call("ListAllSmsProduct", {})
    if args.command == "runtime-info":
        return _local_success(args.command, runtime_environment.CONFIG)
    if args.command == "auth-login":
        try:
            login_env = prepare_cli_process_environment(os.environ)
            login_env["HOME"] = select_cli_auth_home(login_env)
            if os.name == "nt":
                login_env["USERPROFILE"] = login_env["HOME"]
            try:
                help_result = subprocess.run(
                    ["ve", "login", "--help"], env=login_env,
                    capture_output=True, timeout=5,
                )
            except FileNotFoundError:
                raise
            except subprocess.TimeoutExpired as exc:
                raise CliError("CLI login inspection timed out", "ve_cli_timeout") from exc
            except PermissionError as exc:
                raise CliError("CLI executable cannot be started", "ve_cli_unexecutable") from exc
            except OSError as exc:
                raise CliError("Unable to inspect CLI login", "ve_cli_unavailable") from exc
            flow = ve_login_flow(help_result.stdout + help_result.stderr)
            if help_result.returncode != 0 or flow is None:
                raise CliError("CLI login capabilities are unavailable", "ve_login_unsupported")
            login_argv = ["ve", "login"]
            if args.remote:
                if flow != "loopback":
                    raise CliError(
                        "This CLI uses device authorization; run auth-login without --remote",
                        "ve_login_unsupported",
                    )
                login_argv.append("--remote")
            elif flow == "device_authorization":
                # 设备码先交给 Agent 展示，避免网页先于设备码出现。
                login_argv.append("--no-browser")
            elif args.no_browser:
                raise CliError(
                    "This CLI uses a local callback; use --remote when it is unavailable",
                    "ve_login_unsupported",
                )
            login_argv.extend([
                "--region", runtime_environment.REGION,
                "--endpoint-url", runtime_environment.SIGNIN_ENDPOINT,
            ])
            if args.profile:
                login_argv.extend(["--profile", args.profile])
            # Browser completion is authoritative only after an STS readiness probe.
            _run_login_process(login_argv, login_env)
            return client.auth_doctor()
        except FileNotFoundError as exc:
            raise CliError("Volcengine CLI is not installed", "ve_cli_missing") from exc
        except (OSError, RuntimeError) as exc:
            raise CliError(
                "Unable to start Volcengine login in the system temporary directory",
                "auth_temp_home_invalid",
            ) from exc
    if args.command == "auth-doctor":
        return client.auth_doctor()
    if args.command == "batch-wizard":
        from batch_wizard import run_batch_wizard
        draft = BatchFormDraft(client, args, uploader=uploader, now=now)
        result = run_batch_wizard(
            draft, display=qualification_display_adapter(args.display),
            on_display_ready=_report_form_ready,
        )
        return _local_success(args.command, result)
    if args.command == "auth-cleanup":
        return cleanup_private_auth_home(
            args.path,
            empty_only=args.empty_only,
        )

    if args.command == "qualification-wizard":
        try:
            result = run_qualification_wizard(
                client,
                display=qualification_display_adapter(args.display),
                on_display_ready=_report_form_ready,
            )
        except QualificationUploadError as exc:
            raise CliError(
                str(exc),
                exc.code,
                request_id=exc.request_id,
                log_id=exc.log_id,
                outcome_unknown=exc.outcome_unknown,
            ) from exc
        if result.get("outcomeUnknown") is True:
            raise CliError(
                "Qualification submission outcome is unknown; do not submit again",
                "qualification_submission_outcome_unknown",
                request_id=result.get("requestId"),
                log_id=result.get("logId"),
                outcome_unknown=True,
            )
        return _local_success(args.command, result)

    if args.command == "api-read":
        # Native parameters are HTTP data, never CLI flags or authentication options.
        return client.call(args.action, args.params, use_cli=False)

    if args.command == "match-template":
        return _match_template(client, args)

    if args.command == "list-message-groups" and args.page is None:
        action, params = _query_params(args)
        pages = list(_query_pages(client, action, params, page_key="pageIndex", size_key="pageSize"))
        items = [item for page in pages for item in _items(page)]
        return {**pages[-1], "result": {**pages[-1]["result"], "list": items, "total": len(items)}}
    if args.command == "list-templates":
        return _list_templates(client, args)

    if args.command.startswith("list-") or args.command == "message-group-detail":
        action, params = _query_params(args)
        return client.call(action, params)

    if args.command in {
        "signature-preview", "signature-submit", "template-preview", "template-submit",
    }:
        body = args.params
        digest = canonical_digest(body)
        if args.command.endswith("-preview"):
            return _local_success(args.command, {"preview": body, "digest": digest})
        if not hmac.compare_digest(args.preview_digest, digest):
            raise CliError(
                "input changed after preview; generate a new preview",
                "digest_mismatch",
            )
        action = "ApplySmsSignatureV2" if args.command == "signature-submit" else "ApplySmsTemplateV2"
        return client.call(action, body, use_cli=False)

    if args.command == "send-status":
        params = {"MessageId": args.message_id, "Page": args.page, "PageSize": args.page_size}
        if args.from_time is not None:
            params["FromTime"] = args.from_time
        if args.to_time is not None:
            params["ToTime"] = args.to_time
        if args.from_time is not None and args.to_time is not None and args.to_time < args.from_time:
            raise CliError("to-time 必须大于等于 from-time", "argument_error")
        if args.sub_account is not None:
            params["SubAccount"] = args.sub_account
        return client.call("ListSmsSendLogForAgent", params)
    if args.command in {"send-preview", "send-submit"}:
        if args.command == "send-submit":
            if not hmac.compare_digest(args.preview_digest, args.authorization_digest):
                raise CliError(
                    "authorization is not bound to this preview",
                    "authorization_mismatch",
                )
        canonical, preview, recipients, variables = _send_summary(client, args)
        digest = canonical_digest(canonical)
        if args.command == "send-preview":
            return _local_success(args.command, {"preview": preview, "digest": digest})
        if not hmac.compare_digest(args.preview_digest, digest):
            raise CliError(
                "send input or resource state changed after preview",
                "digest_mismatch",
            )
        return client.call(
            "SendSmsForAgent",
            {
                "SubAccount": args.sub_account,
                "Signature": canonical["signature"],
                "TemplateId": args.template_id,
                "Mobiles": ",".join(recipients),
                "TemplateParam": json.dumps(
                    variables,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
        )
    if args.command == "batch-content-check":
        body = {"subAccount": args.sub_account, "signature": _normalize_signature(args.signature), "templateId": args.template_id}
        if args.content is not None:
            body["content"] = args.content
        return client.call("ValidateBatchTaskContentForAgent", body)
    if args.command == "batch-template-demo":
        return client.call("TemplateUploadDemoForAgent", {"subAccount": args.sub_account, "templateId": args.template_id})
    if args.command == "batch-detail":
        return client.call("GetBatchTaskDetail", {"subAccount": args.sub_account, "taskId": args.task_id})
    if args.command == "batch-list":
        params = {
            "subAccount": args.sub_account,
            "pageIndex": args.page,
            "pageSize": args.page_size,
        }
        for target, value in (
            ("taskName", args.task_name),
            ("signature", args.signature),
            ("templateId", args.template_id),
        ):
            if value:
                params[target] = value
        return client.call("GetBatchTaskList", params)
    if args.command == "batch-precheck":
        demo = _batch_demo(client, args.sub_account, args.template_id)
        return _local_success(args.command, precheck_batch_csv(args.file, _batch_demo_columns(demo)[1:]))
    if args.command == "batch-cancel":
        return _cancel_batch_task(args, client, now=now)
    raise CliError("unsupported command", "argument_error")


class BatchFormDraft:
    """Own a private recipient snapshot through server validation and launch."""

    def __init__(self, client: SmsApiClient, args: argparse.Namespace, *, uploader: Any = _default_uploader, now: Any = None):
        self.client = client
        self.args = argparse.Namespace(**vars(args))
        if self.args.scheduled is False and self.args.send_time is not None:
            raise CliError("立即发送与定时时间冲突，请使用会话中确认的发送方式", "argument_error")
        self.uploader = uploader
        self.now = now
        self.revision = 0
        self.result: Optional[Dict[str, Any]] = None
        self._snapshot: Optional[bytes] = None
        self._report: Optional[Dict[str, Any]] = None
        self._preview: Optional[Dict[str, Any]] = None
        self._file_key: Optional[str] = None
        self._validation_task_id: Optional[str] = None
        self._scope: Optional[str] = None
        self._resource_digest: Optional[str] = None
        self._submitting = False
        self._test_send_lock = threading.Lock()
        self._test_send_outcome_unknown = False
        self._test_message_ids = {}
        self._closed = False
        self.metadata = self._resources()
        _check_batch_content(self.client, self.args, self._template, scope=self._scope)
        self._demo = _batch_demo(self.client, self.args.sub_account, self.args.template_id, scope=self._scope)
        columns = _batch_demo_columns(self._demo)
        self.metadata.update({"columns": columns, "templateVariables": columns[1:]})
    def _resources(self) -> Dict[str, Any]:
        template, variables = _batch_resources(self.client, self.args.sub_account, self.args.signature, self.args.template_id)
        fields = _batch_content_fields(template, self.args.content)
        self._scope = self.client.credential_scope
        if not self._scope:
            raise CliError("无法绑定当前登录身份，请检查授权", "confirmation_identity_unavailable")
        self._template = template
        self._resource_digest = canonical_digest({"template": template, "fields": fields})
        initial_time = _task_send_time(self.args.send_time) if self.args.send_time else None
        # 优先回填会话中的发送选择；未传方式的旧调用保留默认定时行为。
        scheduled_initial = self.args.scheduled if self.args.scheduled is not None else True
        return {
            "taskName": self.args.task_name,
            "subAccount": self.args.sub_account,
            "signature": template["Signature"],
            "templateId": self.args.template_id,
            "templateName": template["TemplateName"],
            "channelType": template["ChannelType"],
            "content": fields.get("content", template["Content"]),
            "description": template.get("Description", ""),
            "testSendSupported": not template.get("BatchOnly", False),
            "maxFileBytes": MAX_BATCH_FILE_BYTES,
            "scheduled": scheduled_initial,
            "sendTime": initial_time.strftime("%Y-%m-%dT%H:%M") if initial_time is not None else None,
            "timezone": "Asia/Shanghai",
        }
    def _editable(self) -> None:
        if self._closed or self._submitting or self.result is not None:
            raise CliError("本次任务创建已结束或正在处理", "batch_form_closed")

    def clear_file(self) -> None:
        self._editable()
        self._snapshot = self._report = self._preview = None
        self._file_key = None
        self.revision += 1

    def set_file(self, data: bytes) -> Dict[str, Any]:
        self.clear_file()
        if not isinstance(data, (bytes, bytearray)):
            raise CliError("群发文件内容无效", "invalid_batch_file")
        snapshot = bytes(data)
        if not snapshot:
            raise CliError("群发文件不能为空", "invalid_batch_file")
        if len(snapshot) > MAX_BATCH_FILE_BYTES:
            raise CliError("群发文件不能超过 50 MB", "invalid_batch_file")
        self._snapshot = snapshot
        self._report = {
            "fileSize": len(snapshot),
            "fileSha256": hashlib.sha256(snapshot).hexdigest(),
        }
        return {"revision": self.revision, "file": dict(self._report)}

    def template_file(self) -> Tuple[str, str, bytes]:
        self._editable()
        result = self._demo
        value = result.get("value")
        if not isinstance(value, str) or not value:
            raise CliError("名单模板内容无效", "invalid_response")
        file_name = pathlib.Path(str(result.get("fileName") or "TemplateUploadDemo.csv")).name
        if not file_name.lower().endswith(".csv"):
            file_name = "TemplateUploadDemo.csv"
        content_type = str(result.get("contentType") or "text/csv; charset=utf-8")
        return file_name, content_type, value.encode("utf-8")
    def _refresh_resources(self) -> None:
        old_scope = self._scope
        old_digest = self._resource_digest
        metadata = self._resources()
        if self._scope != old_scope:
            self.clear_file()
            raise CliError(
                "登录身份已变化，请重新选择文件和校验",
                "confirmation_identity_changed",
            )
        if self._resource_digest != old_digest:
            self._preview = None
            self.revision += 1
            raise CliError("群发资源已变化，请重新打开表单", "resource_changed")
        metadata.update({"columns": self.metadata["columns"], "templateVariables": self.metadata["templateVariables"]})
        self.metadata = metadata
    def _ensure_uploaded(self) -> str:
        if self._snapshot is None:
            raise CliError("请先在页面选择 CSV 文件", "batch_file_required")
        if self._file_key is not None:
            return self._file_key
        upload = _batch_task_data(
            self.client.call(
                "GetUploadTosURL",
                {"suffix": "csv"},
                expected_credential_scope=self._scope,
            )
        )
        file_key = upload.get("file")
        upload_url = upload.get("url")
        if not isinstance(file_key, str) or not file_key:
            raise CliError("上传授权缺少文件标识", "invalid_response")
        if not isinstance(upload_url, str) or not upload_url:
            raise CliError("上传授权缺少地址", "invalid_response")
        self.uploader(upload_url, self._snapshot)
        self._file_key = file_key
        return file_key

    def _create_body(self, send_time: int, file_key: str) -> Dict[str, Any]:
        return {
            "subAccount": self.args.sub_account,
            "name": self.args.task_name,
            "signature": self.metadata["signature"],
            "templateId": self.args.template_id,
            "scheduled": self.args.scheduled,
            "sendTime": send_time,
            "fileUrl": file_key,
            **_batch_content_fields(self._template, self.args.content),
        }
    def send_test_sms(
        self,
        phone: Any,
        template_params: Any,
    ) -> Dict[str, Any]:
        self._editable()
        if not self.metadata["testSendSupported"]:
            raise CliError(
                "该模板不支持测试短信",
                "test_send_not_supported",
            )
        if not isinstance(phone, str) or not isinstance(template_params, Mapping):
            raise CliError("测试短信参数格式不正确", "argument_error")
        mobile = _normalize_mobile(phone)
        expected = list(self.metadata["templateVariables"])
        if set(template_params) != set(expected) or len(template_params) != len(expected):
            raise CliError(
                "测试参数必须与模板变量完全一致",
                "template_param_mismatch",
            )
        normalized_params = {}
        for name in expected:
            value = template_params[name]
            if not isinstance(value, str) or not value:
                raise CliError(
                    "请填写测试参数 {}".format(name),
                    "template_param_required",
                )
            normalized_params[name] = value
        self._refresh_resources()
        with self._test_send_lock:
            if self._test_send_outcome_unknown:
                raise CliError(
                    "上一次测试短信结果未知，请勿重复发送",
                    "test_send_outcome_unknown",
                    outcome_unknown=True,
                )
            requested_at = int((self.now or (lambda: datetime.datetime.now(CHINA_TZ)))().timestamp())
            try:
                envelope = self.client.call(
                    "SendSmsForAgent",
                    {
                        "SubAccount": self.args.sub_account,
                        "Signature": self.metadata["signature"],
                        "TemplateId": self.args.template_id,
                        "Mobiles": mobile,
                        "TemplateParam": (
                            json.dumps(
                                normalized_params,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                            if normalized_params
                            else ""
                        ),
                    },
                    expected_credential_scope=self._scope,
                )
            except Exception:
                self._test_send_outcome_unknown = True
                return {
                    "status": "test_sms_outcome_unknown",
                    "outcomeUnknown": True,
                }
        if envelope.get("success"):
            result = envelope.get("result")
            if not isinstance(result, Mapping):
                self._test_send_outcome_unknown = True
                raise CliError(
                    "测试短信返回结果无效",
                    "invalid_response",
                    outcome_unknown=True,
                )
            message_id = result.get("MessageId")
            message_ids = result.get("MessageIds")
            if not message_id and not message_ids:
                self._test_send_outcome_unknown = True
                raise CliError(
                    "测试短信返回结果缺少 Message ID",
                    "invalid_response",
                    outcome_unknown=True,
                )
            if isinstance(message_id, str) and message_id:
                self._test_message_ids[message_id] = requested_at
            if isinstance(message_ids, list):
                self._test_message_ids.update({
                    value: requested_at for value in message_ids if isinstance(value, str) and value
                })
            return {
                "status": "test_sms_submitted",
                "messageId": message_id,
                "messageIds": message_ids,
                "outcomeUnknown": False,
            }
        error = envelope.get("error") or {}
        if error.get("outcome_unknown") is True:
            self._test_send_outcome_unknown = True
            return {
                "status": "test_sms_outcome_unknown",
                "outcomeUnknown": True,
            }
        raise CliError(
            str(error.get("message") or "测试短信发送失败"),
            str(error.get("code") or "test_send_failed"),
        )

    def test_sms_status(self, message_id: Any) -> Dict[str, Any]:
        self._editable()
        if not self.metadata["testSendSupported"]:
            raise CliError("该模板不支持测试短信", "test_send_not_supported")
        if (
            not isinstance(message_id, str)
            or not message_id
            or message_id not in self._test_message_ids
        ):
            raise CliError("测试短信 Message ID 无效", "invalid_test_message_id")
        query_end = int((self.now or (lambda: datetime.datetime.now(CHINA_TZ)))().timestamp()) + 1
        envelope = self.client.call(
            "ListSmsSendLogForAgent",
            {"MessageId": message_id, "Page": 1, "PageSize": 1,
             "FromTime": self._test_message_ids[message_id], "ToTime": query_end},
            expected_credential_scope=self._scope,
        )
        _require_query_success(envelope)
        items = _items(envelope)
        log = next(
            (
                item
                for item in items
                if str(item.get("MessageId") or item.get("MessageID") or "")
                == message_id
            ),
            None,
        )
        if log is None:
            return {"messageId": message_id, "found": False}
        return {
            "messageId": message_id,
            "found": True,
            "status": log.get("Status"),
            "sendTime": log.get("SendTime"),
            "receiptTime": log.get("ReceiptTime"),
            "count": log.get("Count"),
            "errorCode": log.get("ErrorCode"),
            "errorType": log.get("ErrorType"),
            "errorMessage": log.get("ErrorMessage"),
            "channelType": log.get("ChannelType"),
        }

    def _create_attempt(self, send_time: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        file_key = self._ensure_uploaded()
        body = self._create_body(send_time, file_key)
        body["idempotencyKey"] = uuid.uuid4().hex
        envelope = self.client.call(
            "SetBatchTaskForAgent",
            body,
            expected_credential_scope=self._scope,
        )
        if not envelope.get("success"):
            error = envelope.get("error") or {}
            # 与 CLI 创建入口一致，系统错误可能发生在落库之后，不能换 key 重建。
            rejected = error.get("request_sent") is False or (
                error.get("code") in batch_confirmation.CREATE_REJECTION_CODES
                and error.get("outcome_unknown") is not True
            )
            raise CliError(
                str(error.get("message") or "群发任务创建失败"),
                str(error.get("code") or "batch_creation_failed"),
                outcome_unknown=not rejected,
            )
        result = envelope.get("result")
        if not isinstance(result, Mapping):
            raise CliError(
                "群发任务创建结果无效",
                "invalid_response",
                outcome_unknown=True,
            )
        return _batch_creation_result(result), envelope

    def _terminal_error(self, code: str, *, outcome_unknown: bool) -> Dict[str, Any]:
        self.result = {
            "subAccount": self.args.sub_account,
            "status": (
                "batch_creation_outcome_unknown"
                if outcome_unknown
                else "batch_creation_failed"
            ),
            "code": code,
            "outcomeUnknown": outcome_unknown,
            "fallbackAllowed": False,
        }
        self._snapshot = None
        return dict(self.result)

    def preview(self, scheduled: bool, send_time: Optional[str]) -> Dict[str, Any]:
        self._editable()
        self._preview = None
        self.revision += 1
        if not isinstance(scheduled, bool) or (send_time is not None and not isinstance(send_time, str)):
            raise CliError("发送时间格式不正确", "argument_error")
        if self._snapshot is None:
            raise CliError("请先在页面选择 CSV 文件", "batch_file_required")
        current = (self.now or (lambda: datetime.datetime.now(CHINA_TZ)))()
        send_timestamp = validate_batch_schedule(scheduled, send_time, current)
        self.args.scheduled, self.args.send_time = scheduled, send_time
        self._submitting = True
        try:
            validation, _ = self._create_attempt(send_timestamp)
        except CliError as exc:
            if exc.outcome_unknown:
                return {
                    "terminalResult": self._terminal_error(
                        exc.code, outcome_unknown=True
                    )
                }
            raise
        except Exception:
            return {
                "terminalResult": self._terminal_error(
                    "submission_outcome_unknown", outcome_unknown=True
                )
            }
        finally:
            self._submitting = False
        self._preview = {
            **self.metadata,
            **validation,
            "fileSize": self._report["fileSize"],
            "fileSha256": self._report["fileSha256"],
            "scheduled": scheduled,
            "sendTime": send_timestamp,
            "revision": self.revision,
        }
        self._validation_task_id = validation["taskId"]
        return dict(self._preview)

    def create(self, revision: int, confirmed: bool) -> Dict[str, Any]:
        self._editable()
        if confirmed is not True or type(revision) is not int or revision != self.revision or self._preview is None:
            raise CliError("请重新校验并确认当前文件和发送时间", "preview_changed")
        self._refresh_resources()
        current = (self.now or (lambda: datetime.datetime.now(CHINA_TZ)))()
        send_timestamp = validate_batch_schedule(
            self.args.scheduled, self.args.send_time, current
        )
        created: Optional[Dict[str, Any]] = None
        self._submitting = True
        confirming = False
        try:
            created = _batch_creation_result(self._preview)
            envelope = self.client.call("GetBatchTaskDetail", {"subAccount": self.args.sub_account, "taskId": created["taskId"]}, expected_credential_scope=self._scope)
            task = _batch_task_data(envelope)
            for key in ("taskId", "subAccount", "signature", "scheduled", "totalCount"):
                if task.get(key) != self._preview.get(key):
                    raise CliError("任务信息已变化，请重新核对", "preview_changed")
            if self.args.content is not None and task.get("sendContent") != self.args.content:
                raise CliError("任务正文已变化，请重新核对", "preview_changed")
            if task.get("templateId") and task["templateId"] != self.args.template_id:
                raise CliError("任务模板已变化，请重新核对", "preview_changed")
            if self.args.scheduled:
                task_time = _task_send_time(task.get("sendTime"))
                if task_time is None or int(task_time.timestamp()) != send_timestamp:
                    raise CliError("任务时间已变化，请重新核对", "preview_changed")
            if task.get("status") not in {2, 3, 4, 5, 6}:
                raise CliError("当前任务不能确认发送", "task_not_ready")
            if task["status"] in {3, 4, 5, 6}:
                launched = {"success": True}
            else:
                confirming = True
                launched = self.client.call(
                    "ConsentBatchTask",
                    {
                        "subAccount": self.args.sub_account,
                        "taskId": created["taskId"],
                    },
                    expected_credential_scope=self._scope,
                )
            confirmed_result = launched.get("success") is True
            reconciled = False
            if not confirmed_result:
                error = launched.get("error") or {}
                unknown = error.get("outcome_unknown") is True
                if unknown:
                    detail = self.client.call(
                        "GetBatchTaskDetail",
                        {
                            "subAccount": self.args.sub_account,
                            "taskId": created["taskId"],
                        },
                        expected_credential_scope=self._scope,
                    )
                    task = detail.get("result") if detail.get("success") else None
                    if (
                        isinstance(task, Mapping)
                        and task.get("status") in {3, 4, 5, 6}
                    ):
                        confirmed_result = True
                        reconciled = True
                if not confirmed_result:
                    self.result = {
                        **created,
                        "fileSha256": self._report["fileSha256"],
                        "status": (
                            "batch_confirmation_outcome_unknown"
                            if unknown
                            else "batch_confirmation_failed"
                        ),
                        "subAccount": self.args.sub_account,
                        "taskName": self.args.task_name,
                        "signature": self.args.signature,
                        "templateId": self.args.template_id,
                        "scheduled": self.args.scheduled,
                        "sendTime": send_timestamp,
                        "code": error.get("code"),
                        "outcomeUnknown": unknown,
                        "fallbackAllowed": False,
                    }
                    return dict(self.result)
            self.result = {
                **created,
                "fileSha256": self._report["fileSha256"],
                "status": "batch_task_confirmed",
                "subAccount": self.args.sub_account,
                "taskName": self.args.task_name,
                "signature": self.args.signature,
                "templateId": self.args.template_id,
                "scheduled": self.args.scheduled,
                "sendTime": send_timestamp,
                "confirmed": True,
                "reconciled": reconciled,
                "requestId": envelope.get("request_id"),
                "fallbackAllowed": False,
            }
            return dict(self.result)
        except CliError as exc:
            if exc.outcome_unknown:
                return self._terminal_error(exc.code, outcome_unknown=True)
            raise
        except Exception as exc:
            if confirming and created is not None:
                self.result = {
                    **created,
                    "fileSha256": self._report["fileSha256"],
                    "status": "batch_confirmation_outcome_unknown",
                    "subAccount": self.args.sub_account,
                    "taskName": self.args.task_name,
                    "signature": self.args.signature,
                    "templateId": self.args.template_id,
                    "scheduled": self.args.scheduled,
                    "sendTime": send_timestamp,
                    "outcomeUnknown": True,
                    "fallbackAllowed": False,
                }
                return dict(self.result)
            raise CliError("无法获取任务最新状态，请稍后重试确认", "task_query_failed") from exc
        finally:
            self._submitting = False
            if self.result is not None:
                self._snapshot = None

    def close(self, reason: str) -> Dict[str, Any]:
        self._snapshot = self._preview = None
        self._closed = True
        if self.result is not None:
            return dict(self.result)
        if self._submitting:
            return {"status": "batch_creation_outcome_unknown", "outcomeUnknown": True, "fallbackAllowed": False}
        if self._validation_task_id is not None:
            return {
                "status": "batch_file_validated",
                "taskId": self._validation_task_id,
                "subAccount": self.args.sub_account,
                "fallbackAllowed": False,
            }
        return {
            "status": "batch_form_unavailable" if reason == "not_displayed" else "batch_form_closed",
            "reason": reason, "fallbackAllowed": reason in {"not_displayed", "cancelled"},
        }


def _bounded_int(name: str, minimum: int, maximum: int):
    def parse_value(raw: str) -> int:
        value = int(raw)
        if not minimum <= value <= maximum:
            raise argparse.ArgumentTypeError(
                "{} must be between {} and {}".format(name, minimum, maximum)
            )
        return value

    return parse_value


def _non_empty_text(name: str):
    def parse_value(raw: str) -> str:
        value = raw.strip()
        if not value:
            raise argparse.ArgumentTypeError("{} must not be empty".format(name))
        return value

    return parse_value


def _page_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--page", type=_bounded_int("page", 1, 100000), default=1)
    parser.add_argument(
        "--page-size",
        type=_bounded_int("page-size", 1, 100),
        default=100,
    )


def _send_options(parser: argparse.ArgumentParser, *, submit: bool) -> None:
    parser.add_argument("--sub-account", required=True, help=MESSAGE_GROUP_ID_HELP)
    parser.add_argument("--signature", required=True)
    parser.add_argument("--template-id", required=True)
    parser.add_argument("--mobile", required=True, action="append")
    parser.add_argument("--template-params", required=True)
    parser.add_argument(
        "--dedupe-policy", choices=("reject", "keep-first"), default="reject"
    )
    if submit:
        parser.add_argument("--preview-digest", required=True)
        parser.add_argument("--authorization-digest", required=True)


def _batch_identity_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sub-account", required=True, help=MESSAGE_GROUP_ID_HELP)
    parser.add_argument("--task-id", required=True)


def _json_object(raw: str) -> Dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliError("params must be a JSON object", "argument_error") from exc
    if not isinstance(value, dict):
        raise CliError("params must be a JSON object", "argument_error")
    return value


def build_parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(description="Volcengine domestic SMS")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("runtime-info", help="show the installed package environment")
    commands.add_parser("auth-doctor", help="check ve and credential readiness")
    commands.add_parser("account-info", help="read account information for sending preparation")
    auth_login = commands.add_parser(
        "auth-login", help="start login with a system-temporary CLI HOME"
    )
    login_mode = auth_login.add_mutually_exclusive_group()
    login_mode.add_argument("--no-browser", action="store_true")
    login_mode.add_argument("--remote", action="store_true")
    auth_login.add_argument("--profile", default=os.environ.get("VOLCENGINE_PROFILE"))
    auth_cleanup = commands.add_parser(
        "auth-cleanup", help="remove a validated temporary authentication HOME"
    )
    auth_cleanup.add_argument("--path", required=True)
    auth_cleanup.add_argument("--empty-only", action="store_true")

    groups = commands.add_parser("list-message-groups")
    groups.add_argument("--name")
    groups.add_argument("--page", type=_bounded_int("page", 1, 100000))
    groups.add_argument("--page-size", type=_bounded_int("page-size", 1, 100), default=100)
    groups.add_argument("--all-status", action="store_true", help="查询全部消息组状态；省略查询启用组")

    group_detail = commands.add_parser("message-group-detail")
    group_detail.add_argument(
        "--sub-account",
        required=True,
        type=_non_empty_text("sub-account"),
        help=MESSAGE_GROUP_ID_HELP,
    )

    qualifications = commands.add_parser("list-qualifications")
    qualifications.add_argument("--id", dest="qualification_id", type=int)
    qualifications.add_argument("--material-name")
    qualifications.add_argument("--status", action="append", type=int, help="审核状态：1 审核中、2 拒绝、3 通过；可重复传入")
    _page_options(qualifications)

    qualification = commands.add_parser(
        "qualification-wizard",
        help="open one private local qualification draft and submission wizard",
    )
    qualification.add_argument(
        "--display",
        choices=("browser", "host"),
        default="browser",
    )

    signatures = commands.add_parser("list-signatures", help="分页查询签名列表及其适用范围和审核状态")
    signatures.add_argument("--signature")
    signatures.add_argument("--exact-match", action="store_true", help="精确匹配签名；默认按前缀匹配")
    signatures.add_argument("--project")
    signatures.add_argument("--sub-account", action="append", help=MESSAGE_GROUP_ID_HELP)
    signatures.add_argument("--channel-type", action="append", choices=("CN_OTP", "CN_NTC", "CN_MKT"))
    signatures.add_argument("--industry", action="append")
    signatures.add_argument("--status", action="append", type=int, help="审核状态；可重复传入")
    _page_options(signatures)

    templates = commands.add_parser("list-templates")
    templates.add_argument("--template-id")
    templates.add_argument("--sub-account", action="append", help=MESSAGE_GROUP_ID_HELP)
    templates.add_argument("--signature", action="append")
    _page_options(templates)
    templates.set_defaults(page=None)
    templates.add_argument("--keyword", action="append", default=[], type=_non_empty_text("keyword"),
                           help="find candidates by name/content/description; repeat for OR matching")

    match_template = commands.add_parser("match-template")
    match_template.add_argument("--content", required=True)
    match_template.add_argument("--signature", required=True)
    match_template.add_argument("--sub-account", required=True, help=MESSAGE_GROUP_ID_HELP)
    match_template.add_argument(
        "--channel-type", choices=("CN_OTP", "CN_NTC", "CN_MKT"),
        help="按指定短信类型比较；省略时保留全部类型",
    )

    query = commands.add_parser("api-read", help="query an SMS Action with its native JSON parameters")
    query.add_argument("--action", required=True, choices=sorted(PUBLIC_QUERY_ACTIONS))
    query.add_argument("--params", required=True, type=_json_object)

    for name in ("signature-preview", "signature-submit", "template-preview", "template-submit"):
        application = commands.add_parser(name)
        application.add_argument("--params", required=True, type=_json_object)
        if name.endswith("-submit"):
            application.add_argument("--preview-digest", required=True)

    _send_options(commands.add_parser("send-preview"), submit=False)
    _send_options(commands.add_parser("send-submit"), submit=True)
    send_status = commands.add_parser("send-status")
    send_status.add_argument("--sub-account", help=MESSAGE_GROUP_ID_HELP + "；省略时查询当前主账户")
    send_status.add_argument("--message-id", required=True)
    send_status.add_argument("--from-time", type=int, help="查询起点，Unix 秒")
    send_status.add_argument("--to-time", type=int, help="查询终点，Unix 秒")
    _page_options(send_status)
    precheck = commands.add_parser("batch-precheck")
    precheck.add_argument("--file", required=True)
    precheck.add_argument("--sub-account", required=True, help=MESSAGE_GROUP_ID_HELP)
    precheck.add_argument("--template-id", required=True)

    demo = commands.add_parser("batch-template-demo")
    demo.add_argument("--sub-account", required=True, help=MESSAGE_GROUP_ID_HELP)
    demo.add_argument("--template-id", required=True)

    wizard = commands.add_parser(
        "batch-wizard", help="打开群发表单，由客户在页面选择名单并确认发送",
        description="在会话中确认模板、正文、消息组和发送时间，再打开表单预填；客户选择 CSV 名单并最终确认发送。",
    )
    wizard.add_argument("--sub-account", required=True, help=MESSAGE_GROUP_ID_HELP)
    wizard.add_argument("--task-name", required=True)
    wizard.add_argument("--signature", required=True)
    wizard.add_argument("--template-id", required=True)
    wizard.add_argument("--content")
    wizard_time = wizard.add_mutually_exclusive_group()
    wizard_time.add_argument("--scheduled", dest="scheduled", action="store_const", const=True, default=None,
                            help="预选会话中确认的定时发送")
    wizard_time.add_argument("--immediate", dest="scheduled", action="store_const", const=False,
                            help="预选会话中确认的立即发送，仍需在表单确认")
    wizard.add_argument("--send-time", help="会话确认的 ISO 8601 发送时间")
    wizard.add_argument("--display", choices=("host", "browser"), default="browser")

    create = commands.add_parser("batch-create")
    create.add_argument("--file", required=True)
    create.add_argument("--sub-account", required=True, help=MESSAGE_GROUP_ID_HELP)
    create.add_argument("--task-name", required=True)
    create.add_argument("--signature", required=True)
    create.add_argument("--template-id", required=True)
    create.add_argument("--content")
    create.add_argument("--scheduled", action="store_true")
    create.add_argument("--send-time")

    detail = commands.add_parser("batch-detail")
    _batch_identity_options(detail)

    tasks = commands.add_parser("batch-list")
    tasks.add_argument("--sub-account", required=True, help=MESSAGE_GROUP_ID_HELP)
    tasks.add_argument("--task-name")
    tasks.add_argument("--signature")
    tasks.add_argument("--template-id")
    _page_options(tasks)

    launch_preview = commands.add_parser("batch-launch-preview")
    _batch_identity_options(launch_preview)

    launch_submit = commands.add_parser("batch-launch-submit")
    _batch_identity_options(launch_submit)
    launch_submit.add_argument("--preview-digest", required=True)
    launch_submit.add_argument("--authorization-text", required=True)

    cancel = commands.add_parser("batch-cancel")
    _batch_identity_options(cancel)

    content_check = commands.add_parser("batch-content-check")
    content_check.add_argument("--sub-account", required=True, help=MESSAGE_GROUP_ID_HELP)
    content_check.add_argument("--signature", required=True)
    content_check.add_argument("--template-id", required=True)
    content_check.add_argument("--content")
    return parser


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    client: Optional[SmsApiClient] = None,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    uploader: Any = _default_uploader,
    now: Any = None,
) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    command = effective_argv[0] if effective_argv else "sms"
    try:
        args = build_parser().parse_args(effective_argv)
        client = client or SmsApiClient(profile=getattr(args, "profile", None))
        result = execute(
            args,
            client,
            uploader=uploader,
            now=now,
        )
    except CliError as exc:
        result = _local_error(command, exc)
    except Exception:
        result = _local_error(
            command,
            CliError("unexpected local error", "internal_error"),
        )
    output = emit_json(
        result, secrets=tuple(getattr(client, "output_secrets", ())),
        preserve_business_values=command == "match-template",
    )
    if result.get("success"):
        stdout.write(output + "\n")
        return 0
    stderr.write(output + "\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
