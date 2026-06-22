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

"""网络模块。"""
from . import cli_common as cli


def cmd_list_port_mapping_rules(args):
    cli.print_result(cli.get_client().list_port_mapping_rules(
        offset=args.offset,
        count=args.count,
        product_id=args.product_id,
        PortMappingRuleId=args.port_mapping_rule_id,
        Protocol=args.protocol,
        VolcRegion=args.volc_region,
    ))


def cmd_detail_port_mapping_rule(args):
    cli.print_result(cli.get_client().detail_port_mapping_rule(port_mapping_rule_id=args.port_mapping_rule_id, product_id=args.product_id))


def cmd_create_port_mapping_rule(args):
    cli.print_result(cli.get_client().create_port_mapping_rule(
        source_port=args.source_port,
        product_id=args.product_id,
        port_mapping_rule_id=args.port_mapping_rule_id,
        protocol=args.protocol,
        isp=args.isp,
        direction=args.direction,
        volc_region=args.volc_region,
    ))


def cmd_bind_port_mapping_rule(args):
    cli.print_result(cli.get_client().bind_port_mapping_rule(
        pod_id_list=cli.parse_csv_values(args.pod_id_list),
        port_mapping_rule_id_list=cli.parse_csv_values(args.port_mapping_rule_id_list),
        product_id=args.product_id,
    ))


def cmd_unbind_port_mapping_rule(args):
    cli.print_result(cli.get_client().unbind_port_mapping_rule(
        pod_id_list=cli.parse_csv_values(args.pod_id_list),
        port_mapping_rule_id_list=cli.parse_csv_values(args.port_mapping_rule_id_list),
        product_id=args.product_id,
    ))


def cmd_list_dns_rules(args):
    cli.print_result(cli.get_client().list_dns_rules(
        offset=args.offset,
        count=args.count,
        product_id=args.product_id,
        DNSName=args.dns_name,
        Type=args.type,
    ))


def cmd_detail_dns_rule(args):
    cli.print_result(cli.get_client().detail_dns_rule(dns_id=args.dns_id, product_id=args.product_id))


def cmd_create_dns_rule(args):
    cli.print_result(cli.get_client().create_dns_rule(
        dc=args.dc,
        ip_list=cli.parse_csv_values(args.ip_list),
        product_id=args.product_id,
        dns_name=args.dns_name,
        type=args.type,
    ))


def cmd_update_dns_rule(args):
    cli.print_result(cli.get_client().update_dns_rule(
        dns_id=args.dns_id,
        product_id=args.product_id,
        dns_name=args.dns_name,
        type=args.type,
        ip_list=cli.parse_csv_values(args.ip_list) if args.ip_list else None,
    ))


def cmd_delete_dns_rule(args):
    cli.print_result(cli.get_client().delete_dns_rule(
        dns_id=args.dns_id,
        product_id=args.product_id,
    ))


def cmd_list_custom_routes(args):
    cli.print_result(cli.get_client().list_custom_routes(
        max_results=args.max_results,
        next_token=args.next_token,
        product_id=args.product_id,
        CustomRouteId=args.custom_route_id,
        CustomRouteName=args.custom_route_name,
        Zone=args.zone,
        DstIP=args.dst_ip,
    ))


def cmd_add_custom_route(args):
    cli.print_result(cli.get_client().add_custom_route(
        zone=args.zone,
        dst_ip=args.dst_ip,
        proxy_protocol=args.proxy_protocol,
        proxy_port=args.proxy_port,
        product_id=args.product_id,
        custom_route_name=args.custom_route_name,
        proxy_user_name=args.proxy_user_name,
        proxy_password=args.proxy_password,
        proxy_cipher=args.proxy_cipher,
    ))


def cmd_update_custom_route(args):
    cli.print_result(cli.get_client().update_custom_route(
        custom_route_id=args.custom_route_id,
        product_id=args.product_id,
        custom_route_name=args.custom_route_name,
        dst_ip=args.dst_ip,
        proxy_protocol=args.proxy_protocol,
        proxy_port=args.proxy_port,
        proxy_user_name=args.proxy_user_name,
        proxy_password=args.proxy_password,
        proxy_cipher=args.proxy_cipher,
    ))


def cmd_delete_custom_route(args):
    cli.print_result(cli.get_client().delete_custom_route(
        custom_route_id=args.custom_route_id,
        product_id=args.product_id,
    ))


