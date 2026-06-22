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

"""业务模块。"""
from . import cli_common as cli


def cmd_list_products(args):
    cli.print_result(cli.get_client().list_products(
        product_id=args.product_id,
        product_name=args.product_name,
        cloudphone_product_type=args.cloudphone_product_type,
        resource_type=args.resource_type,
        cloudphone_product_use_type=args.cloudphone_product_use_type,
        offset=args.offset,
        count=args.count,
    ))


def register(subparsers):
    list_products_parser = subparsers.add_parser('list-products', help='获取业务列表')
    list_products_parser.add_argument('--product-id', help='业务 ID')
    list_products_parser.add_argument('--product-name', help='业务名称')
    list_products_parser.add_argument('--cloudphone-product-type', type=int, default=5, help='业务类型：4=IPaaS，5=云手机')
    list_products_parser.add_argument('--resource-type', type=int, help='资源类型：100=云盘存储，200=本地存储')
    list_products_parser.add_argument('--cloudphone-product-use-type', type=int, help='用途：1=云手机业务，2=MUA业务')
    list_products_parser.add_argument('--offset', type=int, help='分页偏移量')
    list_products_parser.add_argument('--count', type=int, help='单页数量')
    list_products_parser.set_defaults(func=cmd_list_products)
