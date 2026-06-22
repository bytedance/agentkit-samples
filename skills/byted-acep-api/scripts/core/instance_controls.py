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

"""实例控制模块。"""
from . import cli_common as cli

import tempfile
from pathlib import Path

from . import cli_common as cli


def cmd_start_recording(args):
    kwargs = cli.request_kwargs(args)
    if args.is_saved_on_pod is not None:
        kwargs['is_saved_on_pod'] = args.is_saved_on_pod
    cli.print_result(cli.get_client().start_recording(
        args.pod_id,
        duration_limit=args.duration_limit,
        round_id=args.round_id,
        **kwargs,
    ))


def cmd_stop_recording(args):
    cli.print_result(cli.get_client().stop_recording(args.pod_id, **cli.request_kwargs(args)))


def cmd_batch_screen_shot(args):
    kwargs = cli.request_kwargs(args)
    if args.pod_id_list:
        kwargs['pod_id_list'] = cli.parse_csv(args.pod_id_list)
    if (args.width is None) != (args.height is None):
        raise SystemExit('--width 和 --height 必须同时传入')
    if args.width is not None:
        kwargs['width'] = args.width
    if args.height is not None:
        kwargs['height'] = args.height
    if args.quality is not None:
        kwargs['quality'] = args.quality
    if args.is_saved_on_pod is not None:
        kwargs['is_saved_on_pod'] = args.is_saved_on_pod
    if args.resize_mode is not None:
        kwargs['resize_mode'] = args.resize_mode
    if args.rotation is not None:
        kwargs['rotation'] = args.rotation
    if args.upload_type is not None:
        kwargs['upload_type'] = args.upload_type
    if args.round_id:
        kwargs['round_id'] = args.round_id
    if args.is_broadcasted is not None:
        kwargs['is_broadcasted'] = args.is_broadcasted
    if args.upload_type == 2 and not (args.tos_bucket and args.tos_region and args.tos_endpoint):
        raise SystemExit('--upload-type=2 时必须同时传入 --tos-bucket、--tos-region 和 --tos-endpoint')
    if args.tos_bucket or args.tos_region or args.tos_endpoint:
        if not (args.tos_bucket and args.tos_region and args.tos_endpoint):
            raise SystemExit('--tos-bucket、--tos-region 和 --tos-endpoint 必须同时传入')
        kwargs['tos_info'] = {
            'Bucket': args.tos_bucket,
            'Region': args.tos_region,
            'Endpoint': args.tos_endpoint,
        }
    cli.print_result(cli.get_client().batch_screen_shot(args.pod_id, **kwargs))


def cmd_push_file(args):
    kwargs = cli.request_kwargs(args)
    if args.auto_unzip is not None:
        kwargs['AutoUnzip'] = args.auto_unzip == 0
    if args.overwrite is not None:
        kwargs['OverWrite'] = args.overwrite
    cli.print_result(cli.get_client().push_file(
        pod_id=args.pod_id,
        file_url=args.local_path,
        phone_path=args.phone_path,
        **kwargs,
    ))


def cmd_pull_file(args):
    kwargs = cli.request_kwargs(args)
    if args.range:
        kwargs['Range'] = args.range
    cli.print_result(cli.get_client().pull_file(
        pod_id=args.pod_id,
        phone_path=args.phone_path,
        output_path=args.output,
        **kwargs,
    ))


def cmd_run_command(args):
    kwargs = cli.request_kwargs(args)
    if args.permission_type:
        kwargs['permission_type'] = args.permission_type
    if args.timeout_seconds is not None:
        kwargs['timeout_seconds'] = args.timeout_seconds
    cli.print_result(cli.get_client().run_command(
        pod_id=args.pod_id,
        command=args.command,
        **kwargs,
    ))


def cmd_run_sync_command(args):
    kwargs = cli.request_kwargs(args)
    if args.permission_type:
        kwargs['PermissionType'] = args.permission_type
    if args.timeout_second is not None:
        kwargs['TimeoutSecond'] = args.timeout_second
    if args.result_length is not None:
        kwargs['ResultLength'] = args.result_length
    cli.print_result(cli.get_client().run_sync_command(
        pod_id=args.pod_id,
        command=args.command,
        **kwargs,
    ))


