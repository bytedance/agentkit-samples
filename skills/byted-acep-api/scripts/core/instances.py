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

"""实例模块。"""
from . import cli_common as cli


def cmd_create_pod(args):
    kwargs = {}
    for field, api_field in {
        'data_size': 'DataSize',
        'display_layout_id': 'DisplayLayoutId',
        'tag_id': 'TagId',
        'up_bandwidth_limit': 'UpBandwidthLimit',
        'down_bandwidth_limit': 'DownBandwidthLimit',
        'custom_route_id': 'CustomRouteId',
        'dns_id': 'DNSId',
        'ip_white_list': 'IPWhiteList',
        'resource_type': 'ResourceType',
        'host_id': 'HostId',
        'use_phone_template': 'UsePhoneTemplate',
        'phone_template_id': 'PhoneTemplateId',
        'is_selinux_on': 'IsSelinuxOn',
        'image_id': 'ImageId',
    }.items():
        value = getattr(args, field, None)
        if value is not None:
            kwargs[api_field] = value
    if getattr(args, 'start', False):
        kwargs['Start'] = True
    if getattr(args, 'port_mapping_rule_id_list', None):
        kwargs['PortMappingRuleIdList'] = cli.parse_csv_values(args.port_mapping_rule_id_list)
    result = cli.get_client().create_pod(
        name=args.name,
        template_id=args.template_id,
        configuration_code=args.configuration_code,
        count=args.count,
        product_id=args.product_id,
        dc_id=args.dc_id,
        **kwargs,
    )
    cli.print_result(result)


def cmd_list_pods(args):
    kwargs = cli.request_kwargs(args)
    for key, value in {
        'PodIdList': cli.parse_csv_values(args.pod_id_list),
        'ConfigurationCodeList': cli.parse_csv_values(args.configuration_code_list),
        'RegionList': cli.parse_csv_values(args.region_list),
        'DcList': cli.parse_csv_values(args.dc_list),
        'TagIdList': cli.parse_csv_values(args.tag_id_list),
        'OnlineList': cli.parse_csv_values(args.online_list, int),
        'StreamStatusList': cli.parse_csv_values(args.stream_status_list, int),
        'AuthorityStatus': args.authority_status,
        'ZoneId': args.zone_id,
        'ServerTypeCode': args.server_type_code,
        'HostId': args.host_id,
        'DNSId': args.dns_id,
        'PodName': args.pod_name,
        'ArchiveStatus': args.archive_status,
    }.items():
        if value is not None:
            kwargs[key] = value
    for key, value in {
        'page_size': args.page_size,
        'page_number': args.page_number,
        'max_results': args.max_results,
        'next_token': args.next_token,
    }.items():
        if value is not None:
            kwargs[key] = value
    cli.print_result(cli.get_client().list_pods(**kwargs))


def cmd_detail_pod(args):
    cli.print_result(cli.get_client().detail_pod(
        pod_id=args.pod_id,
        product_id=args.product_id,
    ))


def cmd_delete_pod(args):
    kwargs = cli.request_kwargs(args)
    if getattr(args, "force_destroy", False):
        kwargs["ForceDestroyFlag"] = True
    cli.print_result(cli.get_client().delete_pod(args.pod_id, **kwargs))


def cmd_update_pod(args):
    kwargs = {}
    for field, api_field in {
        'pod_name': 'PodName',
        'data_size': 'DataSize',
        'configuration_code': 'ConfigurationCode',
        'display_layout_id': 'DisplayLayoutId',
        'up_bandwidth_limit': 'UpBandwidthLimit',
        'down_bandwidth_limit': 'DownBandwidthLimit',
        'custom_route_id': 'CustomRouteId',
        'dns_id': 'DNSId',
        'ip_white_list': 'IPWhiteList',
        'is_selinux_on': 'IsSelinuxOn',
    }.items():
        value = getattr(args, field, None)
        if value is not None:
            kwargs[api_field] = value
    if getattr(args, 'port_mapping_rule_id_list', None):
        kwargs['PortMappingRuleIdList'] = cli.parse_csv_values(args.port_mapping_rule_id_list)
    result = cli.get_client().update_pod(
        args.pod_id,
        product_id=args.product_id,
        image_id=args.image_id,
        force=args.force,
        **kwargs,
    )
    cli.print_result(result)


