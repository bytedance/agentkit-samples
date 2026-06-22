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

"""机房模块。"""
from . import cli_common as cli


def cmd_get_dc_bandwidth_daily_peak(args):
    cli.print_result(cli.get_client().get_dc_bandwidth_daily_peak(
        dc_id_list=cli.parse_csv(args.dc_id_list),
        product_id=args.product_id,
        StartDate=args.start_date,
        EndDate=args.end_date,
    ))


def cmd_list_dcs(args):
    cli.print_result(cli.get_client().list_dcs(
        product_id=args.product_id,
        volc_region=args.volc_region,
        region=args.region,
        isp=args.isp,
        server_type_code=args.server_type_code,
        offset=args.offset,
        count=args.count,
    ))


def register(subparsers):

    get_dc_bandwidth_daily_peak_parser = subparsers.add_parser('get-dc-bandwidth-daily-peak', help='获取机房带宽日峰值')
    get_dc_bandwidth_daily_peak_parser.add_argument('product_id', help='产品 ID')
    get_dc_bandwidth_daily_peak_parser.add_argument('dc_id_list', help='机房 ID 列表，多个值用逗号分隔')
    get_dc_bandwidth_daily_peak_parser.add_argument('--start-date', help='开始日期 yyyy-MM-dd')
    get_dc_bandwidth_daily_peak_parser.add_argument('--end-date', help='结束日期 yyyy-MM-dd')
    get_dc_bandwidth_daily_peak_parser.set_defaults(func=cmd_get_dc_bandwidth_daily_peak)

    list_dcs_parser = subparsers.add_parser('list-dcs', help='获取机房列表')
    list_dcs_parser.add_argument('product_id', help='产品 ID')
    list_dcs_parser.add_argument('--volc-region', choices=['inner', 'cn-hongkong-pop'], help='机房所在物理区域')
    list_dcs_parser.add_argument('--region', choices=['cn-north', 'cn-south', 'cn-east', 'cn-middle', 'cn-southwest', 'cn-hongkong-pop'], help='机房所在大区 ID')
    list_dcs_parser.add_argument('--isp', type=int, choices=[1, 2, 4, 7, 8], help='网络运营商 ID：1 移动，2 联通，4 电信，7 三线，8 BGP')
    list_dcs_parser.add_argument('--server-type-code', choices=['g2.8c12g', 'g2.8c16g.basic', 'g2.8c16g.plus', 'g3.host8c24g256g'], help='云机规格，仅本地存储业务适用')
    list_dcs_parser.add_argument('--offset', type=int, help='查询偏移量')
    list_dcs_parser.add_argument('--count', type=int, help='单次返回条数')
    list_dcs_parser.set_defaults(func=cmd_list_dcs)