def cmd_pull_logcat(args):
    pod_id = args.pod_id
    local_path = Path(args.output).expanduser() if args.output else Path.cwd() / f'logcat_{pod_id}'
    filter_terms = args.filter_term or []
    if not args.no_default_filters:
        filter_terms = ['RunCommandHandler', 'AgentRPCServer', *filter_terms]
    max_bytes = args.max_bytes

    def logcat_paths(path: str) -> list[str]:
        aliases = ['/data/misc/logd/logcat']
        ordered = [path, *aliases]
        result = []
        for item in ordered:
            if item not in result:
                result.append(item)
        return result

    def filter_payload(payload: bytes) -> bytes:
        if not filter_terms:
            return payload
        encoded_terms = [term.encode('utf-8') for term in filter_terms]
        return b''.join(
            line for line in payload.splitlines(keepends=True)
            if not any(term in line for term in encoded_terms)
        )

    request_options = cli.request_kwargs(args)
    errors = {}
    raw_payload = None
    used_remote_path = None
    with tempfile.TemporaryDirectory(prefix=f'vephone-logcat-{pod_id}-') as tmpdir:
        temp_output = Path(tmpdir) / 'logcat.raw'
        for candidate in logcat_paths(args.remote_path):
            try:
                cli.get_client().pull_file(pod_id, candidate, output_path=str(temp_output), **request_options)
                raw_payload = temp_output.read_bytes()
                used_remote_path = candidate
                break
            except Exception as exc:
                errors[candidate] = str(exc)
        if raw_payload is None:
            detail = '; '.join(f'{path}: {message}' for path, message in errors.items())
            raise RuntimeError(f'pull-logcat failed for all candidate paths: {detail}')

    raw_size = len(raw_payload)
    filtered_payload = filter_payload(raw_payload)
    filtered_size = len(filtered_payload)
    output_payload = filtered_payload[-max_bytes:] if filtered_size > max_bytes else filtered_payload
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(output_payload)
    cli.print_result({
        'PodId': pod_id,
        'RemotePath': used_remote_path,
        'RequestedRemotePath': args.remote_path,
        'Output': str(local_path),
        'Size': len(output_payload),
        'RawSize': raw_size,
        'FilteredBytes': raw_size - filtered_size,
        'TruncatedBytes': filtered_size - len(output_payload),
        'FilterTerms': filter_terms,
        'SourceSize': raw_size,
        'SourceOffset': max(filtered_size - len(output_payload), 0),
        'MaxBytes': max_bytes,
        'Mode': 'PreSignedEdgeURL',
    })


def cmd_ban_user(args):
    cli.print_result(cli.get_client().ban_user(
        pod_id=args.pod_id,
        user_id=args.user_id,
        product_id=args.product_id,
        forbidden_interval=args.forbidden_interval,
        is_preview_stream=args.is_preview_stream,
    ))