def _simple_pod_command(method_name, pod_id, args):
    cli.print_result(getattr(cli.get_client(), method_name)(pod_id, **cli.request_kwargs(args)))


def cmd_power_on_pod(args):
    _simple_pod_command('power_on_pod', args.pod_id, args)


def cmd_power_off_pod(args):
    _simple_pod_command('power_off_pod', args.pod_id, args)


def cmd_reboot_pod(args):
    _simple_pod_command('reboot_pod', args.pod_id, args)


def cmd_reset_pod(args):
    _simple_pod_command('reset_pod', args.pod_id, args)


def cmd_get_pod_metric(args):
    cli.print_result(cli.get_client().get_pod_metric(pod_id=args.pod_id, product_id=args.product_id))


def cmd_set_proxy(args):
    cli.print_result(cli.get_client().set_proxy(
        pod_id_list=cli.parse_csv_values(args.pod_id_list),
        proxy_status=args.proxy_status,
        proxy_config=cli.parse_json_option(args.proxy_config, '--proxy-config', dict),
        product_id=args.product_id,
    ))


def cmd_get_proxy(args):
    cli.print_result(cli.get_client().get_proxy(
        pod_id_list=cli.parse_csv_values(args.pod_id_list),
        product_id=args.product_id,
    ))


def cmd_get_presigned_edge_url(args):
    cli.print_result(cli.get_client().get_presigned_edge_url(
        args.pod_id,
        api_type=args.api_type,
        api_payload=cli.parse_string_params(args.payload),
        api_path=args.api_path,
        ttl=args.ttl,
        timeout=args.timeout,
        single_use=args.single_use,
        product_id=args.product_id,
    ))


def cmd_pod_mute(args):
    cli.print_result(cli.get_client().pod_mute(
        pod_id=args.pod_id,
        mute=cli.parse_bool_flag(args.mute),
        display_list=cli.parse_csv_values(args.display_list),
        product_id=args.product_id,
    ))


def cmd_pod_adb(args):
    cli.print_result(cli.get_client().pod_adb(
        pod_id=args.pod_id,
        enable=cli.parse_bool_flag(args.enable),
        product_id=args.product_id,
    ))


def cmd_pod_stop(args):
    cli.print_result(cli.get_client().pod_stop(pod_id=args.pod_id, product_id=args.product_id))


def cmd_pod_data_delete(args):
    cli.print_result(cli.get_client().pod_data_delete(
        pod_id=args.pod_id,
        file_path_list=cli.parse_csv_values(args.file_path_list),
        package_list=cli.parse_csv_values(args.package_list),
        product_id=args.product_id,
    ))


def cmd_create_pod_one_step(args):
    result = cli.get_client().create_pod_one_step(
        configuration_code=args.configuration_code,
        dc=args.dc,
        app_list=cli.parse_app_list(args.app_list),
        product_id=args.product_id,
        pod_name=args.pod_name,
        image_id=args.image_id,
        data_size=args.data_size,
        display_layout_id=args.display_layout_id,
        overlay_settings=cli.parse_json_option(args.overlay_settings, '--overlay-settings', list),
        overlay_property=cli.parse_json_option(args.overlay_property, '--overlay-property', list),
        overlay_persist_property=cli.parse_json_option(args.overlay_persist_property, '--overlay-persist-property', list),
        tag_id=args.tag_id,
        up_bandwidth_limit=args.up_bandwidth_limit,
        down_bandwidth_limit=args.down_bandwidth_limit,
        custom_route_id=args.custom_route_id,
        dns_id=args.dns_id,
        port_mapping_rule_id_list=cli.parse_csv_values(args.port_mapping_rule_id_list),
        ip_white_list=args.ip_white_list,
        resource_type=args.resource_type,
        host_id=args.host_id,
        is_preinstall=cli.parse_bool_flag(args.is_preinstall) if args.is_preinstall is not None else None,
        use_phone_template=args.use_phone_template,
        phone_template_id=args.phone_template_id,
        is_selinux_on=cli.parse_bool_flag(args.is_selinux_on) if args.is_selinux_on is not None else None,
    )
    cli.print_result(result)


