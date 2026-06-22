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
"""
火山云手机 CLI 工具
"""

import argparse
import sys

from core import (
    apps,
    dcs,
    display_layouts,
    hosts,
    images,
    instance_controls,
    instance_properties,
    instances,
    network,
    products,
    resources,
    tags,
    tasks,
)


COMMAND_GROUPS = (
    ('任务', '任务查询与排障', (tasks,)),
    ('实例', '实例生命周期与属性', (instances, instance_properties)),
    ('主机与镜像', '主机、镜像与机房查询', (hosts, images, dcs, products, resources, display_layouts)),
    ('应用', '应用上传、安装、启动与查询', (apps,)),
    ('设备控制', '录屏、截图、文件和命令执行', (instance_controls,)),
    ('标签与网络', '标签、DNS、路由和端口映射', (tags, network)),
)


def _register_command_groups(subparsers):
    groups = []
    for title, summary, modules in COMMAND_GROUPS:
        before = set(subparsers.choices)
        for module in modules:
            module.register(subparsers)
        commands = sorted(set(subparsers.choices) - before)
        groups.append({
            'title': title,
            'summary': summary,
            'commands': commands,
        })
    return groups


def _command_help_map(subparsers):
    return {
        action.dest: action.help or ''
        for action in subparsers._get_subactions()
    }


def _format_command_line(command, help_text):
    return f'    {command:<28} {help_text}'.rstrip()


def print_top_level_help(parser, subparsers, groups):
    help_map = _command_help_map(subparsers)
    lines = [
        parser.description,
        '',
        '用法:',
        '  vephone <command> [args]',
        '  vephone <command> -h',
        '',
        '说明:',
        '  大多数业务命令都需要显式传入 product_id。',
        '  查看某个命令的详细参数，请使用 vephone <command> -h。',
        '',
        '命令分组:',
    ]

    for group in groups:
        lines.append(f'  {group["title"]}  {group["summary"]}')
        for command in group['commands']:
            lines.append(_format_command_line(command, help_map.get(command, '')))
        lines.append('')

    lines.extend([
        '示例:',
        '  vephone list-products --count 10',
        '  vephone list-pods <product_id> --max-results 10',
        '  vephone detail-pod <product_id> <pod_id>',
        '  vephone get-task-info <product_id> <task_id>',
    ])
    print('\n'.join(lines).rstrip())


def build_parser():
    parser = argparse.ArgumentParser(
        prog='vephone',
        description='火山云手机 CLI 工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest='command', metavar='<command>', help='命令名称')
    groups = _register_command_groups(subparsers)
    return parser, subparsers, groups


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser, subparsers, groups = build_parser()

    if not argv or argv == ['-h'] or argv == ['--help']:
        print_top_level_help(parser, subparsers, groups)
        sys.exit(0 if argv else 1)

    args = parser.parse_args(argv)
    if not args.command:
        print_top_level_help(parser, subparsers, groups)
        sys.exit(1)
    args.func(args)


if __name__ == '__main__':
    main()