def register(subparsers):

    start_recording_parser = subparsers.add_parser('start-recording', help='开始录屏')
    start_recording_parser.add_argument('product_id', help='产品 ID')
    start_recording_parser.add_argument('pod_id', help='实例 ID')
    start_recording_parser.add_argument('--duration-limit', type=int, required=True, help='最大录制时长，秒，最大 14400')
    start_recording_parser.add_argument('--round-id', required=True, help='录屏请求唯一 ID')
    start_recording_parser.add_argument('--is-saved-on-pod', dest='is_saved_on_pod', action='store_true', help='在云手机实例中保留录屏文件')
    start_recording_parser.add_argument('--no-is-saved-on-pod', dest='is_saved_on_pod', action='store_false', help='不在云手机实例中保留录屏文件')
    start_recording_parser.set_defaults(is_saved_on_pod=None)
    start_recording_parser.set_defaults(func=cmd_start_recording)

    stop_recording_parser = subparsers.add_parser('stop-recording', help='停止录屏')
    stop_recording_parser.add_argument('product_id', help='产品 ID')
    stop_recording_parser.add_argument('pod_id', help='实例 ID')
    stop_recording_parser.set_defaults(func=cmd_stop_recording)

    batch_screen_shot_parser = subparsers.add_parser('batch-screen-shot', help='执行 BatchScreenShot 截图')
    batch_screen_shot_parser.add_argument('product_id', help='产品 ID')
    batch_screen_shot_parser.add_argument('pod_id', help='实例 ID')
    batch_screen_shot_parser.add_argument('--pod-id-list', help='批量截图实例 ID 列表，逗号分隔；默认仅使用位置参数 pod_id')
    batch_screen_shot_parser.add_argument('--width', type=int, help='截图宽度，范围 200-2560；与 --height 互相依赖')
    batch_screen_shot_parser.add_argument('--height', type=int, help='截图高度，范围 200-2560；与 --width 互相依赖')
    batch_screen_shot_parser.add_argument('--quality', type=int, help='截图画质压缩比例，范围 1-100')
    batch_screen_shot_parser.add_argument('--is-saved-on-pod', dest='is_saved_on_pod', action='store_true', help='在云手机实例中保留截图文件')
    batch_screen_shot_parser.add_argument('--no-is-saved-on-pod', dest='is_saved_on_pod', action='store_false', help='不在云手机实例中保留截图文件')
    batch_screen_shot_parser.set_defaults(is_saved_on_pod=None)
    batch_screen_shot_parser.add_argument('--resize-mode', type=int, choices=[0, 1, 2, 3, 4], help='截图缩放模式')
    batch_screen_shot_parser.add_argument('--rotation', type=int, choices=[0, 1], help='截图旋转方向：0 不处理，1 转为竖屏')
    batch_screen_shot_parser.add_argument('--upload-type', type=int, choices=[1, 2], help='上传方式：1 上传到业务对象存储，2 上传到私有存储桶')
    batch_screen_shot_parser.add_argument('--tos-bucket', help='UploadType=2 时的 TOS Bucket')
    batch_screen_shot_parser.add_argument('--tos-region', help='UploadType=2 时的 TOS Region')
    batch_screen_shot_parser.add_argument('--tos-endpoint', help='UploadType=2 时的 TOS Endpoint')
    batch_screen_shot_parser.add_argument('--round-id', help='截图请求唯一标识，5 分钟内不可重复')
    batch_screen_shot_parser.add_argument('--is-broadcasted', dest='is_broadcasted', action='store_true', help='广播截图事件')
    batch_screen_shot_parser.add_argument('--no-is-broadcasted', dest='is_broadcasted', action='store_false', help='不广播截图事件')
    batch_screen_shot_parser.set_defaults(is_broadcasted=None)
    batch_screen_shot_parser.set_defaults(func=cmd_batch_screen_shot)

    push_file_parser = subparsers.add_parser('push-file', help='上传文件到云手机')
    push_file_parser.add_argument('product_id', help='产品 ID')
    push_file_parser.add_argument('pod_id', help='实例 ID')
    push_file_parser.add_argument('local_path', help='本地文件路径，支持 file:// 路径')
    push_file_parser.add_argument('phone_path', help='云手机目标文件路径；若传目录则自动拼接本地文件名')
    push_file_parser.add_argument('--auto-unzip', type=int, choices=[0, 1], help='兼容旧参数：0 自动解压 zip，1 不自动解压')
    push_file_parser.add_argument('--overwrite', dest='overwrite', action='store_true', help='覆盖同名远端文件')
    push_file_parser.add_argument('--no-overwrite', dest='overwrite', action='store_false', help='不覆盖同名远端文件')
    push_file_parser.set_defaults(overwrite=None)
    push_file_parser.set_defaults(func=cmd_push_file)

    pull_file_parser = subparsers.add_parser('pull-file', help='从云手机下载文件')
    pull_file_parser.add_argument('product_id', help='产品 ID')
    pull_file_parser.add_argument('pod_id', help='实例 ID')
    pull_file_parser.add_argument('phone_path', help='云手机上的文件路径')
    pull_file_parser.add_argument('--output', help='本地输出路径，默认使用当前目录下的原文件名')
    pull_file_parser.add_argument('--range', help='HTTP Range 头，如 bytes=0-1023')
    pull_file_parser.set_defaults(func=cmd_pull_file)

    run_command_parser = subparsers.add_parser('run-command', help='异步执行命令')
    run_command_parser.add_argument('product_id', help='产品 ID')
    run_command_parser.add_argument('pod_id', help='实例 ID')
    run_command_parser.add_argument('command', help='要执行的命令')
    run_command_parser.add_argument('--permission-type', choices=['root', 'shell'], help='命令执行权限类型')
    run_command_parser.add_argument('--timeout-seconds', type=int, help='异步命令超时时长，单位秒')
    run_command_parser.set_defaults(func=cmd_run_command)

    run_sync_command_parser = subparsers.add_parser('run-sync-command', help='同步执行命令')
    run_sync_command_parser.add_argument('product_id', help='产品 ID')
    run_sync_command_parser.add_argument('pod_id', help='实例 ID')
    run_sync_command_parser.add_argument('command', help='要执行的命令')
    run_sync_command_parser.add_argument('--permission-type', choices=['root', 'shell'], help='命令执行权限类型')
    run_sync_command_parser.add_argument('--timeout-second', type=int, help='命令超时时间，单位秒')
    run_sync_command_parser.add_argument('--result-length', type=int, help='stdout/stderr 最大返回字节数')
    run_sync_command_parser.set_defaults(func=cmd_run_sync_command)

    pull_logcat_parser = subparsers.add_parser('pull-logcat', help='通过 PreSignedEdgeURL 直连拉取 logcat，并在本地过滤/截断')
    pull_logcat_parser.add_argument('product_id', help='产品 ID')
    pull_logcat_parser.add_argument('pod_id', help='实例 ID')
    pull_logcat_parser.add_argument('--output', help='本地输出文件，默认 ./logcat_<pod_id>')
    pull_logcat_parser.add_argument('--remote-path', default='/data/misc/logd/logcat', help='远端 logcat 路径，默认 /data/misc/logd/logcat')
    pull_logcat_parser.add_argument('--chunk-size', type=int, default=800, help='兼容旧参数，当前实现不再使用')
    pull_logcat_parser.add_argument('--max-bytes', type=int, default=5 * 1024 * 1024, help='最多拉取末尾字节数，默认 5MB')
    pull_logcat_parser.add_argument('--concurrency', type=int, default=5, help='兼容旧参数，当前实现不再使用')
    pull_logcat_parser.add_argument('--retries', type=int, default=3, help='兼容旧参数，当前实现不再使用')
    pull_logcat_parser.add_argument('--resume', action='store_true', help='兼容旧参数，当前实现不再使用')
    pull_logcat_parser.add_argument('--cleanup-on-failure', action='store_true', help='兼容旧参数，当前实现不再使用')
    pull_logcat_parser.add_argument('--filter-term', action='append', help='额外过滤包含该字符串的行，可重复')
    pull_logcat_parser.add_argument('--no-default-filters', action='store_true', help='不默认过滤 RunCommandHandler/AgentRPCServer')
    pull_logcat_parser.set_defaults(func=cmd_pull_logcat)

    ban_user_parser = subparsers.add_parser('ban-user', help='封禁用户')
    ban_user_parser.add_argument('product_id', help='产品 ID')
    ban_user_parser.add_argument('--pod-id', required=True, help='实例 ID')
    ban_user_parser.add_argument('--user-id', required=True, help='用户 ID')
    ban_user_parser.add_argument('--forbidden-interval', type=int, help='封禁时长秒')
    ban_user_parser.add_argument('--is-preview-stream', action='store_true', help='小流')
    ban_user_parser.set_defaults(func=cmd_ban_user)
