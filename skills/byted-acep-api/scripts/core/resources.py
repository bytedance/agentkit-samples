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

"""资源模块。"""
from . import cli_common as cli


def cmd_list_instance_configuration_specs(args):
    cli.print_result(cli.get_client().list_instance_configuration_specs(product_id=args.product_id))


def cmd_list_pod_resources(args):
    cli.print_result(cli.get_client().list_pod_resources(
        offset=args.offset,
        count=args.count,
        product_id=args.product_id,
        ConfigurationCode=args.configuration_code,
        Dc=args.dc,
        ImageId=args.image_id,
    ))


def cmd_get_product_resource(args):
    cli.print_result(cli.get_client().get_product_resource(**cli.request_kwargs(args)))


def cmd_update_product_resource(args):
    cli.print_result(cli.get_client().update_product_resource(
        apply_data_size=args.apply_data_size,
        product_id=args.product_id,
        volc_region=args.volc_region,
    ))


def cmd_list_pod_resource_set(args):
    cli.print_result(cli.get_client().list_pod_resource_set(
        offset=args.offset if args.offset is not None else 0,
        count=args.count if args.count is not None else 10,
        product_id=args.product_id,
        ResourceSetId=args.resource_set_id,
        ConfigurationCode=args.configuration_code,
        Dc=args.dc,
        VolcRegion=args.volc_region,
    ))

def cmd_list_configurations(args):
    cli.print_result(cli.get_client().list_configurations(
        offset=args.offset,
        count=args.count,
        product_id=args.product_id,
        ResourceClass=args.resource_class,
        ConfigurationCode=args.configuration_code,
    ))


def cmd_subscribe_resource_auto(args):
    kwargs = cli.request_kwargs(args)
    for field in ['configuration_code', 'server_type_code', 'dc', 'apply_num', 'resource_type', 'term', 'period', 'pay_type', 'charge_type', 'region', 'volc_region', 'round_id', 'auto_create_pod', 'image_id', 'display_layout_id']:
        value = getattr(args, field, None)
        if value is not None:
            parts = field.split('_')
            kwargs[parts[0].capitalize() + ''.join(part.capitalize() for part in parts[1:])] = value
    cli.print_result(cli.get_client().subscribe_resource_auto(**kwargs))


def cmd_renew_resource_auto(args):
    kwargs = cli.request_kwargs(args)
    for field in ['resource_set_id', 'host_id', 'term', 'period', 'round_id']:
        value = getattr(args, field, None)
        if value is not None:
            parts = field.split('_')
            kwargs[parts[0].capitalize() + ''.join(part.capitalize() for part in parts[1:])] = value
    cli.print_result(cli.get_client().renew_resource_auto(**kwargs))


def cmd_unsubscribe_host_resource(args):
    cli.print_result(cli.get_client().unsubscribe_host_resource(
        host_id_list=cli.parse_csv(args.host_id_list),
        force=args.force,
        **cli.request_kwargs(args),
    ))


