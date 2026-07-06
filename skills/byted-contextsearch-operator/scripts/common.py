#!/usr/bin/env python3
# Copyright (c) 2026 Beijing Volcano Engine Technology Ltd.
# SPDX-License-Identifier: Apache-2.0

from __future__ import print_function

import json
import os
import sys
from typing import Any, Dict, Optional, Tuple

import volcenginesdkcore
from volcenginesdkcore.rest import ApiException


def print_result(data: Any) -> None:
    """以统一的 JSON 结构输出成功结果。"""
    print(json.dumps({"status": "success", "data": data}, ensure_ascii=False))


def print_error(msg: str, details: Optional[str] = None, exit: bool = True) -> None:
    """以统一的 JSON 结构输出错误信息，可选地退出进程。"""
    err: Dict[str, Any] = {"error": msg}
    if details:
        err["details"] = details
    print(json.dumps(err, ensure_ascii=False))
    if exit:
        sys.exit(1)


def api_call(fn) -> None:
    """封装通用 API 调用，统一处理 ApiException 和其他异常。"""
    try:
        response = fn()
        try:
            result = response.to_dict()  # type: ignore[attr-defined]
        except AttributeError:
            result = response
        print_result(result)
    except ApiException as e:
        msg = str(e)
        instr = ""
        if any(k in msg for k in ("Unauthorized", "Forbidden")):
            instr = "检查 VOLCENGINE_AK/VOLCENGINE_SK 是否正确，并确认具有调用 ContextSearch 接口的权限。"
        elif any(k in msg for k in ("BadRequest", "InvalidParameter")):
            instr = "检查传入的分页参数或其他查询参数是否符合接口要求。"
        elif "NotFound" in msg:
            instr = "确认当前区域已开通 ContextSearch 服务，并支持对应接口。"
        details = f"{msg}\n\nInstruction: {instr}" if instr else msg
        print_error("API Error", details)
    except Exception as e:
        print_error(
            "Unexpected Error",
            f"{str(e)}\n\nInstruction: 请检查网络连通性和 VOLCENGINE_* 环境变量配置。",
        )


def parse_json_payload(
    body_json: Optional[str] = None, body_file: Optional[str] = None
) -> Dict[str, Any]:
    """Parse a JSON object from an inline string or a file path."""
    if body_json and body_file:
        print_error(
            "Invalid Payload", "--body-json and --body-file cannot be used together."
        )

    raw = "{}"
    source = "--body-json"
    if body_file:
        source = body_file
        try:
            with open(body_file, "r", encoding="utf-8") as f:
                raw = f.read()
        except OSError as e:
            print_error("Payload File Error", f"Failed to read {body_file}: {str(e)}")
    elif body_json:
        raw = body_json

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        print_error("Invalid JSON", f"{source} is not valid JSON: {str(e)}")

    if not isinstance(payload, dict):
        print_error("Invalid JSON", f"{source} must be a JSON object.")

    return payload


def universal_call(
    action: str,
    body: Dict[str, Any],
    method: str = "POST",
    service: str = "ctxsearch",
    version: str = "2025-09-01",
) -> None:
    """Call a UniversalApi action with the same signing conventions used by the console."""
    api, _configuration = get_universal_api()
    method_upper = method.upper()
    if method_upper not in {"GET", "POST"}:
        print_error("Invalid Method", "--method must be GET or POST.")

    request_body: Dict[str, Any]
    if method_upper == "GET":
        request_body = volcenginesdkcore.Flatten(body).flat()
        content_type = None
    else:
        request_body = body
        content_type = "application/json"

    def call():
        info_kwargs: Dict[str, Any] = {
            "method": method_upper,
            "action": action,
            "service": service,
            "version": version,
        }
        if content_type:
            info_kwargs["content_type"] = content_type
        info = volcenginesdkcore.UniversalInfo(**info_kwargs)
        return api.do_call(info, request_body)

    api_call(call)


def get_universal_api() -> Tuple[
    volcenginesdkcore.UniversalApi, volcenginesdkcore.Configuration
]:
    """读取环境变量并创建 UniversalApi 实例，关闭 client-side 校验。"""
    ak_candidates = [
        "VOLCENGINE_AK",
        "VOLCENGINE_ACCESS_KEY_ID",
        "VOLCENGINE_ACCESS_KEY",
    ]
    sk_candidates = [
        "VOLCENGINE_SK",
        "VOLCENGINE_SECRET_ACCESS_KEY",
        "VOLCENGINE_SECRET_KEY",
    ]

    ak = None
    sk = None

    for key in ak_candidates:
        value = os.environ.get(key)
        if value:
            ak = value
            break

    for key in sk_candidates:
        value = os.environ.get(key)
        if value:
            sk = value
            break

    region = os.environ.get("VOLCENGINE_REGION", "cn-beijing")
    schema = os.environ.get("VOLCENGINE_SCHEMA", "http")

    if not ak or not sk:
        details = (
            "环境变量中未找到有效的火山引擎访问凭证。\n"
            "请按以下任一名称设置 AK/SK（至少各设置一个）：\n"
            f"AK: {', '.join(ak_candidates)}\n"
            f"SK: {', '.join(sk_candidates)}\n"
            "示例：export VOLCENGINE_AK=... VOLCENGINE_SK=..."
        )
        print_error("Missing Credentials", details)

    configuration = volcenginesdkcore.Configuration()
    configuration.ak = ak
    configuration.sk = sk
    configuration.region = region
    if schema:
        configuration.schema = schema
    # 由服务端进行参数校验，避免本地校验导致的不必要限制。
    configuration.client_side_validation = False

    api_client = volcenginesdkcore.ApiClient(configuration)
    api = volcenginesdkcore.UniversalApi(api_client)
    return api, configuration