def register(subparsers):
    list_port_mapping_rules_parser = subparsers.add_parser('list-port-mapping-rules', help='查询端口映射列表')
    list_port_mapping_rules_parser.add_argument('product_id', help='产品 ID')
    list_port_mapping_rules_parser.add_argument('--offset', type=int, default=0, help='查询起始位置')
    list_port_mapping_rules_parser.add_argument('--count', type=int, default=10, help='返回数量')
    list_port_mapping_rules_parser.add_argument('--port-mapping-rule-id', help='端口映射规则 ID')
    list_port_mapping_rules_parser.add_argument('--protocol', choices=['tcp', 'udp'], help='协议')
    list_port_mapping_rules_parser.add_argument('--volc-region', help='物理地域')
    list_port_mapping_rules_parser.set_defaults(func=cmd_list_port_mapping_rules)

    detail_port_mapping_rule_parser = subparsers.add_parser('detail-port-mapping-rule', help='查询端口映射详情')
    detail_port_mapping_rule_parser.add_argument('product_id', help='产品 ID')
    detail_port_mapping_rule_parser.add_argument('port_mapping_rule_id', help='端口映射规则 ID')
    detail_port_mapping_rule_parser.set_defaults(func=cmd_detail_port_mapping_rule)

    create_port_mapping_rule_parser = subparsers.add_parser('create-port-mapping-rule', help='创建端口映射规则')
    create_port_mapping_rule_parser.add_argument('product_id', help='产品 ID')
    create_port_mapping_rule_parser.add_argument('--port-mapping-rule-id', help='端口映射规则 ID')
    create_port_mapping_rule_parser.add_argument('--protocol', choices=['tcp', 'udp', 'all'], help='协议')
    create_port_mapping_rule_parser.add_argument('--source-port', type=int, required=True, help='源端口')
    create_port_mapping_rule_parser.add_argument('--isp', type=int, help='运营商')
    create_port_mapping_rule_parser.add_argument('--direction', choices=['Inbound', 'Bidirectional'], help='流量方向')
    create_port_mapping_rule_parser.add_argument('--volc-region', help='物理地域')
    create_port_mapping_rule_parser.set_defaults(func=cmd_create_port_mapping_rule)

    bind_port_mapping_rule_parser = subparsers.add_parser('bind-port-mapping-rule', help='绑定端口映射规则')
    bind_port_mapping_rule_parser.add_argument('product_id', help='产品 ID')
    bind_port_mapping_rule_parser.add_argument('--pod-id-list', required=True, help='实例 ID 列表，逗号分隔')
    bind_port_mapping_rule_parser.add_argument('--port-mapping-rule-id-list', required=True, help='规则 ID 列表，逗号分隔')
    bind_port_mapping_rule_parser.set_defaults(func=cmd_bind_port_mapping_rule)

    unbind_port_mapping_rule_parser = subparsers.add_parser('unbind-port-mapping-rule', help='解绑端口映射规则')
    unbind_port_mapping_rule_parser.add_argument('product_id', help='产品 ID')
    unbind_port_mapping_rule_parser.add_argument('--pod-id-list', required=True, help='实例 ID 列表，逗号分隔')
    unbind_port_mapping_rule_parser.add_argument('--port-mapping-rule-id-list', required=True, help='规则 ID 列表，逗号分隔')
    unbind_port_mapping_rule_parser.set_defaults(func=cmd_unbind_port_mapping_rule)

    list_dns_rules_parser = subparsers.add_parser('list-dns-rules', help='查询 DNS 规则列表')
    list_dns_rules_parser.add_argument('product_id', help='产品 ID')
    list_dns_rules_parser.add_argument('--offset', type=int, default=0, help='查询起始位置')
    list_dns_rules_parser.add_argument('--count', type=int, default=10, help='返回数量')
    list_dns_rules_parser.add_argument('--dns-name', help='DNS 规则名称')
    list_dns_rules_parser.add_argument('--type', type=int, help='DNS 规则类型：0=非默认，1=默认')
    list_dns_rules_parser.set_defaults(func=cmd_list_dns_rules)

    detail_dns_rule_parser = subparsers.add_parser('detail-dns-rule', help='查询 DNS 规则详情')
    detail_dns_rule_parser.add_argument('product_id', help='产品 ID')
    detail_dns_rule_parser.add_argument('dns_id', help='DNS 规则 ID')
    detail_dns_rule_parser.set_defaults(func=cmd_detail_dns_rule)

    create_dns_rule_parser = subparsers.add_parser('create-dns-rule', help='创建 DNS 规则')
    create_dns_rule_parser.add_argument('product_id', help='产品 ID')
    create_dns_rule_parser.add_argument('--dc', required=True, help='机房 ID')
    create_dns_rule_parser.add_argument('--dns-name', help='DNS 名称')
    create_dns_rule_parser.add_argument('--type', type=int, help='类型：0=非默认，1=默认')
    create_dns_rule_parser.add_argument('--ip-list', required=True, help='IP 列表，逗号分隔')
    create_dns_rule_parser.set_defaults(func=cmd_create_dns_rule)

    update_dns_rule_parser = subparsers.add_parser('update-dns-rule', help='更新 DNS 规则')
    update_dns_rule_parser.add_argument('product_id', help='产品 ID')
    update_dns_rule_parser.add_argument('--dns-id', required=True, help='DNS 规则 ID')
    update_dns_rule_parser.add_argument('--dns-name', help='DNS 名称')
    update_dns_rule_parser.add_argument('--type', type=int, help='类型')
    update_dns_rule_parser.add_argument('--ip-list', help='IP 列表，逗号分隔')
    update_dns_rule_parser.set_defaults(func=cmd_update_dns_rule)

    delete_dns_rule_parser = subparsers.add_parser('delete-dns-rule', help='删除 DNS 规则')
    delete_dns_rule_parser.add_argument('product_id', help='产品 ID')
    delete_dns_rule_parser.add_argument('--dns-id', required=True, help='DNS 规则 ID')
    delete_dns_rule_parser.set_defaults(func=cmd_delete_dns_rule)

    list_custom_routes_parser = subparsers.add_parser('list-custom-routes', help='查询自定义路由规则')
    list_custom_routes_parser.add_argument('product_id', help='产品 ID')
    list_custom_routes_parser.add_argument('--custom-route-id', help='自定义路由规则 ID')
    list_custom_routes_parser.add_argument('--custom-route-name', help='自定义路由名称')
    list_custom_routes_parser.add_argument('--zone', help='区域/片区 ID')
    list_custom_routes_parser.add_argument('--dst-ip', help='代理服务器 IP')
    list_custom_routes_parser.add_argument('--max-results', type=int, default=10, help='每页数量，最大 100')
    list_custom_routes_parser.add_argument('--next-token', help='分页游标')
    list_custom_routes_parser.set_defaults(func=cmd_list_custom_routes)

    add_custom_route_parser = subparsers.add_parser('add-custom-route', help='创建自定义路由')
    add_custom_route_parser.add_argument('product_id', help='产品 ID')
    add_custom_route_parser.add_argument('--custom-route-name', help='规则名称')
    add_custom_route_parser.add_argument('--zone', required=True, help='区域/片区 ID')
    add_custom_route_parser.add_argument('--dst-ip', required=True, help='代理服务器 IP')
    add_custom_route_parser.add_argument('--proxy-protocol', choices=['ss', 'socks5'], required=True, help='代理协议')
    add_custom_route_parser.add_argument('--proxy-port', type=int, required=True, help='代理端口')
    add_custom_route_parser.add_argument('--proxy-user-name', help='代理用户名')
    add_custom_route_parser.add_argument('--proxy-password', help='代理密码')
    add_custom_route_parser.add_argument('--proxy-cipher', help='代理加密算法')
    add_custom_route_parser.set_defaults(func=cmd_add_custom_route)

    update_custom_route_parser = subparsers.add_parser('update-custom-route', help='更新自定义路由')
    update_custom_route_parser.add_argument('product_id', help='产品 ID')
    update_custom_route_parser.add_argument('--custom-route-id', required=True, help='规则 ID')
    update_custom_route_parser.add_argument('--custom-route-name', help='规则名称')
    update_custom_route_parser.add_argument('--dst-ip', help='代理服务器 IP')
    update_custom_route_parser.add_argument('--proxy-protocol', choices=['ss', 'socks5'], help='代理协议')
    update_custom_route_parser.add_argument('--proxy-port', type=int, help='代理端口')
    update_custom_route_parser.add_argument('--proxy-user-name', help='代理用户名')
    update_custom_route_parser.add_argument('--proxy-password', help='代理密码')
    update_custom_route_parser.add_argument('--proxy-cipher', help='代理加密算法')
    update_custom_route_parser.set_defaults(func=cmd_update_custom_route)

    delete_custom_route_parser = subparsers.add_parser('delete-custom-route', help='删除自定义路由')
    delete_custom_route_parser.add_argument('product_id', help='产品 ID')
    delete_custom_route_parser.add_argument('--custom-route-id', required=True, help='规则 ID')
    delete_custom_route_parser.set_defaults(func=cmd_delete_custom_route)
