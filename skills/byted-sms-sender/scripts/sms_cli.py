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
from typing import Any, Dict, List, Mapping, Optional, Sequence, TextIO, Tuple
from urllib import parse, request

from analytics import AnalyticsError, build_report
from api_client import (
    LOGIN_PROCESS_LEASE_SECONDS,
    SmsApiClient,
    cleanup_private_auth_home,
    emit_json,
    select_cli_auth_home,
)
from qualification_display import qualification_display_adapter
from qualification_upload import QualificationUploadError
from qualification_wizard import run_qualification_wizard


PROCESS_TERMINATION_GRACE_SECONDS = 5


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
            process.wait(timeout=LOGIN_PROCESS_LEASE_SECONDS)
        except subprocess.TimeoutExpired as exc:
            _stop_process(process)
            raise CliError(
                "Volcengine login session expired before authorization completed",
                "auth_login_expired",
            ) from exc
        if interrupted:
            raise CliError("Volcengine login was cancelled", "auth_login_cancelled")
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


def _is_approved(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value in (3, 5)
    return str(value).strip().lower() in {
        "3",
        "5",
        "approved",
        "passed",
        "success",
        "completed",
        "no_review",
        "no-review",
        "审核通过",
        "免审",
    }


def _is_template_signature_usable(item: Mapping[str, Any]) -> bool:
    value = item.get("usable")
    if value is None:
        value = item.get("Usable")
    return value is None or value is True


def _channels(item: Mapping[str, Any]) -> set:
    values = item.get("ChannelTypes")
    if values is None:
        values = item.get("channelTypes")
    if values is None:
        single = item.get("ChannelType")
        if single is None:
            single = item.get("channelType")
        values = [single] if single else []
    if isinstance(values, str):
        values = [part for part in values.split(",") if part]
    return {str(value) for value in values}


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


def _validate_signature_resources(
    client: SmsApiClient,
    qualification_id: int,
    purpose: int,
    sub_accounts: Sequence[str],
    channel_types: Sequence[str],
) -> List[Dict[str, str]]:
    qualification = client.call(
        "GetSignatureIdentificationList",
        {"id": qualification_id, "pageIndex": 1, "pageSize": 100},
    )
    _require_query_success(qualification)
    matched = [
        item
        for item in _items(qualification)
        if str(item.get("id")) == str(qualification_id)
    ]
    if not matched:
        raise CliError("qualification is unavailable; apply for it in the SMS console")
    selected = matched[0]
    if not selected.get("usable") or not _is_approved(selected.get("auditStatus")):
        raise CliError("qualification must be approved and usable")
    if selected.get("purpose") is not None and int(selected["purpose"]) != purpose:
        raise CliError("qualification purpose does not match the application")

    groups = client.call("ListSubAccountForAgent", {})
    _require_query_success(groups)
    group_items = _items(groups)
    available = {
        str(item.get("SubAccount"))
        for item in group_items
        if item.get("SubAccount") is not None
    }
    missing = [group for group in sub_accounts if group not in available]
    if missing:
        raise CliError(
            "unknown or unavailable message group: {}".format(", ".join(missing))
        )
    unsupported_by_group = []
    for item in group_items:
        group = str(item.get("SubAccount"))
        if group not in sub_accounts:
            continue
        declared_channels = _channels(item)
        if not declared_channels:
            continue
        unsupported = [
            channel for channel in channel_types if channel not in declared_channels
        ]
        if unsupported:
            unsupported_by_group.append(
                "{}: {}".format(group, ", ".join(unsupported))
            )
    if unsupported_by_group:
        raise CliError(
            "selected message groups do not support channel type: {}".format(
                "; ".join(unsupported_by_group)
            )
        )
    groups_by_id = {
        str(item.get("SubAccount")): item
        for item in group_items
        if item.get("SubAccount") is not None
    }
    summary = []
    for group in sub_accounts:
        raw_name = groups_by_id[group].get("SubAccountName")
        name = str(raw_name) if isinstance(raw_name, (str, int, float, bool)) else ""
        summary.append({"subAccount": group, "subAccountName": name})
    return summary


def _signature_body(args: argparse.Namespace) -> Dict[str, Any]:
    if args.app_icp is not None and args.source != 2:
        raise CliError("app-icp is valid only when source is 2 (App)")
    if args.trademark is not None and args.source != 3:
        raise CliError("trademark is valid only when source is 3 (trademark)")
    body: Dict[str, Any] = {
        "content": _normalize_signature(args.content),
        "purpose": args.purpose,
        "source": args.source,
        "signatureIdentificationID": args.qualification_id,
        "subAccounts": list(dict.fromkeys(args.sub_account)),
        "channelTypes": list(dict.fromkeys(args.channel_type)),
    }
    optional = {
        "desc": args.description,
        "domain": args.domain,
        "scene": args.scene,
        "projectName": args.project_name,
        "appIcp": _parse_typed_json_object(
            args.app_icp,
            "app-icp",
            {"appIcpFilling": str},
        ),
        "trademark": _parse_typed_json_object(
            args.trademark,
            "trademark",
            {
                "trademarkCn": str,
                "trademarkEn": str,
                "trademarkNumber": str,
            },
        ),
    }
    body.update({key: value for key, value in optional.items() if value is not None})
    return body


_VARIABLE_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_SPECIAL_VARIABLES = {"url", "link", "short_url", "shortUrl"}
_MOBILE_RE = re.compile(r"^1[3-9]\d{9}$")
MAX_DIRECT_RECIPIENTS = 200
MAX_BATCH_FILE_BYTES = 50 * 1024 * 1024
MAX_BATCH_ROWS = 1_000_000
MAX_TEMPLATE_MATCH_PAGES = 100
CHINA_TZ = datetime.timezone(datetime.timedelta(hours=8))
CANCEL_LEAD_TIME = datetime.timedelta(minutes=1)


def _parse_typed_json_object(
    raw: Optional[str],
    name: str,
    field_types: Mapping[str, type],
) -> Optional[Mapping[str, Any]]:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliError("{} must be a JSON object".format(name)) from exc
    if not isinstance(value, Mapping):
        raise CliError("{} must be a JSON object".format(name))
    unknown = sorted(set(value).difference(field_types))
    if unknown:
        raise CliError(
            "{} contains unsupported fields: {}".format(name, ", ".join(unknown))
        )
    for key, item in value.items():
        expected = field_types[key]
        if isinstance(item, bool) or not isinstance(item, expected):
            raise CliError(
                "{}.{} must be {}".format(
                    name, key, "an integer" if expected is int else "a string"
                )
            )
    return dict(value)


def _parse_short_url_config(raw: Optional[str]) -> Optional[Mapping[str, Any]]:
    return _parse_typed_json_object(
        raw,
        "short-url-config",
        {
            "isEnabled": str,
            "belong": str,
            "isNeedClickDetails": str,
            "uaCheckStrategy": int,
        },
    )


def _template_body(args: argparse.Namespace) -> Dict[str, Any]:
    declared = list(args.template_param)
    if len(set(declared)) != len(declared):
        raise CliError("template parameters must not contain duplicates")
    extracted = _VARIABLE_RE.findall(args.content)
    if set(declared) != set(extracted) or len(extracted) != len(set(extracted)):
        raise CliError(
            "template parameters must exactly match unique ${name} variables in content"
        )
    if args.channel_type == "CN_OTP" and not any(
        name not in _SPECIAL_VARIABLES for name in declared
    ):
        raise CliError("OTP templates require at least one ordinary variable")
    short_url = _parse_short_url_config(args.short_url_config)
    if short_url is not None and args.channel_type != "CN_MKT":
        raise CliError("short-link options are available only to marketing templates")

    body: Dict[str, Any] = {
        "content": args.content,
        "channelType": args.channel_type,
        "area": "cn",
        "name": args.name,
        "signatures": [_normalize_signature(value) for value in args.signature],
        "subAccounts": list(dict.fromkeys(args.sub_account)),
        "templateParams": [{"name": name} for name in declared],
    }
    if args.project is not None:
        body["project"] = args.project
    if args.description is not None:
        body["desc"] = args.description
    if short_url is not None:
        body["shortUrlConfig"] = short_url
    return body


def _validate_template_resources(client: SmsApiClient, body: Mapping[str, Any]) -> None:
    signatures = client.call(
        "ListSignatureForAgent",
        {
            "Signature": body["signatures"][0] if len(body["signatures"]) == 1 else "",
            "SubAccounts": body["subAccounts"],
            "Page": 1,
            "PageSize": 100,
        },
    )
    _require_query_success(signatures)
    requested_groups = set(body["subAccounts"])
    available: Dict[str, Dict[str, set]] = {}
    for item in _items(signatures):
        if not _is_approved(item.get("Status")) or not _is_template_signature_usable(
            item
        ):
            continue
        name = _normalize_signature(str(item.get("Signature", "")))
        entry = available.setdefault(name, {"groups": set(), "channels": set()})
        entry["groups"].update(str(value) for value in item.get("SubAccounts", []))
        entry["channels"].update(_channels(item))
    for name in body["signatures"]:
        if name not in available or not requested_groups.issubset(
            available[name]["groups"]
        ):
            raise CliError(
                "signature is not approved for every selected message group: {}".format(
                    name
                )
            )
        channels = available[name]["channels"]
        if channels and body["channelType"] not in channels:
            raise CliError(
                "signature is not approved for channel type: {}".format(
                    body["channelType"]
                )
            )


def _signature_preview(
    body: Mapping[str, Any], message_groups: Sequence[Mapping[str, str]]
) -> Dict[str, Any]:
    return {
        "preview": dict(body),
        "messageGroups": [dict(group) for group in message_groups],
        "messageGroupCount": len(message_groups),
        "digest": canonical_digest(body),
    }


def _template_preview(body: Mapping[str, Any]) -> Dict[str, Any]:
    preview: Dict[str, Any] = {
        "name": body["name"],
        "channelType": body["channelType"],
        "area": body["area"],
        "signatures": body["signatures"],
        "subAccounts": body["subAccounts"],
        "templateParams": [item["name"] for item in body["templateParams"]],
        "content_length": len(body["content"]),
        "content_sha256": hashlib.sha256(body["content"].encode("utf-8")).hexdigest(),
    }
    for name in ("project", "desc", "shortUrlConfig"):
        if name in body:
            preview[name] = body[name]
    return {"preview": preview, "digest": canonical_digest(body)}


def _is_outcome_unknown(envelope: Mapping[str, Any]) -> bool:
    error_value = envelope.get("error")
    return bool(
        not envelope.get("success")
        and isinstance(error_value, Mapping)
        and error_value.get("outcome_unknown")
    )


def _application_status_is_not_rejected(value: Any) -> bool:
    if isinstance(value, int):
        return value in {0, 1, 3, 5, 6}
    return str(value).strip().lower() in {
        "0",
        "1",
        "3",
        "5",
        "6",
        "reviewing",
        "pending",
        "approved",
        "passed",
        "no_review",
        "no-review",
        "审核中",
        "审核通过",
        "免审",
    }


def _matches_optional_fields(
    body: Mapping[str, Any],
    item: Mapping[str, Any],
    aliases: Mapping[str, Sequence[str]],
) -> bool:
    for body_name, response_names in aliases.items():
        if body_name not in body:
            continue
        actual = _template_value(item, *response_names)
        if actual is None or actual != body[body_name]:
            return False
    return True


def _safe_template_item(item: Mapping[str, Any]) -> Dict[str, Any]:
    safe = dict(item)
    content = safe.pop("Content", None)
    if content is None:
        content = safe.pop("content", None)
    if content is not None:
        encoded = str(content).encode("utf-8")
        safe["ContentLength"] = len(str(content))
        safe["ContentSha256"] = hashlib.sha256(encoded).hexdigest()
    return safe


def _safe_template_envelope(envelope: Mapping[str, Any]) -> Dict[str, Any]:
    output = dict(envelope)
    result = output.get("result")
    if not isinstance(result, Mapping):
        return output
    safe_result = dict(result)
    for key in ("List", "list", "Items", "items"):
        values = safe_result.get(key)
        if isinstance(values, list):
            safe_result[key] = [
                _safe_template_item(item) if isinstance(item, Mapping) else item
                for item in values
            ]
    safe_result = _safe_template_item(safe_result)
    output["result"] = safe_result
    return output


def _reconciled_success(
    action: str,
    query: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "success": True,
        "action": action,
        "request_id": query.get("request_id"),
        "result": {"reconciled": True, **dict(summary)},
        "error": None,
    }


def _reconcile_signature_application(
    client: SmsApiClient,
    body: Mapping[str, Any],
    unknown: Mapping[str, Any],
) -> Dict[str, Any]:
    query = client.call(
        "ListSignatureForAgent",
        {
            "Signature": body["content"],
            "SubAccounts": body["subAccounts"],
            "Page": 1,
            "PageSize": 100,
        },
    )
    if not query.get("success"):
        return dict(unknown)
    requested_groups = {str(value) for value in body["subAccounts"]}
    requested_channels = {str(value) for value in body["channelTypes"]}
    matches = []
    for item in _items(query):
        qualification_id = item.get("IdentificationId") or item.get("IdentificationID")
        if (
            _normalize_signature(str(item.get("Signature", ""))) == body["content"]
            and _application_status_is_not_rejected(item.get("Status"))
            and requested_groups.issubset(
                {str(value) for value in item.get("SubAccounts", [])}
            )
            and requested_channels.issubset(_channels(item))
            and str(qualification_id or "") == str(body["signatureIdentificationID"])
            and str(item.get("Purpose") or "") == str(body["purpose"])
            and _matches_optional_fields(
                body,
                item,
                {
                    "source": ("Source", "source"),
                    "desc": ("Description", "description", "desc"),
                    "domain": ("Domain", "domain"),
                    "scene": ("Scene", "scene"),
                    "projectName": ("ProjectName", "projectName"),
                    "appIcp": ("AppIcp", "appIcp"),
                    "trademark": ("Trademark", "trademark"),
                },
            )
        ):
            matches.append(item)
    if len(matches) != 1:
        return dict(unknown)
    item = matches[0]
    return _reconciled_success(
        "ApplySmsSignatureV2",
        query,
        {
            "Signature": body["content"],
            "Status": item.get("Status"),
            "SubAccounts": sorted(requested_groups),
            "ChannelTypes": sorted(requested_channels),
        },
    )


def _reconcile_template_application(
    client: SmsApiClient,
    body: Mapping[str, Any],
    unknown: Mapping[str, Any],
) -> Dict[str, Any]:
    query = client.call(
        "ListSmsTemplateForAgent",
        {
            "SubAccounts": body["subAccounts"],
            "Signatures": body["signatures"],
            "Page": 1,
            "PageSize": 100,
        },
    )
    if not query.get("success"):
        return dict(unknown)
    requested_groups = {str(value) for value in body["subAccounts"]}
    requested_signatures = {
        _normalize_signature(str(value)) for value in body["signatures"]
    }
    expected_params = sorted(
        str(value["name"]) for value in body.get("templateParams", [])
    )
    matches = []
    for item in _items(query):
        name = item.get("TemplateName") or item.get("Name") or item.get("name")
        content = item.get("Content") or item.get("content")
        channel = item.get("ChannelType") or item.get("channelType")
        try:
            returned_signatures = _normalized_template_signatures(item)
        except CliError:
            return dict(unknown)
        if (
            str(name or "") == str(body["name"])
            and _application_status_is_not_rejected(item.get("Status"))
            and str(content or "") == str(body["content"])
            and str(channel or "") == str(body["channelType"])
            and requested_groups.issubset(
                {str(value) for value in item.get("SubAccounts", [])}
            )
            and returned_signatures is not None
            and requested_signatures.issubset(returned_signatures)
            and sorted(_template_param_names(item)) == expected_params
            and _matches_optional_fields(
                body,
                item,
                {
                    "project": ("Project", "project"),
                    "desc": ("Description", "description", "desc"),
                    "shortUrlConfig": ("ShortUrlConfig", "shortUrlConfig"),
                },
            )
        ):
            matches.append(item)
    if len(matches) != 1:
        return dict(unknown)
    item = matches[0]
    return _reconciled_success(
        "ApplySmsTemplateV2",
        query,
        {
            "TemplateId": item.get("TemplateId") or item.get("templateId"),
            "TemplateName": body["name"],
            "Status": item.get("Status"),
            "ContentSha256": hashlib.sha256(
                str(body["content"]).encode("utf-8")
            ).hexdigest(),
        },
    )


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


def _complete_template_for_send(
    client: SmsApiClient,
    template: Mapping[str, Any],
    template_id: str,
    signature: str,
    sub_account: str,
) -> Dict[str, Any]:
    completed = dict(template)
    required = (
        ("Content", "content"),
        ("SubAccounts", "subAccounts"),
        ("ChannelType", "channelType"),
    )
    has_template_params = any(
        name in completed and isinstance(completed[name], list)
        for name in ("TemplateParams", "templateParams")
    )
    if (
        has_template_params
        and all(_template_value(completed, *names) is not None for names in required)
        and str(
            _template_value(
                completed, "TemplateName", "templateName", "Name", "name"
            )
            or ""
        ).strip()
    ):
        return completed

    second_template_id = str(
        _template_value(completed, "SecondTemplateId", "secondTemplateId") or ""
    )
    detail_params = {
        "templateId": template_id,
        "signatures": signature,
    }
    if second_template_id:
        detail_params["secondTemplateId"] = second_template_id
    detail = client.call("ListSecondTemplate", detail_params)
    _require_query_success(detail)
    candidate = next(
        (
            item
            for item in _items(detail)
            if str(
                _template_value(
                    item,
                    "TemplateId",
                    "templateId",
                    "SecondTemplateId",
                )
            )
            in {template_id, second_template_id}
            and _template_supports_sub_account(item, sub_account)
            and _template_supports_signature(item, signature)
        ),
        None,
    )
    if candidate is None:
        raise CliError("template detail is unavailable")
    for target, source_names in (
        ("Content", ("Content", "content")),
        ("TemplateParams", ("TemplateParams", "templateParams")),
        (
            "Signatures",
            ("Signatures", "signatures", "Signature", "signature"),
        ),
        ("SubAccounts", ("SubAccounts", "subAccounts")),
        ("ChannelType", ("ChannelType", "channelType")),
        ("TemplateName", ("TemplateName", "templateName", "Name", "name")),
    ):
        if completed.get(target) in (None, "", []):
            if target == "Signatures" and any(
                name in completed for name in source_names
            ):
                continue
            if target == "TemplateParams":
                resolved = next(
                    (
                        candidate[name]
                        for name in source_names
                        if name in candidate and isinstance(candidate[name], list)
                    ),
                    None,
                )
                if resolved is not None or any(
                    name in completed for name in source_names
                ):
                    completed[target] = resolved
            else:
                if any(name in candidate for name in source_names):
                    completed[target] = _template_value(candidate, *source_names)
    has_template_params = any(
        name in completed and isinstance(completed[name], list)
        for name in ("TemplateParams", "templateParams")
    )
    if not has_template_params or any(
        _template_value(completed, *names) is None for names in required
    ):
        raise CliError("template detail is incomplete")
    return completed


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


def _signature_supports_sub_account(
    item: Mapping[str, Any], sub_account: str
) -> bool:
    values = _template_relationship_values(item, "SubAccounts", "subAccounts")
    return not values or bool(values.intersection({sub_account, "*", "All"}))


def _template_content_body(content: str, signature: str) -> str:
    wrapper = "【{}】".format(signature)
    return content[len(wrapper) :] if content.startswith(wrapper) else content


def _match_template(client: SmsApiClient, args: argparse.Namespace) -> Dict[str, Any]:
    signature = _normalize_signature(args.signature)
    approved_ids = set()
    seen_page_fingerprints = set()
    page = 1
    while True:
        if page > MAX_TEMPLATE_MATCH_PAGES:
            raise CliError(
                "template pagination exceeded the safe page limit",
                "resource_query_failed",
            )
        templates = client.call(
            "ListSmsTemplateForAgent",
            {
                "SubAccounts": [args.sub_account],
                "Signatures": [signature],
                "Page": page,
                "PageSize": 100,
            },
        )
        _require_query_success(templates)
        template_items = _items(templates)
        fingerprint = canonical_digest({"items": template_items})
        if fingerprint in seen_page_fingerprints:
            raise CliError(
                "template pagination repeated a page",
                "resource_query_failed",
            )
        seen_page_fingerprints.add(fingerprint)
        approved_ids.update(
            str(_template_value(item, "TemplateId", "templateId"))
            for item in template_items
            if _template_value(item, "TemplateId", "templateId") is not None
            and _is_approved(_template_value(item, "Status", "status"))
            and _template_value(item, "ChannelType", "channelType")
            == args.channel_type
        )
        result = templates.get("result")
        total = (
            result.get("Total", result.get("total"))
            if isinstance(result, Mapping)
            else None
        )
        if isinstance(total, str) and total.strip().isdigit():
            total = int(total.strip())
        if (
            len(template_items) < 100
            or (
                isinstance(total, int)
                and not isinstance(total, bool)
                and page * 100 >= total
            )
        ):
            break
        page += 1
    candidates: Dict[str, Dict[str, Any]] = {}
    if approved_ids:
        details = client.call("ListSecondTemplate", {"signatures": signature})
        _require_query_success(details)
        for item in _items(details):
            template_id = _template_value(item, "TemplateId", "templateId")
            content = _template_value(item, "Content", "content")
            if (
                template_id is None
                or str(template_id) not in approved_ids
                or _template_value(item, "ChannelType", "channelType")
                != args.channel_type
                or not isinstance(content, str)
                or not any(name in item for name in ("TemplateParams", "templateParams"))
                or not _template_supports_sub_account(item, args.sub_account)
                or not _template_supports_signature(item, signature)
            ):
                continue
            body = _template_content_body(content, signature)
            if body != args.content:
                continue
            variable_names = _template_param_names(item)
            if len(variable_names) != len(set(variable_names)):
                continue
            normalized_id = str(template_id)
            candidates.setdefault(
                normalized_id,
                {
                    "templateId": normalized_id,
                    "signature": signature,
                    "subAccount": args.sub_account,
                    "variableNames": sorted(variable_names),
                    "contentLength": len(body),
                    "contentSha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                },
            )
    ordered = [candidates[key] for key in sorted(candidates)]
    classification = "none" if not ordered else "single" if len(ordered) == 1 else "ambiguous"
    return _local_success(
        args.command,
        {"classification": classification, "candidates": ordered},
    )


def _render_content(content: str, variables: Mapping[str, Any]) -> str:
    return _VARIABLE_RE.sub(lambda match: str(variables[match.group(1)]), content)


def _segments(content: str, signature: str) -> int:
    length = len("【{}】{}".format(signature, content))
    return 1 if length <= 70 else int(math.ceil(length / 67.0))


def _direct_send_template_detail(
    client: SmsApiClient,
    template_id: str,
    signature: str,
    sub_account: str,
) -> Mapping[str, Any]:
    detail = client.call(
        "ListSecondTemplate",
        {"templateId": template_id, "signatures": signature},
    )
    _require_query_success(detail)
    selected = next(
        (
            item
            for item in _items(detail)
            if str(_template_value(item, "TemplateId", "templateId")) == template_id
            and _template_supports_sub_account(item, sub_account)
            and _template_supports_signature(item, signature)
        ),
        None,
    )
    if selected is None:
        raise CliError("template detail does not match message group and signature")
    if not any(name in selected for name in ("TemplateParams", "templateParams")):
        raise CliError("template detail is incomplete")
    content = _template_value(selected, "Content", "content")
    channel_type = _template_value(selected, "ChannelType", "channelType")
    if not isinstance(content, str) or channel_type not in {
        "CN_OTP",
        "CN_NTC",
        "CN_MKT",
    }:
        raise CliError("template detail is incomplete")
    normalized = dict(selected)
    normalized["Content"] = _template_content_body(content, signature)
    return normalized


def _send_summary(
    client: SmsApiClient,
    args: argparse.Namespace,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str], Dict[str, Any]]:
    original, recipients, variables = _send_local_inputs(args)
    signature = _normalize_signature(args.signature)

    group = client.call("GetSubAccountDetail", {"subAccount": args.sub_account})
    _require_query_success(group)
    group_result = group.get("result")
    if not isinstance(group_result, Mapping) or str(group_result.get("status")) != "1":
        raise CliError("message group is unavailable")

    signatures = client.call(
        "ListSignatureForAgent",
        {
            "Signature": signature,
            "SubAccounts": [args.sub_account],
            "Page": 1,
            "PageSize": 100,
        },
    )
    _require_query_success(signatures)
    selected_signature = next(
        (
            item
            for item in _items(signatures)
            if _is_approved(item.get("Status"))
            and _is_template_signature_usable(item)
            and _normalize_signature(str(item.get("Signature", ""))) == signature
            and _signature_supports_sub_account(item, args.sub_account)
        ),
        None,
    )
    if selected_signature is None:
        raise CliError("signature is not approved for the selected message group")

    templates = client.call(
        "ListSmsTemplateForAgent",
        {
            "TemplateId": args.template_id,
            "SubAccounts": [args.sub_account],
            "Signatures": [signature],
            "Page": 1,
            "PageSize": 100,
        },
    )
    _require_query_success(templates)
    selected_template = next(
        (
            item
            for item in _items(templates)
            if str(_template_value(item, "TemplateId", "templateId"))
            == args.template_id
            and _is_approved(_template_value(item, "Status", "status"))
        ),
        None,
    )
    if selected_template is None:
        raise CliError("template is not approved or available")
    selected_template = _direct_send_template_detail(
        client,
        args.template_id,
        signature,
        args.sub_account,
    )

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
        or not hostname.endswith(".volces.com")
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


def _batch_resources(
    client: SmsApiClient,
    sub_account: str,
    signature_value: str,
    template_id: str,
) -> Tuple[Mapping[str, Any], List[str]]:
    signature = _normalize_signature(signature_value)
    groups = client.call("ListSubAccountForAgent", {})
    _require_query_success(groups)
    group = next(
        (item for item in _items(groups) if str(item.get("SubAccount")) == sub_account),
        None,
    )
    if group is None:
        raise CliError("message group is unavailable")
    signatures = client.call(
        "ListSignatureForAgent",
        {
            "Signature": signature,
            "SubAccounts": [sub_account],
            "Page": 1,
            "PageSize": 100,
        },
    )
    _require_query_success(signatures)
    signature_item = next(
        (
            item
            for item in _items(signatures)
            if _is_approved(item.get("Status"))
            and _is_template_signature_usable(item)
            and _normalize_signature(str(item.get("Signature", ""))) == signature
            and sub_account in {str(value) for value in item.get("SubAccounts", [])}
        ),
        None,
    )
    if signature_item is None:
        raise CliError("signature is unavailable for the message group")
    qualification_id = signature_item.get("IdentificationId") or signature_item.get(
        "IdentificationID"
    )
    if qualification_id is not None:
        qualifications = client.call(
            "GetSignatureIdentificationList",
            {"id": qualification_id, "pageIndex": 1, "pageSize": 100},
        )
        _require_query_success(qualifications)
        qualification = next(
            (
                item
                for item in _items(qualifications)
                if str(item.get("id")) == str(qualification_id)
            ),
            None,
        )
        if (
            qualification is None
            or not qualification.get("usable")
            or not _is_approved(qualification.get("auditStatus"))
        ):
            raise CliError("signature qualification is no longer approved and usable")
    templates = client.call(
        "ListSmsTemplateForAgent",
        {
            "TemplateId": template_id,
            "SubAccounts": [sub_account],
            "Signatures": [signature],
            "Page": 1,
            "PageSize": 100,
        },
    )
    _require_query_success(templates)
    template = next(
        (
            item
            for item in _items(templates)
            if str(item.get("TemplateId")) == template_id
            and _is_approved(item.get("Status"))
        ),
        None,
    )
    if template is None:
        raise CliError("template is unavailable")
    template = _complete_template_for_send(
        client, template, template_id, signature, sub_account
    )
    channel = str(template.get("ChannelType") or "")
    if channel == "CN_OTP":
        raise CliError("OTP templates cannot be used for batch tasks")
    if channel not in {"CN_NTC", "CN_MKT"}:
        raise CliError("batch task requires a notification or marketing template")
    signature_channels = _channels(signature_item)
    if signature_channels and channel not in {
        str(value) for value in signature_channels
    }:
        raise CliError("signature does not support the batch template channel type")
    group_channels = _channels(group)
    if group_channels and channel not in {str(value) for value in group_channels}:
        raise CliError("message group does not support the batch template channel type")
    if not _template_supports_sub_account(template, sub_account):
        raise CliError("template is not bound to the message group")
    if not _template_supports_signature(template, signature):
        raise CliError("template is not bound to the signature")
    template_name = str(template.get("TemplateName") or "").strip()
    if not template_name:
        template_name = template_id
        template = dict(template)
        template["TemplateName"] = template_name
    return template, _template_param_names(template)


def _batch_task_data(envelope: Mapping[str, Any]) -> Mapping[str, Any]:
    _require_query_success(envelope)
    result = envelope.get("result")
    if not isinstance(result, Mapping):
        raise CliError("batch task detail is missing")
    return result


def _first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _batch_summary(task: Mapping[str, Any]) -> Dict[str, Any]:
    extra = task.get("extra") or task.get("Extra") or {}
    if not isinstance(extra, Mapping):
        extra = {}
    return {
        "taskId": str(task.get("taskId") or task.get("TaskId") or ""),
        "taskName": task.get("taskName")
        or task.get("TaskName")
        or task.get("name")
        or task.get("Name"),
        "subAccount": str(task.get("subAccount") or task.get("SubAccount") or ""),
        "signature": task.get("signature") or task.get("Signature"),
        "templateId": task.get("templateId") or task.get("TemplateId"),
        "templateName": task.get("templateName") or task.get("TemplateName"),
        "channelType": task.get("channelType") or task.get("ChannelType"),
        "fileUrl": task.get("fileUrl") or task.get("FileUrl"),
        "fileSha256": extra.get("fileSha256"),
        "totalCount": _first_not_none(extra.get("totalCount"), task.get("totalCount")),
        "validCount": _first_not_none(extra.get("validCount"), task.get("validCount")),
        "invalidCount": _first_not_none(
            extra.get("invalidCount"), task.get("invalidCount")
        ),
        "dupCount": _first_not_none(extra.get("dupCount"), task.get("dupCount")),
        "contentSha256": extra.get("contentSha256"),
        "scheduled": task.get("scheduled"),
        "sendTime": task.get("sendTime") or task.get("SendTime"),
    }


def _launch_summary(
    client: SmsApiClient,
    args: argparse.Namespace,
    task: Mapping[str, Any],
) -> Dict[str, Any]:
    summary = _batch_summary(task)
    if summary["taskId"] != args.task_id or summary["subAccount"] != args.sub_account:
        raise CliError("batch task identity does not match")
    template_id = str(summary["templateId"] or "")
    signature = str(summary["signature"] or "")
    if not template_id or not signature:
        raise CliError("batch task resource identity is incomplete")
    template, _ = _batch_resources(
        client,
        args.sub_account,
        signature,
        template_id,
    )
    current_content_sha = hashlib.sha256(
        str(template.get("Content") or "").encode("utf-8")
    ).hexdigest()
    if summary["contentSha256"] not in (None, current_content_sha):
        raise CliError("batch task template content changed", "digest_mismatch")
    summary["contentSha256"] = current_content_sha
    for summary_name, template_name in (
        ("templateName", "TemplateName"),
        ("channelType", "ChannelType"),
    ):
        current = str(template.get(template_name) or "")
        if summary[summary_name] not in (None, "", current):
            raise CliError("batch task template metadata changed", "digest_mismatch")
        summary[summary_name] = current

    handoff = {
        "fileSha256": args.file_sha256,
        "totalCount": args.total_count,
        "validCount": args.valid_count,
        "invalidCount": args.invalid_count,
        "dupCount": args.dup_count,
    }
    for name, supplied in handoff.items():
        if supplied is not None:
            if summary[name] is not None and str(summary[name]) != str(supplied):
                raise CliError(
                    "batch task handoff metadata changed: {}".format(name),
                    "digest_mismatch",
                )
            summary[name] = supplied
    missing = [
        name
        for name in (
            "fileSha256",
            "totalCount",
            "validCount",
            "invalidCount",
            "dupCount",
        )
        if summary[name] is None
    ]
    if missing:
        raise CliError(
            "provide creation handoff metadata for launch: {}".format(
                ", ".join(missing)
            )
        )
    return summary


def _query_params(args: argparse.Namespace) -> Tuple[str, Dict[str, Any]]:
    if args.command == "list-message-groups":
        return (
            "ListSubAccountForAgent",
            {"SubAccountName": args.name} if args.name else {},
        )
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
        if args.sub_account:
            params["SubAccounts"] = args.sub_account
        return "ListSignatureForAgent", params
    if args.command == "list-templates":
        params = {"Page": args.page, "PageSize": args.page_size}
        if args.template_id:
            params["TemplateId"] = args.template_id
        if args.sub_account:
            params["SubAccounts"] = args.sub_account
        if args.signature:
            params["Signatures"] = [
                _normalize_signature(value) for value in args.signature
            ]
        return "ListSmsTemplateForAgent", params
    raise CliError("unknown query command")


def execute(
    args: argparse.Namespace,
    client: SmsApiClient,
    *,
    uploader: Any = _default_uploader,
    now: Any = None,
) -> Dict[str, Any]:
    if args.command == "auth-login":
        try:
            login_env = dict(os.environ)
            login_env["HOME"] = select_cli_auth_home(login_env)
            if os.name == "nt":
                login_env["USERPROFILE"] = login_env["HOME"]
            login_argv = ["ve", "login"]
            if args.remote:
                login_argv.append("--remote")
            login_argv.extend(["--region", "cn-beijing"])
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
            )
        except QualificationUploadError as exc:
            raise CliError(
                str(exc),
                exc.code,
                request_id=exc.request_id,
                log_id=exc.log_id,
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

    if args.command == "analytics":
        try:
            report = build_report(
                client,
                start=args.start,
                end=args.end,
                sub_account=args.sub_account,
                channel_type=args.channel_type,
                signature=args.signature,
                template_id=args.template_id,
                mobile=(
                    _normalize_mobile(args.mobile)
                    if args.mobile is not None
                    else None
                ),
                bucket=args.bucket,
                include_logs=args.include_logs,
                page_size=args.page_size,
                max_pages=args.max_pages,
                dimension=args.dimension,
            )
        except AnalyticsError as exc:
            raise CliError(str(exc), exc.code) from exc
        return _local_success(args.command, report)

    if args.command == "match-template":
        return _match_template(client, args)

    if args.command.startswith("list-") or args.command == "message-group-detail":
        action, params = _query_params(args)
        result = client.call(action, params)
        return (
            _safe_template_envelope(result)
            if action == "ListSmsTemplateForAgent"
            else result
        )

    if args.command in {"signature-preview", "signature-submit"}:
        body = _signature_body(args)
        message_groups = _validate_signature_resources(
            client,
            body["signatureIdentificationID"],
            body["purpose"],
            body["subAccounts"],
            body["channelTypes"],
        )
        digest = canonical_digest(body)
        if args.command == "signature-preview":
            return _local_success(
                args.command, _signature_preview(body, message_groups)
            )
        if not hmac.compare_digest(args.preview_digest, digest):
            raise CliError(
                "input changed after preview; generate a new preview",
                "digest_mismatch",
            )
        submitted = client.call("ApplySmsSignatureV2", body)
        if _is_outcome_unknown(submitted):
            return _reconcile_signature_application(client, body, submitted)
        return submitted

    if args.command in {"template-preview", "template-submit"}:
        body = _template_body(args)
        _validate_template_resources(client, body)
        digest = canonical_digest(body)
        if args.command == "template-preview":
            return _local_success(args.command, _template_preview(body))
        if not hmac.compare_digest(args.preview_digest, digest):
            raise CliError(
                "input changed after preview; generate a new preview",
                "digest_mismatch",
            )
        submitted = client.call("ApplySmsTemplateV2", body)
        if _is_outcome_unknown(submitted):
            return _reconcile_template_application(client, body, submitted)
        return _safe_template_envelope(submitted)
    if args.command == "send-status":
        return client.call(
            "ListSmsSendLogForAgent",
            {
                "SubAccount": args.sub_account,
                "MessageId": args.message_id,
                "Page": args.page,
                "PageSize": args.page_size,
            },
        )
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
    if args.command == "batch-template-demo":
        params = {"subAccount": args.sub_account, "templateId": args.template_id}
        if args.force_update:
            params["forceUpdate"] = True
        return client.call("TemplateUploadDemo", params)
    if args.command == "batch-detail":
        return client.call(
            "GetBatchTaskDetail",
            {"subAccount": args.sub_account, "taskId": args.task_id},
        )
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
        report = precheck_batch_csv(pathlib.Path(args.file), args.template_param or [])
        return _local_success(args.command, report)
    if args.command == "batch-create":
        current = (now or (lambda: datetime.datetime.now(CHINA_TZ)))()
        send_time = validate_batch_schedule(args.scheduled, args.send_time, current)
        template, variables = _batch_resources(
            client, args.sub_account, args.signature, args.template_id
        )
        source_path = pathlib.Path(args.file)
        if source_path.suffix.lower() != ".csv":
            raise CliError("batch v1 supports CSV files only")
        snapshot = _read_batch_snapshot(source_path)
        report = precheck_batch_csv(snapshot, variables)
        upload = client.call(
            "GetUploadTosURL",
            {"suffix": "csv"},
            preserve_presigned_url=True,
        )
        upload_data = _batch_task_data(upload)
        upload_url = upload_data.get("url") or upload_data.get("Url")
        file_key = upload_data.get("file") or upload_data.get("File")
        if not upload_url or not file_key:
            raise CliError("upload authorization is incomplete")
        try:
            uploader(str(upload_url), snapshot)
        except CliError:
            raise
        except Exception as exc:
            raise CliError("batch file upload failed") from exc
        try:
            current_file_sha = hashlib.sha256(snapshot).hexdigest()
        except (TypeError, ValueError) as exc:
            raise CliError("batch CSV snapshot is invalid") from exc
        if not hmac.compare_digest(current_file_sha, report["fileSha256"]):
            raise CliError("batch CSV snapshot changed during upload")
        content = str(template.get("Content") or "")
        handoff_metadata = {
            "fileSha256": report["fileSha256"],
            "totalCount": report["totalCount"],
            "validCount": report["validCount"],
            "invalidCount": report["invalidCount"],
            "dupCount": report["dupCount"],
            "contentSha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }
        body = {
            "subAccount": args.sub_account,
            "name": args.task_name,
            "signature": _normalize_signature(args.signature),
            "templateId": args.template_id,
            "templateName": str(template["TemplateName"]),
            "channelType": str(template["ChannelType"]),
            "scheduled": args.scheduled,
            "sendTime": send_time,
            "fileUrl": str(file_key),
            "extra": {},
        }
        created = client.call("SetBatchTask", body)
        if not created.get("success"):
            return created
        service_result = created.get("result")
        if not isinstance(service_result, Mapping):
            raise CliError("batch create response is incomplete")
        task_id = service_result.get("taskId") or service_result.get("TaskId")
        if not task_id:
            raise CliError("batch create response has no taskId")
        authoritative = client.call(
            "GetBatchTaskDetail",
            {"subAccount": args.sub_account, "taskId": str(task_id)},
        )
        authoritative_result = (
            authoritative.get("result") if authoritative.get("success") else None
        )
        status = None
        if isinstance(authoritative_result, Mapping):
            detail_id = authoritative_result.get("taskId") or authoritative_result.get(
                "TaskId"
            )
            detail_group = authoritative_result.get(
                "subAccount"
            ) or authoritative_result.get("SubAccount")
            if (
                str(detail_id or "") == str(task_id)
                and str(detail_group or "") == args.sub_account
            ):
                status = authoritative_result.get("status")
                if status is None:
                    status = authoritative_result.get("Status")
        handoff = dict(service_result)
        handoff.update(
            {
                "taskId": str(task_id),
                "subAccount": args.sub_account,
                "status": status,
                "statusAuthoritative": status is not None,
                "fileSha256": report["fileSha256"],
                "totalCount": service_result.get("totalCount", report["totalCount"]),
                "validCount": service_result.get("validCount", report["validCount"]),
                "invalidCount": service_result.get(
                    "invalidCount", report["invalidCount"]
                ),
                "dupCount": service_result.get("dupCount", report["dupCount"]),
                "digest": canonical_digest(
                    {
                        "taskId": str(task_id),
                        "subAccount": args.sub_account,
                        "body": body,
                        "handoff": handoff_metadata,
                    }
                ),
            }
        )
        return {
            "success": True,
            "action": "SetBatchTask",
            "request_id": created.get("request_id"),
            "result": handoff,
            "error": None,
        }
    if args.command in {"batch-launch-preview", "batch-launch-submit"}:
        if args.command == "batch-launch-submit":
            expected_text = "确认启动任务 {}".format(args.task_id)
            if args.authorization_text != expected_text:
                raise CliError(
                    "authorization must exactly be: {}".format(expected_text),
                    "authorization_mismatch",
                )
        first = client.call(
            "GetBatchTaskDetail",
            {"subAccount": args.sub_account, "taskId": args.task_id},
        )
        task = _batch_task_data(first)
        summary = _batch_summary(task)
        if (
            summary["taskId"] != args.task_id
            or summary["subAccount"] != args.sub_account
        ):
            raise CliError("batch task identity does not match")
        status = int(task.get("status", task.get("Status", -1)))
        if 3 <= status <= 6:
            return _local_success(
                args.command,
                {"alreadyStarted": True, "status": status, "taskId": args.task_id},
            )
        if status != 2:
            raise CliError("batch task is not in Valid(2) state")
        summary = _launch_summary(client, args, task)
        digest = canonical_digest(summary)
        preview = {
            "taskId": args.task_id,
            "subAccount": args.sub_account,
            "taskName": summary["taskName"],
            "signature": summary["signature"],
            "templateId": summary["templateId"],
            "channelType": summary["channelType"],
            "fileKeySha256": hashlib.sha256(
                str(summary["fileUrl"] or "").encode("utf-8")
            ).hexdigest(),
            "fileSha256": summary["fileSha256"],
            "contentSha256": summary["contentSha256"],
            "totalCount": summary["totalCount"],
            "validCount": summary["validCount"],
            "invalidCount": summary["invalidCount"],
            "dupCount": summary["dupCount"],
            "sendTime": summary["sendTime"],
        }
        if args.command == "batch-launch-preview":
            return _local_success(args.command, {"preview": preview, "digest": digest})
        if not hmac.compare_digest(args.preview_digest, digest):
            raise CliError("batch task changed after preview", "digest_mismatch")
        second = client.call(
            "GetBatchTaskDetail",
            {"subAccount": args.sub_account, "taskId": args.task_id},
        )
        latest = _batch_task_data(second)
        latest_status = int(latest.get("status", latest.get("Status", -1)))
        if 3 <= latest_status <= 6:
            return _local_success(
                args.command,
                {
                    "alreadyStarted": True,
                    "status": latest_status,
                    "taskId": args.task_id,
                },
            )
        latest_summary = _launch_summary(client, args, latest)
        if latest_status != 2 or canonical_digest(latest_summary) != digest:
            raise CliError("batch task changed before launch", "digest_mismatch")
        launched = client.call(
            "ConsentBatchTask",
            {"subAccount": args.sub_account, "taskId": args.task_id},
        )
        if (
            not launched.get("success")
            and isinstance(launched.get("error"), Mapping)
            and launched["error"].get("outcome_unknown")
        ):
            reconciled = client.call(
                "GetBatchTaskDetail",
                {"subAccount": args.sub_account, "taskId": args.task_id},
            )
            if reconciled.get("success"):
                reconciled_task = _batch_task_data(reconciled)
                reconciled_status = int(
                    reconciled_task.get("status", reconciled_task.get("Status", -1))
                )
                if 3 <= reconciled_status <= 6:
                    return _local_success(
                        args.command,
                        {
                            "reconciled": True,
                            "status": reconciled_status,
                            "taskId": args.task_id,
                        },
                    )
        return launched
    if args.command == "batch-cancel":
        detail = client.call(
            "GetBatchTaskDetail",
            {"subAccount": args.sub_account, "taskId": args.task_id},
        )
        task = _batch_task_data(detail)
        summary = _batch_summary(task)
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
    raise CliError("unsupported command", "argument_error")


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


def _sha256_value(raw: str) -> str:
    value = raw.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise argparse.ArgumentTypeError(
            "file-sha256 must be 64 hexadecimal characters"
        )
    return value


def _page_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--page", type=_bounded_int("page", 1, 100000), default=1)
    parser.add_argument(
        "--page-size",
        type=_bounded_int("page-size", 1, 100),
        default=100,
    )


def _signature_application_options(
    parser: argparse.ArgumentParser, *, submit: bool
) -> None:
    parser.add_argument("--content", required=True)
    parser.add_argument("--purpose", required=True, type=int, choices=(1, 2))
    parser.add_argument("--qualification-id", required=True, type=int)
    parser.add_argument("--sub-account", required=True, action="append")
    parser.add_argument(
        "--channel-type",
        required=True,
        action="append",
        choices=("CN_OTP", "CN_NTC", "CN_MKT"),
    )
    parser.add_argument("--source", required=True, type=int, choices=(1, 2, 3))
    parser.add_argument("--description")
    parser.add_argument("--domain")
    parser.add_argument("--scene")
    parser.add_argument("--project-name")
    parser.add_argument("--app-icp")
    parser.add_argument("--trademark")
    if submit:
        parser.add_argument("--preview-digest", required=True)


def _template_application_options(
    parser: argparse.ArgumentParser, *, submit: bool
) -> None:
    parser.add_argument("--name", required=True)
    parser.add_argument("--content", required=True)
    parser.add_argument(
        "--channel-type", required=True, choices=("CN_OTP", "CN_NTC", "CN_MKT")
    )
    parser.add_argument("--signature", required=True, action="append")
    parser.add_argument("--sub-account", required=True, action="append")
    parser.add_argument("--template-param", action="append", default=[])
    parser.add_argument("--project")
    parser.add_argument("--description")
    parser.add_argument("--short-url-config")
    if submit:
        parser.add_argument("--preview-digest", required=True)


def _send_options(parser: argparse.ArgumentParser, *, submit: bool) -> None:
    parser.add_argument("--sub-account", required=True)
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
    parser.add_argument("--sub-account", required=True)
    parser.add_argument("--task-id", required=True)


def _batch_handoff_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--file-sha256", type=_sha256_value)
    parser.add_argument("--total-count", type=_bounded_int("total-count", 0, 1000000))
    parser.add_argument("--valid-count", type=_bounded_int("valid-count", 0, 1000000))
    parser.add_argument(
        "--invalid-count", type=_bounded_int("invalid-count", 0, 1000000)
    )
    parser.add_argument("--dup-count", type=_bounded_int("dup-count", 0, 1000000))


def build_parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(description="Volcengine domestic SMS")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("auth-doctor", help="check ve and credential readiness")
    auth_login = commands.add_parser(
        "auth-login", help="start login with a system-temporary CLI HOME"
    )
    auth_login.add_argument("--remote", action="store_true")
    auth_login.add_argument("--profile")
    auth_cleanup = commands.add_parser(
        "auth-cleanup", help="remove a validated temporary authentication HOME"
    )
    auth_cleanup.add_argument("--path", required=True)
    auth_cleanup.add_argument("--empty-only", action="store_true")

    groups = commands.add_parser("list-message-groups")
    groups.add_argument("--name")

    group_detail = commands.add_parser("message-group-detail")
    group_detail.add_argument(
        "--sub-account",
        required=True,
        type=_non_empty_text("sub-account"),
    )

    qualifications = commands.add_parser("list-qualifications")
    qualifications.add_argument("--id", dest="qualification_id", type=int)
    qualifications.add_argument("--material-name")
    qualifications.add_argument("--status", action="append", type=int)
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

    signatures = commands.add_parser("list-signatures")
    signatures.add_argument("--signature")
    signatures.add_argument("--sub-account", action="append")
    _page_options(signatures)

    templates = commands.add_parser("list-templates")
    templates.add_argument("--template-id")
    templates.add_argument("--sub-account", action="append")
    templates.add_argument("--signature", action="append")
    _page_options(templates)

    match_template = commands.add_parser("match-template")
    match_template.add_argument("--content", required=True)
    match_template.add_argument("--signature", required=True)
    match_template.add_argument("--sub-account", required=True)
    match_template.add_argument(
        "--channel-type", required=True, choices=("CN_OTP", "CN_NTC", "CN_MKT")
    )

    analytics = commands.add_parser("analytics")
    analytics.add_argument("--start", required=True)
    analytics.add_argument("--end", required=True)
    analytics.add_argument("--sub-account")
    analytics.add_argument(
        "--channel-type", choices=("CN_OTP", "CN_NTC", "CN_MKT")
    )
    analytics.add_argument("--signature")
    analytics.add_argument("--template-id")
    analytics.add_argument("--mobile")
    analytics.add_argument(
        "--bucket",
        choices=("total", "hour", "day"),
        default="day",
    )
    analytics.add_argument("--include-logs", action="store_true")
    analytics.add_argument(
        "--dimension",
        choices=("subAccount", "signature", "template", "time"),
        default="time",
    )
    analytics.add_argument(
        "--page-size",
        type=_bounded_int("page-size", 1, 100),
        default=100,
    )
    analytics.add_argument(
        "--max-pages",
        type=_bounded_int("max-pages", 1, 100),
        default=10,
    )

    _signature_application_options(
        commands.add_parser("signature-preview"), submit=False
    )
    _signature_application_options(commands.add_parser("signature-submit"), submit=True)
    _template_application_options(commands.add_parser("template-preview"), submit=False)
    _template_application_options(commands.add_parser("template-submit"), submit=True)
    _send_options(commands.add_parser("send-preview"), submit=False)
    _send_options(commands.add_parser("send-submit"), submit=True)
    send_status = commands.add_parser("send-status")
    send_status.add_argument("--sub-account", required=True)
    send_status.add_argument("--message-id", required=True)
    _page_options(send_status)
    precheck = commands.add_parser("batch-precheck")
    precheck.add_argument("--file", required=True)
    precheck.add_argument("--template-param", action="append")

    demo = commands.add_parser("batch-template-demo")
    demo.add_argument("--sub-account", required=True)
    demo.add_argument("--template-id", required=True)
    demo.add_argument("--force-update", action="store_true")

    create = commands.add_parser("batch-create")
    create.add_argument("--file", required=True)
    create.add_argument("--sub-account", required=True)
    create.add_argument("--task-name", required=True)
    create.add_argument("--signature", required=True)
    create.add_argument("--template-id", required=True)
    create.add_argument("--scheduled", action="store_true")
    create.add_argument("--send-time")

    detail = commands.add_parser("batch-detail")
    _batch_identity_options(detail)

    tasks = commands.add_parser("batch-list")
    tasks.add_argument("--sub-account", required=True)
    tasks.add_argument("--task-name")
    tasks.add_argument("--signature")
    tasks.add_argument("--template-id")
    _page_options(tasks)

    launch_preview = commands.add_parser("batch-launch-preview")
    _batch_identity_options(launch_preview)
    _batch_handoff_options(launch_preview)

    launch_submit = commands.add_parser("batch-launch-submit")
    _batch_identity_options(launch_submit)
    _batch_handoff_options(launch_submit)
    launch_submit.add_argument("--preview-digest", required=True)
    launch_submit.add_argument("--authorization-text", required=True)

    cancel = commands.add_parser("batch-cancel")
    _batch_identity_options(cancel)
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
        result = execute(
            args,
            client or SmsApiClient(),
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
    output = emit_json(result)
    if result.get("success"):
        stdout.write(output + "\n")
        return 0
    stderr.write(output + "\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
