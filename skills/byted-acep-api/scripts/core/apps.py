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

"""应用模块。"""
from . import cli_common as cli


def parse_app_list(value: str) -> list[dict]:
    result = []
    for item in cli.parse_csv_values(value):
        app_id, sep, version_id = item.partition(':')
        if not app_id or not sep or not version_id:
            raise ValueError(f'Invalid --app-list item: {item!r}; expected AppId:VersionId')
        result.append({'AppId': app_id, 'VersionId': version_id})
    return result


def cmd_install_app(args):
    cli.print_result(cli.get_client().install_app(
        pod_id=args.pod_id,
        app_id=args.app_id,
        version_id=args.version_id,
        **cli.request_kwargs(args),
    ))


def cmd_launch_app(args):
    cli.print_result(cli.get_client().launch_app(
        pod_id=args.pod_id,
        package_name=args.package_name,
        **cli.request_kwargs(args),
    ))


def cmd_close_app(args):
    cli.print_result(cli.get_client().close_app(
        pod_id=args.pod_id,
        package_name=args.package_name,
        **cli.request_kwargs(args),
    ))


def cmd_uninstall_app(args):
    cli.print_result(cli.get_client().uninstall_app(
        pod_id=args.pod_id,
        app_id=args.app_id,
        **cli.request_kwargs(args),
    ))


def cmd_auto_install_app(args):
    kwargs = cli.request_kwargs(args)
    for field in ['install_type', 'download_url', 'package_name', 'version_code', 'image_id', 'absolute_path']:
        value = getattr(args, field, None)
        if value is not None:
            kwargs[field] = value
    if args.is_preinstall is not None:
        kwargs['IsPreinstall'] = args.is_preinstall
    cli.print_result(cli.get_client().auto_install_app(
        pod_id_list=cli.parse_csv_values(args.pod_id_list),
        **kwargs,
    ))


def cmd_get_pod_app_list(args):
    cli.print_result(cli.get_client().get_pod_app_list(args.pod_id, **cli.request_kwargs(args)))


def cmd_detail_app(args):
    cli.print_result(cli.get_client().detail_app(app_id=args.app_id, product_id=args.product_id))


def cmd_list_apps(args):
    cli.print_result(cli.get_client().list_apps(
        max_results=args.max_results,
        next_token=args.next_token,
        product_id=args.product_id,
        AppId=args.app_id,
        AppName=args.app_name,
        AppType=args.app_type,
        PackageNameList=cli.parse_csv_values(args.package_name_list),
    ))


def cmd_list_app_version_deploys(args):
    cli.print_result(cli.get_client().list_app_version_deploys(
        app_id=args.app_id,
        product_id=args.product_id,
        VersionId=args.version_id,
    ))


def cmd_get_app_crash_log(args):
    cli.print_result(cli.get_client().get_app_crash_log(
        pod_id_list=args.pod_id_list,
        start_time=args.start_time,
        end_time=args.end_time,
        product_id=args.product_id,
    ))


def cmd_install_apps(args):
    cli.print_result(cli.get_client().install_apps(
        pod_id=args.pod_id,
        app_list=parse_app_list(args.app_list),
        product_id=args.product_id,
        install_type=args.install_type,
        is_preinstall=args.is_preinstall,
    ))


def cmd_upload_app(args):
    cli.print_result(cli.get_client().upload_app(
        app_type=args.app_type,
        download_url=args.download_url,
        product_id=args.product_id,
        app_id=args.app_id,
        app_name=args.app_name,
        rotation=args.rotation,
        app_desc=args.app_desc,
        parse_flag=args.parse_flag,
        app_mode=args.app_mode,
    ))


def cmd_update_app(args):
    cli.print_result(cli.get_client().update_app(
        app_id=args.app_id,
        product_id=args.product_id,
        app_name=args.app_name,
        rotation=args.rotation,
        icon_url=args.icon_url,
        app_desc=args.app_desc,
        app_mode=args.app_mode,
    ))


def cmd_delete_app(args):
    cli.print_result(cli.get_client().delete_app(app_id=args.app_id, product_id=args.product_id))


def cmd_delete_app_version(args):
    cli.print_result(cli.get_client().delete_app_version(version_id=args.version_id, product_id=args.product_id))


