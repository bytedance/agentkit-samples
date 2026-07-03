#!/usr/bin/env python3
# Copyright (c) 2026 Beijing Volcano Engine Technology Ltd.
# SPDX-License-Identifier: Apache-2.0

from __future__ import print_function

import argparse
from typing import Any

import volcenginesdkcore

from common import api_call, get_universal_api, print_error


def cmd_model_list(args: argparse.Namespace) -> None:
    """model 命名空间下的 list 子命令：调用 ctxsearch 的 ListAIModel 接口，Types 固定为 SYSTEM/ARK。"""
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

    # 构造请求体：分页 + Project + 固定排序与类型 + 可选名称过滤。
    body = {
        "PageNumber": page_number,
        "PageSize": page_size,
        "Project": project,
        "SortField": "priority",
        "SortOrder": "DESC",
        "Name": name,
        "Types": ["SYSTEM", "ARK"],
    }

    def call():
        info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="ListAIModel",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        return api.do_call(info, body)

    api_call(call)


def cmd_model_list_user(args: argparse.Namespace) -> None:
    """model 命名空间下的 list_user 子命令：调用 ctxsearch 的 ListAIModel 接口，Types 固定为 USER。"""
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

    # 构造请求体：分页 + Project + 固定排序与类型 + 可选名称过滤，Types 固定为 USER。
    body = {
        "PageNumber": page_number,
        "PageSize": page_size,
        "Project": project,
        "SortField": "priority",
        "SortOrder": "DESC",
        "Name": name,
        "Types": ["USER"],
    }

    def call():
        info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="ListAIModel",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        return api.do_call(info, body)

    api_call(call)


def cmd_model_get(args: argparse.Namespace) -> None:
    """model 命名空间下的 get 子命令：调用 ctxsearch 的 GetAIModel 接口。"""
    api, _configuration = get_universal_api()

    model_id = args.id
    project = args.project

    body = {
        "Id": model_id,
        "Project": project,
    }

    def call():
        info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="GetAIModel",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        return api.do_call(info, body)

    api_call(call)


def register_model(ns_parsers: Any) -> None:
    """在顶层解析器上注册 model 命名空间及其子命令。"""
    model_parser = ns_parsers.add_parser(
        "model", help="管理 ContextSearch 公共/自定义模型 (model)"
    )
    model_subparsers = model_parser.add_subparsers(dest="command", required=True)

    # 子命令：model list
    p_model_list = model_subparsers.add_parser(
        "list",
        help="列举公共模型列表 (ListAIModel)",
    )
    p_model_list.add_argument(
        "--page-number",
        type=int,
        default=1,
        help="页码，默认 1",
    )
    p_model_list.add_argument(
        "--page-size",
        type=int,
        default=10,
        help="每页条数，默认 10",
    )
    p_model_list.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_model_list.add_argument(
        "--name",
        default="",
        help="按模型名称模糊匹配，可选，默认空字符串",
    )
    p_model_list.set_defaults(func=cmd_model_list)

    # 子命令：model list_user
    p_model_list_user = model_subparsers.add_parser(
        "list_user",
        help="列举自定义模型列表 (ListAIModel, Types=USER)",
    )
    p_model_list_user.add_argument(
        "--page-number",
        type=int,
        default=1,
        help="页码，默认 1",
    )
    p_model_list_user.add_argument(
        "--page-size",
        type=int,
        default=10,
        help="每页条数，默认 10",
    )
    p_model_list_user.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_model_list_user.add_argument(
        "--name",
        default="",
        help="按模型名称模糊匹配，可选，默认空字符串",
    )
    p_model_list_user.set_defaults(func=cmd_model_list_user)

    # 子命令：model get
    p_model_get = model_subparsers.add_parser(
        "get",
        help="查询模型详情 (GetAIModel)",
    )
    p_model_get.add_argument(
        "--id",
        required=True,
        help="模型 Id，必填，例如 1000043",
    )
    p_model_get.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_model_get.set_defaults(func=cmd_model_get)
