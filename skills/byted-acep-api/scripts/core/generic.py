#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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

"""通用 Action 调用模块。"""

from . import cli_common as cli


def cmd_action_call(args):
    params = cli.parse_json_option(args.params_json, "--params-json", dict) or {}
    params.update(cli.parse_key_value_params(args.param, "--param"))
    if args.product_id and "ProductId" not in params:
        params["ProductId"] = args.product_id

    result = cli.get_client().request_action(
        args.action,
        json_body=args.json_body,
        version=args.version,
        **params,
    )
    cli.print_result(result)


def register(subparsers):
    action_call_parser = subparsers.add_parser(
        "action-call",
        help="通用 Action 调用",
        description="通用 Action 调用",
        epilog=(
            "示例:\n"
            "  vephone action-call ListOperableProduct --json-body --param Count=10\n"
            "  vephone action-call SetProxy --json-body --param ProductId=pid --param ProxyStatus=1 "
            '--param PodIdList=["pod-1","pod-2"]\n'
            "  vephone action-call CreatePod --param ProductId=pid --param PodName=demo "
            "--param Start=true --param UpBandwidthLimit=10\n"
            "\n"
            "多个参数可重复传入 --param，形式为 --param Key=Value --param Key2=Value2。"
        ),
        formatter_class=cli.argparse.RawDescriptionHelpFormatter,
    )
    action_call_parser.add_argument(
        "action", help="OpenAPI Action 名称，例如 ListOperableProduct"
    )
    action_call_parser.add_argument(
        "--json-body",
        action="store_true",
        help="以 JSON body 方式调用；默认按 query string 方式调用",
    )
    action_call_parser.add_argument(
        "--version",
        help="显式指定 API Version；不传则使用客户端内置的 Action-Version 映射",
    )
    action_call_parser.add_argument(
        "--product-id",
        help="便捷参数；未在其他参数中提供 ProductId 时，自动注入为 ProductId",
    )
    action_call_parser.add_argument(
        "--param",
        action="append",
        metavar="Key=Value",
        help="单个请求参数；Value 会优先按 JSON 解析，失败时按字符串处理，可重复传入",
    )
    action_call_parser.add_argument(
        "--params-json",
        help="批量请求参数 JSON 对象；会先合并，再由 --param 覆盖同名键。命令行中请整体加引号，例如 --params-json '{\"Count\":1}'",
    )
    action_call_parser.set_defaults(func=cmd_action_call)