def cmd_launch_apps(args):
    cli.print_result(cli.get_client().launch_apps(
        pod_id=args.pod_id,
        package_name_list=cli.parse_csv_values(args.package_name_list),
        product_id=args.product_id,
    ))


def register(subparsers):

    install_app_parser = subparsers.add_parser('install-app', help='安装应用')
    install_app_parser.add_argument('product_id', help='产品 ID')
    install_app_parser.add_argument('pod_id', help='实例 ID')
    install_app_parser.add_argument('app_id', help='应用 ID')
    install_app_parser.add_argument('version_id', help='应用版本 ID')
    install_app_parser.set_defaults(func=cmd_install_app)

    launch_app_parser = subparsers.add_parser('launch-app', help='启动应用')
    launch_app_parser.add_argument('product_id', help='产品 ID')
    launch_app_parser.add_argument('pod_id', help='实例 ID')
    launch_app_parser.add_argument('package_name', help='应用包名')
    launch_app_parser.set_defaults(func=cmd_launch_app)

    close_app_parser = subparsers.add_parser('close-app', help='关闭应用')
    close_app_parser.add_argument('product_id', help='产品 ID')
    close_app_parser.add_argument('pod_id', help='实例 ID')
    close_app_parser.add_argument('package_name', help='应用包名')
    close_app_parser.set_defaults(func=cmd_close_app)

    uninstall_app_parser = subparsers.add_parser('uninstall-app', help='卸载应用')
    uninstall_app_parser.add_argument('product_id', help='产品 ID')
    uninstall_app_parser.add_argument('pod_id', help='实例 ID')
    uninstall_app_parser.add_argument('app_id', help='应用 ID')
    uninstall_app_parser.set_defaults(func=cmd_uninstall_app)

    auto_install_app_parser = subparsers.add_parser('auto-install-app', help='自动下载安装应用')
    auto_install_app_parser.add_argument('product_id', help='产品 ID')
    auto_install_app_parser.add_argument('--pod-id-list', required=True, help='实例 ID 列表，逗号分隔')
    auto_install_app_parser.add_argument('--install-type', type=int, choices=[0, 1], help='安装方式：0=机身存储独立安装，1=应用镜像安装')
    auto_install_app_parser.add_argument('--download-url', help='应用下载 URL')
    auto_install_app_parser.add_argument('--package-name', help='应用包名')
    auto_install_app_parser.add_argument('--version-code', type=int, help='应用版本号')
    auto_install_app_parser.add_argument('--image-id', help='镜像包 ID')
    auto_install_app_parser.add_argument('--absolute-path', help='应用绝对路径或应用镜像根目录')
    auto_install_app_parser.add_argument('--is-preinstall', action='store_true', default=None, help='标记为预装应用')
    auto_install_app_parser.set_defaults(func=cmd_auto_install_app)

    get_app_list_parser = subparsers.add_parser('get-pod-app-list', help='获取实例应用列表')
    get_app_list_parser.add_argument('product_id', help='产品 ID')
    get_app_list_parser.add_argument('pod_id', help='实例 ID')
    get_app_list_parser.set_defaults(func=cmd_get_pod_app_list)

    detail_app_parser = subparsers.add_parser('detail-app', help='查询应用信息')
    detail_app_parser.add_argument('product_id', help='产品 ID')
    detail_app_parser.add_argument('app_id', help='应用 ID')
    detail_app_parser.set_defaults(func=cmd_detail_app)

    list_apps_parser = subparsers.add_parser('list-apps', help='查询应用信息列表')
    list_apps_parser.add_argument('product_id', help='产品 ID')
    list_apps_parser.add_argument('--app-id', help='应用 ID')
    list_apps_parser.add_argument('--app-name', help='应用名称')
    list_apps_parser.add_argument('--app-type', type=int, help='应用类型')
    list_apps_parser.add_argument('--package-name-list', help='包名列表，逗号分隔')
    list_apps_parser.add_argument('--max-results', type=int, default=10, help='每页数量')
    list_apps_parser.add_argument('--next-token', help='分页游标')
    list_apps_parser.set_defaults(func=cmd_list_apps)

    list_app_version_deploys_parser = subparsers.add_parser('list-app-version-deploys', help='查询应用版本部署信息列表')
    list_app_version_deploys_parser.add_argument('product_id', help='产品 ID')
    list_app_version_deploys_parser.add_argument('app_id', help='应用 ID')
    list_app_version_deploys_parser.add_argument('--version-id', help='应用版本 ID')
    list_app_version_deploys_parser.set_defaults(func=cmd_list_app_version_deploys)

    get_app_crash_log_parser = subparsers.add_parser('get-app-crash-log', help='查询应用崩溃日志')
    get_app_crash_log_parser.add_argument('product_id', help='产品 ID')
    get_app_crash_log_parser.add_argument('pod_id_list', help='实例 ID 列表，逗号分隔')
    get_app_crash_log_parser.add_argument('--start-time', type=int, required=True, help='开始时间 Unix 秒')
    get_app_crash_log_parser.add_argument('--end-time', type=int, required=True, help='结束时间 Unix 秒')
    get_app_crash_log_parser.set_defaults(func=cmd_get_app_crash_log)

    install_apps_parser = subparsers.add_parser('install-apps', help='批量安装应用')
    install_apps_parser.add_argument('product_id', help='产品 ID')
    install_apps_parser.add_argument('--pod-id', required=True, help='实例 ID')
    install_apps_parser.add_argument('--app-list', required=True, help='应用列表；格式 AppId:VersionId,AppId2:VersionId2')
    install_apps_parser.add_argument('--install-type', type=int, help='安装模式')
    install_apps_parser.add_argument('--is-preinstall', action='store_true', help='标记为预装应用')
    install_apps_parser.set_defaults(func=cmd_install_apps)

    upload_app_parser = subparsers.add_parser('upload-app', help='上传应用')
    upload_app_parser.add_argument('product_id', help='产品 ID')
    upload_app_parser.add_argument('--app-type', type=int, required=True, help='应用类型')
    upload_app_parser.add_argument('--download-url', required=True, help='应用文件下载 URL')
    upload_app_parser.add_argument('--app-id', help='应用 ID')
    upload_app_parser.add_argument('--app-name', help='应用名称')
    upload_app_parser.add_argument('--rotation', type=int, help='方向：0=竖屏，270=横屏')
    upload_app_parser.add_argument('--app-desc', help='应用描述')
    upload_app_parser.add_argument('--parse-flag', type=int, help='解析方式')
    upload_app_parser.add_argument('--app-mode', choices=['Public', 'Private'], help='应用范围')
    upload_app_parser.set_defaults(func=cmd_upload_app)

    update_app_parser = subparsers.add_parser('update-app', help='修改应用')
    update_app_parser.add_argument('product_id', help='产品 ID')
    update_app_parser.add_argument('--app-id', required=True, help='应用 ID')
    update_app_parser.add_argument('--app-name', help='应用名称')
    update_app_parser.add_argument('--rotation', type=int, help='方向')
    update_app_parser.add_argument('--icon-url', help='图标 URL')
    update_app_parser.add_argument('--app-desc', help='应用描述')
    update_app_parser.add_argument('--app-mode', choices=['Public'], help='应用范围')
    update_app_parser.set_defaults(func=cmd_update_app)

    delete_app_parser = subparsers.add_parser('delete-app', help='删除应用')
    delete_app_parser.add_argument('product_id', help='产品 ID')
    delete_app_parser.add_argument('--app-id', required=True, help='应用 ID')
    delete_app_parser.set_defaults(func=cmd_delete_app)

    delete_app_version_parser = subparsers.add_parser('delete-app-version', help='删除应用版本')
    delete_app_version_parser.add_argument('product_id', help='产品 ID')
    delete_app_version_parser.add_argument('--version-id', required=True, help='应用版本 ID')
    delete_app_version_parser.set_defaults(func=cmd_delete_app_version)

    launch_apps_parser = subparsers.add_parser('launch-apps', help='批量启动应用')
    launch_apps_parser.add_argument('product_id', help='产品 ID')
    launch_apps_parser.add_argument('--pod-id', required=True, help='实例 ID')
    launch_apps_parser.add_argument('--package-name-list', required=True, help='包名列表，逗号分隔')
    launch_apps_parser.set_defaults(func=cmd_launch_apps)