def register(subparsers):
    list_instance_configuration_specs_parser = subparsers.add_parser('list-instance-configuration-specs', help='查询实例规格列表')
    list_instance_configuration_specs_parser.add_argument('product_id', help='产品 ID')
    list_instance_configuration_specs_parser.set_defaults(func=cmd_list_instance_configuration_specs)

    subscribe_resource_parser = subparsers.add_parser('subscribe-resource-auto', help='自动下单订购资源')
    subscribe_resource_parser.add_argument('product_id', help='产品 ID')
    subscribe_resource_parser.add_argument('--configuration-code', help='实例规格 ID；本地存储业务必填')
    subscribe_resource_parser.add_argument('--server-type-code', help='云机规格 ID')
    subscribe_resource_parser.add_argument('--dc', help='机房 ID')
    subscribe_resource_parser.add_argument('--apply-num', type=int, help='订购实例数量')
    subscribe_resource_parser.add_argument('--resource-type', type=int, required=True, choices=[100, 200], help='资源类型（必填）：云盘 100，本地 200')
    subscribe_resource_parser.add_argument('--term', type=int, help='订购周期数')
    subscribe_resource_parser.add_argument('--period', help='订购周期单位')
    subscribe_resource_parser.add_argument('--pay-type', type=int, help='付费类型')
    subscribe_resource_parser.add_argument('--charge-type', help='计费类型')
    subscribe_resource_parser.add_argument('--region', help='资源地域')
    subscribe_resource_parser.add_argument('--volc-region', help='火山地域标识')
    subscribe_resource_parser.add_argument('--round-id', help='幂等请求 ID')
    subscribe_resource_parser.add_argument('--auto-create-pod', type=int, choices=[0, 1], help='是否自动创建实例')
    subscribe_resource_parser.add_argument('--image-id', help='自动创建实例使用的镜像 ID')
    subscribe_resource_parser.add_argument('--display-layout-id', help='自动创建实例使用的屏幕布局 ID')
    subscribe_resource_parser.set_defaults(func=cmd_subscribe_resource_auto)

    renew_resource_parser = subparsers.add_parser('renew-resource-auto', help='自动下单续订资源')
    renew_resource_parser.add_argument('product_id', help='产品 ID')
    renew_resource_parser.add_argument('--resource-set-id', help='资源组 ID')
    renew_resource_parser.add_argument('--host-id', help='云机 ID')
    renew_resource_parser.add_argument('--term', type=int, help='续费周期数')
    renew_resource_parser.add_argument('--period', help='续费周期单位')
    renew_resource_parser.add_argument('--round-id', help='幂等请求 ID')
    renew_resource_parser.set_defaults(func=cmd_renew_resource_auto)

    unsubscribe_host_parser = subparsers.add_parser('unsubscribe-host-resource', help='退订后付费云机资源')
    unsubscribe_host_parser.add_argument('product_id', help='产品 ID')
    unsubscribe_host_parser.add_argument('host_id_list', help='云机 ID 列表，逗号分隔')
    unsubscribe_host_parser.add_argument('--force', action='store_true', help='强制退订')
    unsubscribe_host_parser.set_defaults(func=cmd_unsubscribe_host_resource)

    list_pod_resources_parser = subparsers.add_parser('list-pod-resources', help='查询实例资源列表')
    list_pod_resources_parser.add_argument('product_id', help='产品 ID')
    list_pod_resources_parser.add_argument('--configuration-code', help='实例规格 ID')
    list_pod_resources_parser.add_argument('--dc', help='机房 ID')
    list_pod_resources_parser.add_argument('--image-id', help='镜像 ID')
    list_pod_resources_parser.add_argument('--offset', type=int, default=0, help='查询起始位置')
    list_pod_resources_parser.add_argument('--count', type=int, default=10, help='返回数量')
    list_pod_resources_parser.set_defaults(func=cmd_list_pod_resources)

    get_product_resource_parser = subparsers.add_parser('get-product-resource', help='查询业务存储资源')
    get_product_resource_parser.add_argument('product_id', help='产品 ID')
    get_product_resource_parser.set_defaults(func=cmd_get_product_resource)

    list_configs_parser = subparsers.add_parser('list-configurations', help='查询套餐列表')
    list_configs_parser.add_argument('product_id', help='产品 ID')
    list_configs_parser.add_argument('--resource-class', type=int, help='资源类型：1=计算资源，2=存储资源，3=带宽资源')
    list_configs_parser.add_argument('--configuration-code', help='套餐规格 ID')
    list_configs_parser.add_argument('--offset', type=int, default=0, help='查询起始位置')
    list_configs_parser.add_argument('--count', type=int, default=10, help='返回数量')
    list_configs_parser.set_defaults(func=cmd_list_configurations)

    update_product_resource_parser = subparsers.add_parser('update-product-resource', help='更新业务存储资源')
    update_product_resource_parser.add_argument('product_id', help='产品 ID')
    update_product_resource_parser.add_argument('--apply-data-size', type=int, required=True, help='订购存储资源总容量 GB')
    update_product_resource_parser.add_argument('--volc-region', help='物理地域')
    update_product_resource_parser.set_defaults(func=cmd_update_product_resource)

    list_pod_resource_set_parser = subparsers.add_parser('list-pod-resource-set', help='查询实例资源组列表')
    list_pod_resource_set_parser.add_argument('product_id', help='产品 ID')
    list_pod_resource_set_parser.add_argument('--resource-set-id', help='资源组 ID')
    list_pod_resource_set_parser.add_argument('--configuration-code', help='实例规格 ID')
    list_pod_resource_set_parser.add_argument('--dc', help='机房 ID')
    list_pod_resource_set_parser.add_argument('--volc-region', help='物理地域')
    list_pod_resource_set_parser.add_argument('--offset', type=int, default=0, help='起始位置')
    list_pod_resource_set_parser.add_argument('--count', type=int, default=10, help='返回数量')
    list_pod_resource_set_parser.set_defaults(func=cmd_list_pod_resource_set)