def cmd_update_pod_resource_apply_num(args):
    result = cli.get_client().update_pod_resource_apply_num(
        apply_num=args.apply_num,
        product_id=args.product_id,
        resource_set_id=args.resource_set_id,
        configuration_code=args.configuration_code,
        dc=args.dc,
    )
    cli.print_result(result)


def cmd_backup_pod(args):
    cli.print_result(cli.get_client().backup_pod(pod_id_list=cli.parse_csv_values(args.pod_id_list), product_id=args.product_id))


def cmd_cancel_backup_pod(args):
    cli.print_result(cli.get_client().cancel_backup_pod(pod_id_list=cli.parse_csv_values(args.pod_id_list), product_id=args.product_id))


def cmd_restore_pod(args):
    cli.print_result(cli.get_client().restore_pod(
        product_id=args.product_id,
        pod_id_list=cli.parse_csv_values(args.pod_id_list),
        specify_host_list=cli.parse_json_option(args.specify_host_list, '--specify-host-list', list),
    ))


def cmd_cancel_restore_pod(args):
    cli.print_result(cli.get_client().cancel_restore_pod(pod_id_list=cli.parse_csv_values(args.pod_id_list), product_id=args.product_id))


def cmd_pod_data_transfer(args):
    cli.print_result(cli.get_client().pod_data_transfer(
        origin_pod_id=args.origin_pod_id,
        dst_pod_id_list=cli.parse_csv_values(args.dst_pod_id_list),
        transfer_type=args.type,
        product_id=args.product_id,
    ))


def cmd_migrate_pod(args):
    cli.print_result(cli.get_client().migrate_pod(
        pod_id_list=cli.parse_csv_values(args.pod_id_list),
        target_dc=args.target_dc,
        product_id=args.product_id,
    ))


def cmd_backup_data(args):
    cli.print_result(cli.get_client().backup_data(
        pod_id_list=cli.parse_csv_values(args.pod_id_list),
        description=args.description,
        backup_all=cli.parse_bool_flag(args.backup_all) if args.backup_all is not None else None,
        include_path_list=cli.parse_csv_values(args.include_path_list),
        exclude_path_list=cli.parse_csv_values(args.exclude_path_list),
        product_id=args.product_id,
    ))


def cmd_restore_data(args):
    cli.print_result(cli.get_client().restore_data(
        backup_data_id=args.backup_data_id,
        pod_id_list=cli.parse_csv_values(args.pod_id_list),
        create_pod_num=args.create_pod_num,
        product_id=args.product_id,
    ))


def cmd_list_backup_data(args):
    cli.print_result(cli.get_client().list_backup_data(
        source_pod_id=args.source_pod_id,
        backup_data_id_list=cli.parse_csv_values(args.backup_data_id_list),
        status=args.status,
        max_results=args.max_results,
        next_token=args.next_token,
        product_id=args.product_id,
    ))


def cmd_delete_backup_data(args):
    cli.print_result(cli.get_client().delete_backup_data(
        backup_data_id_list=cli.parse_csv_values(args.backup_data_id_list),
        product_id=args.product_id,
    ))


