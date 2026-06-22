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

"""实例属性模块。"""
from . import cli_common as cli


def cmd_get_phone_template(args):
    result = cli.get_client().get_phone_template(phone_template_id=args.phone_template_id, product_id=args.product_id)
    cli.print_result(result)


def cmd_list_phone_templates(args):
    result = cli.get_client().list_phone_templates(
        max_results=args.max_results,
        next_token=args.next_token,
        product_id=args.product_id,
        PhoneTemplateName=args.phone_template_name,
        Status=args.status,
        PhoneTemplateId=args.phone_template_id,
        TagId=args.tag_id,
        AospVersion=args.aosp_version,
    )
    cli.print_result(result)


def cmd_add_phone_template(args):
    result = cli.get_client().add_phone_template(
        phone_template_name=args.phone_template_name,
        aosp_version=args.aosp_version,
        status=args.status,
        overlay_property=cli.parse_json_option(args.overlay_property, '--overlay-property', list),
        overlay_persist_property=cli.parse_json_option(args.overlay_persist_property, '--overlay-persist-property', list),
        overlay_settings=cli.parse_json_option(args.overlay_settings, '--overlay-settings', list),
    )
    cli.print_result(result)


def cmd_update_phone_template(args):
    result = cli.get_client().update_phone_template(
        phone_template_id=args.phone_template_id,
        phone_template_name=args.phone_template_name,
        status=args.status,
    )
    cli.print_result(result)


def cmd_remove_phone_template(args):
    result = cli.get_client().remove_phone_template(
        phone_template_id=args.phone_template_id,
    )
    cli.print_result(result)


def cmd_get_pod_property(args):
    result = cli.get_client().get_pod_property(pod_id=args.pod_id, product_id=args.product_id)
    cli.print_result(result)


def cmd_update_pod_property(args):
    result = cli.get_client().update_pod_property(
        product_id=args.product_id,
        pod_id=args.pod_id,
        pod_id_list=cli.parse_csv_values(args.pod_id_list),
        pod_settings=cli.parse_json_option(args.pod_settings, '--pod-settings', list),
        pod_properties=cli.parse_json_option(args.pod_properties, '--pod-properties', list),
        pod_persist_properties=cli.parse_json_option(args.pod_persist_properties, '--pod-persist-properties', list),
        phone_template_id=args.phone_template_id,
    )
    cli.print_result(result)


def register(subparsers):

    get_phone_template_parser = subparsers.add_parser('get-phone-template', help='查询机型库详情')
    get_phone_template_parser.add_argument('product_id', help='产品 ID')
    get_phone_template_parser.add_argument('phone_template_id', help='机型库 ID')
    get_phone_template_parser.set_defaults(func=cmd_get_phone_template)

    list_templates_parser = subparsers.add_parser('list-phone-templates', help='查询机型库列表')
    list_templates_parser.add_argument('product_id', help='产品 ID')
    list_templates_parser.add_argument('--phone-template-name', help='机型库名称')
    list_templates_parser.add_argument('--status', type=int, help='状态：1=已发布，2=测试中，3=已废弃')
    list_templates_parser.add_argument('--phone-template-id', help='机型库 ID')
    list_templates_parser.add_argument('--tag-id', help='标签 ID')
    list_templates_parser.add_argument('--aosp-version', help='AOSP 版本')
    list_templates_parser.add_argument('--max-results', type=int, default=10, help='每页数量')
    list_templates_parser.add_argument('--next-token', help='分页游标')
    list_templates_parser.set_defaults(func=cmd_list_phone_templates)

    add_phone_template_parser = subparsers.add_parser('add-phone-template', help='添加机型库')
    add_phone_template_parser.add_argument('--phone-template-name', required=True, help='机型库名称')
    add_phone_template_parser.add_argument('--aosp-version', required=True, help='AOSP 版本')
    add_phone_template_parser.add_argument('--status', type=int, required=True, help='状态：1=已发布，2=测试中，3=已废弃')
    add_phone_template_parser.add_argument('--overlay-property', help='非持久化系统属性 JSON 数组')
    add_phone_template_parser.add_argument('--overlay-persist-property', help='持久化系统属性 JSON 数组')
    add_phone_template_parser.add_argument('--overlay-settings', help='Settings 属性 JSON 数组')
    add_phone_template_parser.set_defaults(func=cmd_add_phone_template)

    update_phone_template_parser = subparsers.add_parser('update-phone-template', help='更新机型库')
    update_phone_template_parser.add_argument('--phone-template-id', required=True, help='机型库 ID')
    update_phone_template_parser.add_argument('--phone-template-name', help='机型库名称')
    update_phone_template_parser.add_argument('--status', type=int, help='状态：1=已发布，2=测试中，3=已废弃')
    update_phone_template_parser.set_defaults(func=cmd_update_phone_template)

    remove_phone_template_parser = subparsers.add_parser('remove-phone-template', help='删除机型库')
    remove_phone_template_parser.add_argument('--phone-template-id', required=True, help='机型库 ID')
    remove_phone_template_parser.set_defaults(func=cmd_remove_phone_template)

    get_pod_property_parser = subparsers.add_parser('get-pod-property', help='查询实例属性列表')
    get_pod_property_parser.add_argument('product_id', help='产品 ID')
    get_pod_property_parser.add_argument('pod_id', help='实例 ID')
    get_pod_property_parser.set_defaults(func=cmd_get_pod_property)

    update_pod_property_parser = subparsers.add_parser('update-pod-property', help='更新实例属性')
    update_pod_property_parser.add_argument('product_id', help='产品 ID')
    update_pod_property_parser.add_argument('--pod-id', help='单个实例 ID')
    update_pod_property_parser.add_argument('--pod-id-list', help='实例 ID 列表，逗号分隔')
    update_pod_property_parser.add_argument('--phone-template-id', help='机型库 ID')
    update_pod_property_parser.add_argument('--pod-settings', help='PodSettings JSON 数组')
    update_pod_property_parser.add_argument('--pod-properties', help='PodProperties JSON 数组')
    update_pod_property_parser.add_argument('--pod-persist-properties', help='PodPersistProperties JSON 数组')
    update_pod_property_parser.set_defaults(func=cmd_update_pod_property)
