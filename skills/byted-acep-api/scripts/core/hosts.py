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

"""云机模块。"""
from . import cli_common as cli


def cmd_list_hosts(args):
    result = cli.get_client().list_hosts(
        max_results=args.max_results,
        next_token=args.next_token,
        product_id=args.product_id,
        HostIdList=cli.parse_csv_values(args.host_id_list),
        StatusList=cli.parse_csv_values(args.status_list, int),
        Dc=args.dc,
        Region=args.region,
        ConfigurationCode=args.configuration_code,
        VolcRegion=args.volc_region,
        ResourceSetId=args.resource_set_id,
        UseStatus=args.use_status,
        AuthorityStatus=args.authority_status,
        PodIdList=cli.parse_csv_values(args.pod_id_list),
        ExpireTimeBefore=args.expire_time_before,
        SyncRenewType=args.sync_renew_type,
    )
    cli.print_result(result)


def cmd_detail_host(args):
    cli.print_result(cli.get_client().detail_host(host_id=args.host_id, product_id=args.product_id))


def cmd_update_host(args):
    cli.print_result(cli.get_client().update_host(
        host_id_list=cli.parse_csv(args.host_id_list),
        configuration_code=args.configuration_code,
        **cli.request_kwargs(args),
    ))


def cmd_reboot_host(args):
    cli.print_result(cli.get_client().reboot_host(
        host_id_list=cli.parse_csv(args.host_id_list),
        force=args.force,
        **cli.request_kwargs(args),
    ))


def cmd_reset_host(args):
    cli.print_result(cli.get_client().reset_host(
        host_id_list=cli.parse_csv(args.host_id_list),
        force=args.force,
        **cli.request_kwargs(args),
    ))


def register(subparsers):

    list_hosts_parser = subparsers.add_parser('list-hosts', help='查询云机列表')
    list_hosts_parser.add_argument('product_id', help='产品 ID')
    list_hosts_parser.add_argument('--host-id-list', help='云机 ID 列表，逗号分隔')
    list_hosts_parser.add_argument('--status-list', help='状态列表，逗号分隔')
    list_hosts_parser.add_argument('--dc', help='机房 ID')
    list_hosts_parser.add_argument('--region', help='大区 ID')
    list_hosts_parser.add_argument('--configuration-code', help='实例规格 ID')
    list_hosts_parser.add_argument('--volc-region', help='物理地域')
    list_hosts_parser.add_argument('--resource-set-id', help='资源组 ID')
    list_hosts_parser.add_argument('--use-status', type=int, help='占用状态')
    list_hosts_parser.add_argument('--authority-status', type=int, help='运维授权状态')
    list_hosts_parser.add_argument('--pod-id-list', help='实例 ID 列表，逗号分隔')
    list_hosts_parser.add_argument('--expire-time-before', help='过期时间早于该值')
    list_hosts_parser.add_argument('--sync-renew-type', action='store_true', help='返回续费类型')
    list_hosts_parser.add_argument('--max-results', type=int, default=10, help='每页数量')
    list_hosts_parser.add_argument('--next-token', help='分页游标')
    list_hosts_parser.set_defaults(func=cmd_list_hosts)

    detail_host_parser = subparsers.add_parser('detail-host', help='查询云机详情')
    detail_host_parser.add_argument('product_id', help='产品 ID')
    detail_host_parser.add_argument('host_id', help='云机 ID')
    detail_host_parser.set_defaults(func=cmd_detail_host)

    update_host_parser = subparsers.add_parser('update-host', help='更新云机可运行实例规格')
    update_host_parser.add_argument('product_id', help='产品 ID')
    update_host_parser.add_argument('host_id_list', help='云机 ID 列表，逗号分隔')
    update_host_parser.add_argument('--configuration-code', help='目标实例规格 ID')
    update_host_parser.set_defaults(func=cmd_update_host)

    reboot_host_parser = subparsers.add_parser('reboot-host', help='重启云机')
    reboot_host_parser.add_argument('product_id', help='产品 ID')
    reboot_host_parser.add_argument('host_id_list', help='云机 ID 列表，逗号分隔')
    reboot_host_parser.add_argument('--force', action='store_true', help='强制重启')
    reboot_host_parser.set_defaults(func=cmd_reboot_host)

    reset_host_parser = subparsers.add_parser('reset-host', help='重置云机')
    reset_host_parser.add_argument('product_id', help='产品 ID')
    reset_host_parser.add_argument('host_id_list', help='云机 ID 列表，逗号分隔')
    reset_host_parser.add_argument('--force', action='store_true', help='强制重置')
    reset_host_parser.set_defaults(func=cmd_reset_host)
