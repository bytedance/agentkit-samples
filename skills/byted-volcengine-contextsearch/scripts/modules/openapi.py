#!/usr/bin/env python3
# Copyright (c) 2026 Beijing Volcano Engine Technology Ltd.
# SPDX-License-Identifier: Apache-2.0

from __future__ import print_function

import argparse
from typing import Any

from common import parse_json_payload, universal_call


def cmd_openapi_call(args: argparse.Namespace) -> None:
    """Call any ContextSearch OpenAPI action with a JSON payload."""
    body = parse_json_payload(args.body_json, args.body_file)
    universal_call(
        action=args.action,
        body=body,
        method=args.method,
        service=args.service,
        version=args.version,
    )


def register_openapi(ns_parsers: Any) -> None:
    """Register the raw OpenAPI namespace used for console-covered long-tail features."""
    openapi_parser = ns_parsers.add_parser(
        "openapi",
        help="调用任意 ContextSearch OpenAPI action，覆盖控制面长尾能力",
    )
    subparsers = openapi_parser.add_subparsers(dest="command", required=True)

    p_call = subparsers.add_parser(
        "call",
        help="直接调用指定 action；POST 使用 JSON body，GET 自动 Flatten 查询参数",
    )
    p_call.add_argument(
        "--action", required=True, help="OpenAPI Action，例如 CreateAgenticScene"
    )
    p_call.add_argument(
        "--method", choices=["GET", "POST"], default="POST", help="HTTP 方法，默认 POST"
    )
    p_call.add_argument(
        "--service", default="ctxsearch", help='服务名，默认 "ctxsearch"'
    )
    p_call.add_argument(
        "--version", default="2025-09-01", help='版本号，默认 "2025-09-01"'
    )
    p_call.add_argument(
        "--body-json",
        default="",
        help='JSON 对象字符串，例如 \'{"Project":"default"}\'',
    )
    p_call.add_argument(
        "--body-file", default="", help="JSON 对象文件路径；与 --body-json 二选一"
    )
    p_call.set_defaults(func=cmd_openapi_call)
