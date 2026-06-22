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

"""镜像模块。"""
from . import cli_common as cli


def cmd_list_image_resources(args):
    cli.print_result(cli.get_client().list_image_resources(
        offset=args.offset,
        count=args.count,
        product_id=args.product_id,
        ImageIdList=args.image_id_list,
    ))


def cmd_get_image_preheating(args):
    cli.print_result(cli.get_client().get_image_preheating(
        image_id_list=cli.parse_csv_values(args.image_id_list),
        product_id=args.product_id,
        dc_id=args.dc_id,
    ))


def cmd_list_aosp_images(args):
    image_id_list = cli.parse_csv(args.image_id_list) if args.image_id_list else None
    cli.print_result(cli.get_client().list_aosp_images(
        product_id=args.product_id,
        image_id_list=image_id_list,
        image_name=args.image_name,
        aosp_version=args.aosp_version,
        is_public=args.is_public,
        image_status=args.image_status,
        expand_scope=args.expand_scope,
        max_results=args.max_results,
        next_token=args.next_token,
        PlatformType=args.platform_type,
    ))


def cmd_delete_aosp_image(args):
    cli.print_result(cli.get_client().delete_aosp_image(
        image_id_list=cli.parse_csv_values(args.image_id_list),
        product_id=args.product_id,
    ))


def cmd_update_aosp_image(args):
    cli.print_result(cli.get_client().update_aosp_image(
        image_id=args.image_id,
        product_id=args.product_id,
        image_name=args.image_name,
        image_annotation=args.image_annotation,
    ))


def cmd_create_image_one_step(args):
    cli.print_result(cli.get_client().create_image_one_step(
        image_id=args.image_id,
        product_id=args.product_id,
        image_name=args.image_name,
        image_annotation=args.image_annotation,
        file_url=args.file_url,
    ))


def cmd_build_aosp_image(args):
    cli.print_result(cli.get_client().build_aosp_image(
        product_id=args.product_id,
        image_name=args.image_name,
        image_annotation=args.image_annotation,
        image_file_format=args.image_file_format,
        system_url=args.system_url,
        vendor_url=args.vendor_url,
    ))


def register(subparsers):

    list_image_resources_parser = subparsers.add_parser('list-image-resources', help='查询镜像分布')
    list_image_resources_parser.add_argument('product_id', help='产品 ID')
    list_image_resources_parser.add_argument('--image-id-list', help='镜像 ID 列表，逗号分隔')
    list_image_resources_parser.add_argument('--offset', type=int, default=0, help='查询起始位置')
    list_image_resources_parser.add_argument('--count', type=int, default=10, help='返回数量')
    list_image_resources_parser.set_defaults(func=cmd_list_image_resources)

    get_image_preheating_parser = subparsers.add_parser('get-image-preheating', help='查询镜像预热信息')
    get_image_preheating_parser.add_argument('product_id', help='产品 ID')
    get_image_preheating_parser.add_argument('image_id_list', help='镜像 ID 列表，逗号分隔')
    get_image_preheating_parser.add_argument('--dc-id', help='机房 ID')
    get_image_preheating_parser.set_defaults(func=cmd_get_image_preheating)

    list_aosp_images_parser = subparsers.add_parser('list-aosp-images', help='查询 AOSP 镜像列表（公共镜像使用 --is-public）')
    list_aosp_images_parser.add_argument('product_id', help='产品 ID')
    list_aosp_images_parser.add_argument('--image-id-list', help='镜像 ID 列表，逗号分隔')
    list_aosp_images_parser.add_argument('--image-name', help='镜像名称')
    list_aosp_images_parser.add_argument('--aosp-version', choices=['10', '11', '12', '13'], help='AOSP 版本')
    list_aosp_images_parser.add_argument('--is-public', action='store_true', help='查询公共镜像；不传则查询自定义镜像')
    list_aosp_images_parser.add_argument('--image-status', type=int, help='镜像状态：1=导入/待构建，2=构建中，11=构建完成，-1=构建失败')
    list_aosp_images_parser.add_argument('--expand-scope', action='store_true', help='查询公共镜像时包含未发布镜像，需精确传 ImageIdList')
    list_aosp_images_parser.add_argument('--platform-type', choices=['g2', 'g3'], help='芯片类型')
    list_aosp_images_parser.add_argument('--max-results', type=int, default=10, help='分页大小，0-100')
    list_aosp_images_parser.add_argument('--next-token', help='分页游标')
    list_aosp_images_parser.set_defaults(func=cmd_list_aosp_images)

    delete_aosp_image_parser = subparsers.add_parser('delete-aosp-image', help='删除 AOSP 镜像')
    delete_aosp_image_parser.add_argument('product_id', help='产品 ID')
    delete_aosp_image_parser.add_argument('--image-id-list', required=True, help='镜像 ID 列表，逗号分隔')
    delete_aosp_image_parser.set_defaults(func=cmd_delete_aosp_image)

    update_aosp_image_parser = subparsers.add_parser('update-aosp-image', help='更新 AOSP 镜像')
    update_aosp_image_parser.add_argument('product_id', help='产品 ID')
    update_aosp_image_parser.add_argument('--image-id', required=True, help='镜像 ID')
    update_aosp_image_parser.add_argument('--image-name', help='镜像名称')
    update_aosp_image_parser.add_argument('--image-annotation', help='镜像备注')
    update_aosp_image_parser.set_defaults(func=cmd_update_aosp_image)

    create_image_one_step_parser = subparsers.add_parser('create-image-one-step', help='镜像内置应用/文件')
    create_image_one_step_parser.add_argument('product_id', help='产品 ID')
    create_image_one_step_parser.add_argument('--image-id', required=True, help='基线镜像 ID')
    create_image_one_step_parser.add_argument('--image-name', help='新镜像名称')
    create_image_one_step_parser.add_argument('--image-annotation', help='镜像备注')
    create_image_one_step_parser.add_argument('--file-url', help='内置应用或文件下载地址')
    create_image_one_step_parser.set_defaults(func=cmd_create_image_one_step)

    build_aosp_image_parser = subparsers.add_parser('build-aosp-image', help='构建 AOSP 镜像')
    build_aosp_image_parser.add_argument('product_id', help='产品 ID')
    build_aosp_image_parser.add_argument('--image-name', help='镜像名称')
    build_aosp_image_parser.add_argument('--image-annotation', help='镜像备注')
    build_aosp_image_parser.add_argument('--image-file-format', choices=['volc_tos', 'url'], help='镜像文件格式')
    build_aosp_image_parser.add_argument('--system-url', help='system 镜像 URL；复杂 TOS 参数需补充专用命令支持')
    build_aosp_image_parser.add_argument('--vendor-url', help='vendor 镜像 URL；复杂 TOS 参数需补充专用命令支持')
    build_aosp_image_parser.set_defaults(func=cmd_build_aosp_image)
