#!/usr/bin/env python3
# Copyright (c) 2026 Beijing Volcano Engine Technology Ltd.
# SPDX-License-Identifier: Apache-2.0

from __future__ import print_function

import argparse
from typing import Any

import volcenginesdkcore
from volcenginesdkcore.rest import ApiException

from common import api_call, get_universal_api, print_error


def cmd_apikey_list(args: argparse.Namespace) -> None:
    """apikey 命名空间下的 list 子命令：调用 ListMLApiKeys 接口。"""
    api, _configuration = get_universal_api()

    page_number = args.page_number
    page_size = args.page_size
    project = args.project
    name = args.name

    if page_number <= 0 or page_size <= 0:
        print_error(
            "Invalid Pagination",
            "分页参数无效：--page-number 和 --page-size 必须为正整数。",
        )

    body = {
        "PageSize": page_size,
        "PageNumber": page_number,
        "Project": project,
        "Name": name,
        "Encrypt": True,
    }

    def call():
        info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="ListMLApiKeys",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        return api.do_call(info, body)

    api_call(call)


def cmd_apikey_create(args: argparse.Namespace) -> None:
    """apikey 命名空间下的 create 子命令：在创建前校验单个 Project 下 API Key 数量上限。"""
    api, _configuration = get_universal_api()

    name = args.name
    project = args.project

    # 第一步：调用 ListMLApiKeys 获取当前 Project 下的 total。
    list_body = {
        "PageSize": 1,
        "PageNumber": 1,
        "Project": project,
        "Name": "",
        "Encrypt": True,
    }

    total = 0
    try:
        list_info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="ListMLApiKeys",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        list_resp = api.do_call(list_info, list_body)
        try:
            list_data = list_resp.to_dict()  # type: ignore[attr-defined]
        except AttributeError:
            list_data = list_resp

        if isinstance(list_data, dict):
            total_value = list_data.get("Total")
            if isinstance(total_value, int):
                total = total_value
            else:
                total_num_value = list_data.get("TotalNum")
                if isinstance(total_num_value, int):
                    total = total_num_value
                else:
                    items = list_data.get("Items") or []
                    try:
                        total = len(items)
                    except TypeError:
                        total = 0
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

    if total >= 5:
        print_error(
            "API Key Limit Exceeded",
            f"Each project can have at most 5 API Keys. Current total: {total}. Please delete unused keys and retry.",
        )

    # 第二步：数量未超限时，调用 CreateMLApiKey 创建新的 API Key。
    create_body = {
        "Project": project,
        "Name": name,
    }

    def call():
        info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="CreateMLApiKey",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        return api.do_call(info, create_body)

    api_call(call)


def cmd_apikey_delete(args: argparse.Namespace) -> None:
    """apikey 命名空间下的 delete 子命令：删除指定的 API Key（危险操作，必须 --confirm）。"""
    api, _configuration = get_universal_api()

    apikey_id = args.id
    project = args.project
    confirm = args.confirm

    if not confirm:
        print_error(
            "Confirmation Required",
            "Refusing to delete without --confirm. Rerun with: apikey delete --id <id> --project <project> --confirm",
        )

    body = {
        "Project": project,
        "Id": apikey_id,
    }

    def call():
        info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="DeleteMLApiKey",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        return api.do_call(info, body)

    api_call(call)


def register_apikey(ns_parsers: Any) -> None:
    """在顶层解析器上注册 apikey 命名空间及其子命令。"""
    apikey_namespace = "api" + "key"
    apikey_parser = ns_parsers.add_parser(
        apikey_namespace,
        help="管理 ContextSearch API Key (apikey)",
    )
    apikey_subparsers = apikey_parser.add_subparsers(dest="command", required=True)

    # 子命令：apikey list
    p_apikey_list = apikey_subparsers.add_parser(
        "list",
        help="列举 API Key 列表 (ListMLApiKeys)",
    )
    p_apikey_list.add_argument(
        "--page-number",
        type=int,
        default=1,
        help="页码，默认 1",
    )
    p_apikey_list.add_argument(
        "--page-size",
        type=int,
        default=10,
        help="每页条数，默认 10",
    )
    p_apikey_list.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_apikey_list.add_argument(
        "--name",
        default="",
        help="按名称模糊匹配，可选，默认空字符串",
    )
    p_apikey_list.set_defaults(func=cmd_apikey_list)

    # 子命令：apikey create
    p_apikey_create = apikey_subparsers.add_parser(
        "create",
        help="创建 API Key（创建前校验最多 5 个）",
    )
    p_apikey_create.add_argument(
        "--name",
        required=True,
        help="API Key 名称，必填",
    )
    p_apikey_create.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_apikey_create.set_defaults(func=cmd_apikey_create)

    # 子命令：apikey delete
    p_apikey_delete = apikey_subparsers.add_parser(
        "delete",
        help="删除 API Key（危险操作，必须 --confirm）",
    )
    p_apikey_delete.add_argument(
        "--id",
        required=True,
        help="API Key Id，必填，例如 2042224690871406593",
    )
    p_apikey_delete.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_apikey_delete.add_argument(
        "--confirm",
        action="store_true",
        help="危险操作，必须显式提供该开关才允许删除",
    )
    p_apikey_delete.set_defaults(func=cmd_apikey_delete)
