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

"""屏幕布局模块。"""
from . import cli_common as cli


def cmd_list_display_layouts(args):
    cli.print_result(cli.get_client().list_display_layouts(
        offset=args.offset,
        count=args.count,
        product_id=args.product_id,
        DisplayLayoutId=args.display_layout_id,
    ))


def cmd_detail_display_layout(args):
    cli.print_result(cli.get_client().detail_display_layout(display_layout_id=args.display_layout_id, product_id=args.product_id))


def cmd_create_display_layout(args):
    cli.print_result(cli.get_client().create_display_layout(
        display_layout_id=args.display_layout_id,
        width=args.width,
        height=args.height,
        product_id=args.product_id,
        density=args.density,
        fps=args.fps,
        extra=args.extra,
    ))


def cmd_delete_display_layout(args):
    cli.print_result(cli.get_client().delete_display_layout(
        display_layout_id=args.display_layout_id,
        product_id=args.product_id,
    ))


def register(subparsers):

    list_display_layouts_parser = subparsers.add_parser('list-display-layouts', help='查询基础版屏幕布局列表')
    list_display_layouts_parser.add_argument('product_id', help='产品 ID')
    list_display_layouts_parser.add_argument('--display-layout-id', help='屏幕布局 ID')
    list_display_layouts_parser.add_argument('--offset', type=int, default=0, help='查询起始位置')
    list_display_layouts_parser.add_argument('--count', type=int, default=10, help='返回数量')
    list_display_layouts_parser.set_defaults(func=cmd_list_display_layouts)

    detail_display_layout_parser = subparsers.add_parser('detail-display-layout', help='查询基础版屏幕布局详情')
    detail_display_layout_parser.add_argument('product_id', help='产品 ID')
    detail_display_layout_parser.add_argument('display_layout_id', help='屏幕布局 ID')
    detail_display_layout_parser.set_defaults(func=cmd_detail_display_layout)

    create_display_layout_parser = subparsers.add_parser('create-display-layout', help='创建屏幕布局')
    create_display_layout_parser.add_argument('product_id', help='产品 ID')
    create_display_layout_parser.add_argument('--display-layout-id', required=True, help='屏幕布局 ID')
    create_display_layout_parser.add_argument('--width', type=int, required=True, help='宽度 px')
    create_display_layout_parser.add_argument('--height', type=int, required=True, help='高度 px')
    create_display_layout_parser.add_argument('--density', type=int, help='DPI')
    create_display_layout_parser.add_argument('--fps', type=int, help='FPS')
    create_display_layout_parser.add_argument('--extra', help='备注')
    create_display_layout_parser.set_defaults(func=cmd_create_display_layout)

    delete_display_layout_parser = subparsers.add_parser('delete-display-layout', help='删除屏幕布局')
    delete_display_layout_parser.add_argument('product_id', help='产品 ID')
    delete_display_layout_parser.add_argument('--display-layout-id', required=True, help='屏幕布局 ID')
    delete_display_layout_parser.set_defaults(func=cmd_delete_display_layout)