def register(subparsers):

    create_pod_parser = subparsers.add_parser('create-pod', help='创建云手机实例')
    create_pod_parser.add_argument('product_id', help='产品 ID')
    create_pod_parser.add_argument('--name', required=True, help='实例名称')
    create_pod_parser.add_argument('--template-id', required=True, help='机型模板 ID')
    create_pod_parser.add_argument('--configuration-code', required=True, help='套餐代码')
    create_pod_parser.add_argument('--count', type=int, default=1, help='创建数量')
    create_pod_parser.add_argument('--dc-id', help='机房 ID（按需指定；不从配置默认读取）')
    create_pod_parser.add_argument('--image-id', help='实例镜像 ID')
    create_pod_parser.add_argument('--data-size', help='云盘存储容量，如 32Gi')
    create_pod_parser.add_argument('--display-layout-id', help='屏幕布局 ID')
    create_pod_parser.add_argument('--start', action='store_true', help='创建完成后立即开机')
    create_pod_parser.add_argument('--tag-id', help='标签 ID')
    create_pod_parser.add_argument('--up-bandwidth-limit', type=int, help='上行带宽上限 Mbps，0 表示不限速')
    create_pod_parser.add_argument('--down-bandwidth-limit', type=int, help='下行带宽上限 Mbps，0 表示不限速')
    create_pod_parser.add_argument('--custom-route-id', help='自定义路由规则 ID')
    create_pod_parser.add_argument('--dns-id', help='自定义 DNS 规则 ID')
    create_pod_parser.add_argument('--port-mapping-rule-id-list', help='端口映射规则 ID 列表，逗号分隔')
    create_pod_parser.add_argument('--ip-white-list', help='白名单 IP，逗号分隔')
    create_pod_parser.add_argument('--host-id', help='本地存储业务指定云机 ID')
    create_pod_parser.add_argument('--use-phone-template', type=int, choices=[1, 2], help='是否使用机型库：1=使用，2=不使用')
    create_pod_parser.add_argument('--phone-template-id', help='机型库 ID')
    create_pod_parser.add_argument('--is-selinux-on', action='store_true', help='开启 SELinux')
    create_pod_parser.add_argument('--resource-type', type=int, choices=[100, 200], help='业务资源类型：100=云盘存储，200=本地存储')
    create_pod_parser.set_defaults(func=cmd_create_pod)

    list_pods_parser = subparsers.add_parser('list-pods', help='查询云手机实例列表')
    list_pods_parser.add_argument('product_id', help='产品 ID')
    list_pods_parser.add_argument('--page-size', type=int, help='兼容旧参数：每页数量')
    list_pods_parser.add_argument('--page-number', type=int, help='兼容旧参数：页码')
    list_pods_parser.add_argument('--max-results', type=int, default=10, help='每页数量，最大 100')
    list_pods_parser.add_argument('--next-token', help='分页查询凭证')
    list_pods_parser.add_argument('--pod-id-list', help='实例 ID 列表，逗号分隔')
    list_pods_parser.add_argument('--configuration-code-list', help='实例规格 ID 列表，逗号分隔')
    list_pods_parser.add_argument('--region-list', help='大区 ID 列表，逗号分隔')
    list_pods_parser.add_argument('--dc-list', help='机房 ID 列表，逗号分隔')
    list_pods_parser.add_argument('--tag-id-list', help='标签 ID 列表，逗号分隔')
    list_pods_parser.add_argument('--online-list', help='运行状态列表，逗号分隔')
    list_pods_parser.add_argument('--stream-status-list', help='推流状态列表，逗号分隔')
    list_pods_parser.add_argument('--authority-status', type=int, help='运维授权状态：1=未授权，2=已授权')
    list_pods_parser.add_argument('--zone-id', help='片区 ID')
    list_pods_parser.add_argument('--server-type-code', help='云机规格')
    list_pods_parser.add_argument('--host-id', help='云机 ID')
    list_pods_parser.add_argument('--dns-id', help='DNS 规则 ID')
    list_pods_parser.add_argument('--pod-name', help='实例名称，精确查找')
    list_pods_parser.add_argument('--archive-status', type=int, help='备份/还原状态')
    list_pods_parser.set_defaults(func=cmd_list_pods)

    detail_pod_parser = subparsers.add_parser('detail-pod', help='查询云手机实例详情')
    detail_pod_parser.add_argument('product_id', help='产品 ID')
    detail_pod_parser.add_argument('pod_id', help='实例 ID')
    detail_pod_parser.set_defaults(func=cmd_detail_pod)

    delete_pod_parser = subparsers.add_parser('delete-pod', help='删除云手机实例')
    delete_pod_parser.add_argument('product_id', help='产品 ID')
    delete_pod_parser.add_argument('pod_id', help='实例 ID')
    delete_pod_parser.set_defaults(func=cmd_delete_pod)

    power_on_pod_parser = subparsers.add_parser('power-on-pod', help='开机')
    power_on_pod_parser.add_argument('product_id', help='产品 ID')
    power_on_pod_parser.add_argument('pod_id', help='实例 ID')
    power_on_pod_parser.set_defaults(func=cmd_power_on_pod)

    power_off_pod_parser = subparsers.add_parser('power-off-pod', help='关机')
    power_off_pod_parser.add_argument('product_id', help='产品 ID')
    power_off_pod_parser.add_argument('pod_id', help='实例 ID')
    power_off_pod_parser.set_defaults(func=cmd_power_off_pod)

    reboot_pod_parser = subparsers.add_parser('reboot-pod', help='重启实例')
    reboot_pod_parser.add_argument('product_id', help='产品 ID')
    reboot_pod_parser.add_argument('pod_id', help='实例 ID')
    reboot_pod_parser.set_defaults(func=cmd_reboot_pod)

    reset_pod_parser = subparsers.add_parser('reset-pod', help='重置实例')
    reset_pod_parser.add_argument('product_id', help='产品 ID')
    reset_pod_parser.add_argument('pod_id', help='实例 ID')
    reset_pod_parser.set_defaults(func=cmd_reset_pod)

    get_pod_metric_parser = subparsers.add_parser('get-pod-metric', help='查询实例资源状态')
    get_pod_metric_parser.add_argument('product_id', help='产品 ID')
    get_pod_metric_parser.add_argument('pod_id', help='实例 ID')
    get_pod_metric_parser.set_defaults(func=cmd_get_pod_metric)

    update_pod_parser = subparsers.add_parser('update-pod', help='更新实例配置或镜像')
    update_pod_parser.add_argument('product_id', help='产品 ID')
    update_pod_parser.add_argument('pod_id', help='实例 ID')
    update_pod_parser.add_argument('--image-id', help='目标镜像 ID')
    update_pod_parser.add_argument('--pod-name', help='实例新名称')
    update_pod_parser.add_argument('--data-size', help='云盘存储容量，如 32Gi')
    update_pod_parser.add_argument('--configuration-code', help='目标套餐规格 ID')
    update_pod_parser.add_argument('--display-layout-id', help='屏幕布局 ID')
    update_pod_parser.add_argument('--up-bandwidth-limit', type=int, help='上行带宽上限 Mbps')
    update_pod_parser.add_argument('--down-bandwidth-limit', type=int, help='下行带宽上限 Mbps')
    update_pod_parser.add_argument('--custom-route-id', help='自定义路由规则 ID')
    update_pod_parser.add_argument('--dns-id', help='自定义 DNS 规则 ID')
    update_pod_parser.add_argument('--port-mapping-rule-id-list', help='端口映射规则 ID 列表，逗号分隔')
    update_pod_parser.add_argument('--ip-white-list', help='白名单 IP，逗号分隔')
    update_pod_parser.add_argument('--is-selinux-on', action='store_true', help='开启 SELinux')
    update_pod_parser.add_argument('--force', action='store_true', help='传 Force=true 强制更新运行中实例；镜像需重启后生效')
    update_pod_parser.set_defaults(func=cmd_update_pod)

    set_proxy_parser = subparsers.add_parser('set-proxy', help='设置代理服务')
    set_proxy_parser.add_argument('product_id', help='产品 ID')
    set_proxy_parser.add_argument('--pod-id-list', required=True, help='实例 ID 列表，逗号分隔')
    set_proxy_parser.add_argument('--proxy-status', type=int, choices=[0, 1], required=True, help='代理状态：1=开启，0=关闭')
    set_proxy_parser.add_argument('--proxy-config', help='ProxyConfig JSON 对象；开启代理时必填')
    set_proxy_parser.set_defaults(func=cmd_set_proxy)

    get_proxy_parser = subparsers.add_parser('get-proxy', help='获取代理服务设置')
    get_proxy_parser.add_argument('product_id', help='产品 ID')
    get_proxy_parser.add_argument('--pod-id-list', required=True, help='实例 ID 列表，逗号分隔')
    get_proxy_parser.set_defaults(func=cmd_get_proxy)

    get_edge_url_parser = subparsers.add_parser('get-presigned-edge-url', help='获取实例直连预签名 URL（GetPreSignedEdgeURL）')
    get_edge_url_parser.add_argument('product_id', help='产品 ID')
    get_edge_url_parser.add_argument('pod_id', help='实例 ID')
    get_edge_url_parser.add_argument('--api-type', required=True, help='API 类型，如 TakeScreenshot 或 Sandbox')
    get_edge_url_parser.add_argument('--api-path', help='API 路径，如 /screenshot、/sandbox/ws、/sandbox/exec、/sandbox/healthz')
    get_edge_url_parser.add_argument('--payload', action='append', help='APIPayload 键值对，Key=Value，可重复；Value 总是按字符串传递')
    get_edge_url_parser.add_argument('--ttl', type=int, help='预签名链接有效期，单位秒，默认 60，最大 86400')
    get_edge_url_parser.add_argument('--timeout', type=int, help='直连请求超时时间，单位秒')
    get_edge_url_parser.add_argument('--single-use', action='store_true', default=None, help='生成单次使用 URL')
    get_edge_url_parser.set_defaults(func=cmd_get_presigned_edge_url)

    pod_mute_parser = subparsers.add_parser('pod-mute', help='暂停/恢复实例推流')
    pod_mute_parser.add_argument('product_id', help='产品 ID')
    pod_mute_parser.add_argument('--pod-id', required=True, help='实例 ID')
    pod_mute_parser.add_argument('--mute', required=True, type=cli.parse_bool_flag, help='true=暂停推流，false=恢复推流')
    pod_mute_parser.add_argument('--display-list', help='屏幕 ID 列表，逗号分隔')
    pod_mute_parser.set_defaults(func=cmd_pod_mute)

    pod_adb_parser = subparsers.add_parser('pod-adb', help='打开/关闭实例 ADB')
    pod_adb_parser.add_argument('product_id', help='产品 ID')
    pod_adb_parser.add_argument('--pod-id', required=True, help='实例 ID')
    pod_adb_parser.add_argument('--enable', required=True, type=cli.parse_bool_flag, help='true=开启 ADB，false=关闭 ADB')
    pod_adb_parser.set_defaults(func=cmd_pod_adb)

    pod_stop_parser = subparsers.add_parser('pod-stop', help='停止实例推流')
    pod_stop_parser.add_argument('product_id', help='产品 ID')
    pod_stop_parser.add_argument('--pod-id', required=True, help='实例 ID')
    pod_stop_parser.set_defaults(func=cmd_pod_stop)

    pod_data_delete_parser = subparsers.add_parser('pod-data-delete', help='清理用户数据')
    pod_data_delete_parser.add_argument('product_id', help='产品 ID')
    pod_data_delete_parser.add_argument('--pod-id', required=True, help='实例 ID')
    pod_data_delete_parser.add_argument('--file-path-list', required=True, help='路径列表，逗号分隔')
    pod_data_delete_parser.add_argument('--package-list', help='包名列表，逗号分隔')
    pod_data_delete_parser.set_defaults(func=cmd_pod_data_delete)

    create_pod_one_step_parser = subparsers.add_parser('create-pod-one-step', help='创建安卓实例并部署应用')
    create_pod_one_step_parser.add_argument('product_id', help='产品 ID')
    create_pod_one_step_parser.add_argument('--pod-name', help='实例名称')
    create_pod_one_step_parser.add_argument('--image-id', help='镜像 ID')
    create_pod_one_step_parser.add_argument('--configuration-code', required=True, help='套餐规格 ID')
    create_pod_one_step_parser.add_argument('--data-size', help='云盘存储容量，如 8Gi')
    create_pod_one_step_parser.add_argument('--dc', required=True, help='机房 ID')
    create_pod_one_step_parser.add_argument('--display-layout-id', help='屏幕布局 ID')
    create_pod_one_step_parser.add_argument('--overlay-settings', help='OverlaySettings JSON 数组')
    create_pod_one_step_parser.add_argument('--overlay-property', help='OverlayProperty JSON 数组')
    create_pod_one_step_parser.add_argument('--overlay-persist-property', help='OverlayPersistProperty JSON 数组')
    create_pod_one_step_parser.add_argument('--tag-id', help='标签 ID')
    create_pod_one_step_parser.add_argument('--up-bandwidth-limit', type=int, help='上行带宽限制 Mbps')
    create_pod_one_step_parser.add_argument('--down-bandwidth-limit', type=int, help='下行带宽限制 Mbps')
    create_pod_one_step_parser.add_argument('--app-list', required=True, help='应用列表，支持 AppId:VersionId,AppId2:VersionId2 或 JSON 数组')
    create_pod_one_step_parser.add_argument('--custom-route-id', help='自定义路由 ID')
    create_pod_one_step_parser.add_argument('--dns-id', help='DNS 规则 ID')
    create_pod_one_step_parser.add_argument('--port-mapping-rule-id-list', help='端口映射规则 ID 列表，逗号分隔')
    create_pod_one_step_parser.add_argument('--ip-white-list', help='白名单 IP，逗号分隔')
    create_pod_one_step_parser.add_argument('--resource-type', type=int, choices=[100, 200], help='资源类型')
    create_pod_one_step_parser.add_argument('--host-id', help='云机 ID')
    create_pod_one_step_parser.add_argument('--is-preinstall', type=cli.parse_bool_flag, help='是否标记为预装应用：true/false')
    create_pod_one_step_parser.add_argument('--use-phone-template', type=int, choices=[1, 2], help='是否使用机型库')
    create_pod_one_step_parser.add_argument('--phone-template-id', help='机型库 ID')
    create_pod_one_step_parser.add_argument('--is-selinux-on', type=cli.parse_bool_flag, help='是否开启 SELinux：true/false')
    create_pod_one_step_parser.set_defaults(func=cmd_create_pod_one_step)

    update_pod_resource_apply_num_parser = subparsers.add_parser('update-pod-resource-apply-num', help='修改实例订单并发数量')
    update_pod_resource_apply_num_parser.add_argument('product_id', help='产品 ID')
    update_pod_resource_apply_num_parser.add_argument('--resource-set-id', help='资源组 ID')
    update_pod_resource_apply_num_parser.add_argument('--configuration-code', help='实例规格 ID')
    update_pod_resource_apply_num_parser.add_argument('--dc', help='机房 ID')
    update_pod_resource_apply_num_parser.add_argument('--apply-num', type=int, required=True, help='修改后的实例数量')
    update_pod_resource_apply_num_parser.set_defaults(func=cmd_update_pod_resource_apply_num)

    backup_pod_parser = subparsers.add_parser('backup-pod', help='备份实例')
    backup_pod_parser.add_argument('product_id', help='产品 ID')
    backup_pod_parser.add_argument('--pod-id-list', required=True, help='实例 ID 列表，逗号分隔')
    backup_pod_parser.set_defaults(func=cmd_backup_pod)

    cancel_backup_pod_parser = subparsers.add_parser('cancel-backup-pod', help='取消备份实例')
    cancel_backup_pod_parser.add_argument('product_id', help='产品 ID')
    cancel_backup_pod_parser.add_argument('--pod-id-list', required=True, help='实例 ID 列表，逗号分隔')
    cancel_backup_pod_parser.set_defaults(func=cmd_cancel_backup_pod)

    restore_pod_parser = subparsers.add_parser('restore-pod', help='还原实例')
    restore_pod_parser.add_argument('product_id', help='产品 ID')
    restore_pod_parser.add_argument('--pod-id-list', help='待还原实例 ID 列表，逗号分隔')
    restore_pod_parser.add_argument('--specify-host-list', help='SpecifyHostList JSON 数组')
    restore_pod_parser.set_defaults(func=cmd_restore_pod)

    cancel_restore_pod_parser = subparsers.add_parser('cancel-restore-pod', help='取消还原实例')
    cancel_restore_pod_parser.add_argument('product_id', help='产品 ID')
    cancel_restore_pod_parser.add_argument('--pod-id-list', required=True, help='实例 ID 列表，逗号分隔')
    cancel_restore_pod_parser.set_defaults(func=cmd_cancel_restore_pod)

    pod_data_transfer_parser = subparsers.add_parser('pod-data-transfer', help='实例数据复制迁移')
    pod_data_transfer_parser.add_argument('product_id', help='产品 ID')
    pod_data_transfer_parser.add_argument('--origin-pod-id', required=True, help='源实例 ID')
    pod_data_transfer_parser.add_argument('--dst-pod-id-list', required=True, help='目标实例 ID 列表，逗号分隔')
    pod_data_transfer_parser.add_argument('--type', type=int, help='复制迁移方式')
    pod_data_transfer_parser.set_defaults(func=cmd_pod_data_transfer)

    migrate_pod_parser = subparsers.add_parser('migrate-pod', help='迁移实例')
    migrate_pod_parser.add_argument('product_id', help='产品 ID')
    migrate_pod_parser.add_argument('--pod-id-list', required=True, help='实例 ID 列表，逗号分隔')
    migrate_pod_parser.add_argument('--target-dc', help='目标机房 ID')
    migrate_pod_parser.set_defaults(func=cmd_migrate_pod)

    backup_data_parser = subparsers.add_parser('backup-data', help='备份数据')
    backup_data_parser.add_argument('product_id', help='产品 ID')
    backup_data_parser.add_argument('--pod-id-list', required=True, help='实例 ID 列表，逗号分隔')
    backup_data_parser.add_argument('--description', help='备份描述')
    backup_data_parser.add_argument('--backup-all', type=cli.parse_bool_flag, help='是否全量备份：true/false')
    backup_data_parser.add_argument('--include-path-list', help='包含路径列表，逗号分隔')
    backup_data_parser.add_argument('--exclude-path-list', help='排除路径列表，逗号分隔')
    backup_data_parser.set_defaults(func=cmd_backup_data)

    restore_data_parser = subparsers.add_parser('restore-data', help='恢复数据')
    restore_data_parser.add_argument('product_id', help='产品 ID')
    restore_data_parser.add_argument('--backup-data-id', required=True, help='备份数据 ID')
    restore_data_parser.add_argument('--pod-id-list', help='目标实例 ID 列表，逗号分隔')
    restore_data_parser.add_argument('--create-pod-num', type=int, help='自动创建实例数量')
    restore_data_parser.set_defaults(func=cmd_restore_data)

    list_backup_data_parser = subparsers.add_parser('list-backup-data', help='查询备份数据')
    list_backup_data_parser.add_argument('product_id', help='产品 ID')
    list_backup_data_parser.add_argument('--source-pod-id', help='源实例 ID')
    list_backup_data_parser.add_argument('--backup-data-id-list', help='备份数据 ID 列表，逗号分隔')
    list_backup_data_parser.add_argument('--status', help='备份数据状态')
    list_backup_data_parser.add_argument('--max-results', type=int, default=10, help='每页数量')
    list_backup_data_parser.add_argument('--next-token', help='分页游标')
    list_backup_data_parser.set_defaults(func=cmd_list_backup_data)

    delete_backup_data_parser = subparsers.add_parser('delete-backup-data', help='删除备份数据')
    delete_backup_data_parser.add_argument('product_id', help='产品 ID')
    delete_backup_data_parser.add_argument('--backup-data-id-list', required=True, help='备份数据 ID 列表，逗号分隔')
    delete_backup_data_parser.set_defaults(func=cmd_delete_backup_data)
