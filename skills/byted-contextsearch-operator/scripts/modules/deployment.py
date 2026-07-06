#!/usr/bin/env python3
# Copyright (c) 2026 Beijing Volcano Engine Technology Ltd.
# SPDX-License-Identifier: Apache-2.0

from __future__ import print_function

import argparse
from datetime import datetime, timedelta
from typing import Any

import volcenginesdkcore

from common import api_call, get_universal_api, print_error


def cmd_deployment_list_builtin(args: argparse.Namespace) -> None:
    """deployment 命名空间下的 list_builtin 子命令：调用 ListAIDeployment 接口，列举预置推理服务。"""
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
        "PageNumber": page_number,
        "PageSize": page_size,
        "Project": project,
        "SortField": "create_time",
        "SortOrder": "DESC",
        "Name": name,
        "IsBuiltin": True,
    }

    def call():
        info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="ListAIDeployment",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        return api.do_call(info, body)

    api_call(call)


def cmd_deployment_list_user(args: argparse.Namespace) -> None:
    """deployment 命名空间下的 list_user 子命令：调用 ListAIDeployment 接口，列举自定义推理服务。"""
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
        "PageNumber": page_number,
        "PageSize": page_size,
        "Project": project,
        "SortField": "create_time",
        "SortOrder": "DESC",
        "Name": name,
        "IsBuiltin": False,
    }

    def call():
        info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="ListAIDeployment",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        return api.do_call(info, body)

    api_call(call)


def cmd_deployment_get(args: argparse.Namespace) -> None:
    """deployment 命名空间下的 get 子命令：调用 GetAIDeployment 接口。"""
    api, _configuration = get_universal_api()

    deployment_id = args.id
    project = args.project

    body = {
        "Id": deployment_id,
        "Project": project,
    }

    def call():
        info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="GetAIDeployment",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        return api.do_call(info, body)

    api_call(call)


def cmd_deployment_usage(args: argparse.Namespace) -> None:
    """deployment 命名空间下的 usage 子命令：调用 GetArkEndpointUsage 接口，支持默认当天或自定义时间范围查询用量。"""
    api, _configuration = get_universal_api()

    deployment_id = args.id
    start_time_arg = args.start_time
    end_time_arg = args.end_time
    interval = args.interval

    # 校验 interval > 0
    if interval <= 0:
        print_error(
            "Invalid Interval",
            "时间间隔参数无效：--interval 必须为正整数。",
        )

    # 处理时间范围：同时提供 / 同时省略 / 仅提供一个
    if start_time_arg is not None and end_time_arg is not None:
        try:
            start_ts = int(str(start_time_arg))
            end_ts = int(str(end_time_arg))
        except ValueError:
            print_error(
                "Invalid Time Range",
                "时间范围参数无效：--start-time 和 --end-time 必须为 Unix 秒级时间戳（整数或数字字符串）。",
            )
    elif start_time_arg is None and end_time_arg is None:
        start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        start_ts = int(start.timestamp())
        end_ts = int(end.timestamp())
    else:
        print_error(
            "Invalid Time Range",
            "时间范围参数无效：--start-time 和 --end-time 必须同时提供或同时省略。",
        )

    body = {
        "Id": deployment_id,
        "StartTime": str(start_ts),
        "EndTime": str(end_ts),
        "Interval": interval,
    }

    def call():
        info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="GetArkEndpointUsage",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        return api.do_call(info, body)

    api_call(call)


def register_deployment(ns_parsers: Any) -> None:
    """在顶层解析器上注册 deployment 命名空间及其子命令。"""
    deployment_parser = ns_parsers.add_parser(
        "deployment",
        help="管理 ContextSearch 推理服务 (deployment)",
    )
    deployment_subparsers = deployment_parser.add_subparsers(
        dest="command", required=True
    )

    # 子命令：deployment list_builtin
    p_dep_list_builtin = deployment_subparsers.add_parser(
        "list_builtin",
        help="列举预置推理服务列表 (ListAIDeployment, IsBuiltin=true)",
    )
    p_dep_list_builtin.add_argument(
        "--page-number",
        type=int,
        default=1,
        help="页码，默认 1",
    )
    p_dep_list_builtin.add_argument(
        "--page-size",
        type=int,
        default=10,
        help="每页条数，默认 10",
    )
    p_dep_list_builtin.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_dep_list_builtin.add_argument(
        "--name",
        default="",
        help="按推理服务名称模糊匹配，可选，默认空字符串",
    )
    p_dep_list_builtin.set_defaults(func=cmd_deployment_list_builtin)

    # 子命令：deployment list_user
    p_dep_list_user = deployment_subparsers.add_parser(
        "list_user",
        help="列举自定义推理服务列表 (ListAIDeployment, IsBuiltin=false)",
    )
    p_dep_list_user.add_argument(
        "--page-number",
        type=int,
        default=1,
        help="页码，默认 1",
    )
    p_dep_list_user.add_argument(
        "--page-size",
        type=int,
        default=10,
        help="每页条数，默认 10",
    )
    p_dep_list_user.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_dep_list_user.add_argument(
        "--name",
        default="",
        help="按推理服务名称模糊匹配，可选，默认空字符串",
    )
    p_dep_list_user.set_defaults(func=cmd_deployment_list_user)

    # 子命令：deployment get
    p_dep_get = deployment_subparsers.add_parser(
        "get",
        help="查询推理服务详情 (GetAIDeployment)",
    )
    p_dep_get.add_argument(
        "--id",
        required=True,
        help="推理服务 Id，必填，例如 2041355986031497217",
    )
    p_dep_get.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_dep_get.set_defaults(func=cmd_deployment_get)

    # 子命令：deployment usage
    p_dep_usage = deployment_subparsers.add_parser(
        "usage",
        help=(
            "查询推理服务用量（GetArkEndpointUsage，默认按本机时区当天 00:00-次日 00:00，"
            "支持自定义 StartTime/EndTime/Interval）。"
        ),
    )
    p_dep_usage.add_argument(
        "--id",
        required=True,
        help="推理服务 Id，必填，例如 2041355986031497217",
    )
    p_dep_usage.add_argument(
        "--start-time",
        dest="start_time",
        default=None,
        help="自定义查询起始时间 Unix 秒（字符串或整数），需与 --end-time 成对使用。",
    )
    p_dep_usage.add_argument(
        "--end-time",
        dest="end_time",
        default=None,
        help="自定义查询结束时间 Unix 秒（字符串或整数），需与 --start-time 成对使用。",
    )
    p_dep_usage.add_argument(
        "--interval",
        type=int,
        default=86400,
        help="聚合时间间隔（秒），默认 86400。",
    )
    p_dep_usage.set_defaults(func=cmd_deployment_usage)
