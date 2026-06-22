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

from . import cli_common as cli


def cmd_get_task_info(args):
    result = cli.get_client().get_task_info(task_id=args.task_id, product_id=args.product_id)
    cli.print_result(result)


def cmd_list_tasks(args):
    result = cli.get_client().list_tasks(
        max_results=args.max_results,
        next_token=args.next_token,
        product_id=args.product_id,
        TaskId=args.task_id,
        TaskAction=args.task_action,
        TaskResult=args.task_result,
        StartTime=args.start_time,
        EndTime=args.end_time,
    )
    cli.print_result(result)


def register(subparsers):

    get_task_info_parser = subparsers.add_parser('get-task-info', help='查询任务详情')
    get_task_info_parser.add_argument('product_id', help='产品 ID')
    get_task_info_parser.add_argument('task_id', help='任务 ID')
    get_task_info_parser.set_defaults(func=cmd_get_task_info)

    list_tasks_parser = subparsers.add_parser('list-tasks', help='查询任务列表')
    list_tasks_parser.add_argument('product_id', help='产品 ID')
    list_tasks_parser.add_argument('--task-id', help='任务 ID')
    list_tasks_parser.add_argument('--task-action', help='任务 Action')
    list_tasks_parser.add_argument('--task-result', type=int, help='任务结果/进度')
    list_tasks_parser.add_argument('--start-time', type=int, help='开始时间 Unix 秒')
    list_tasks_parser.add_argument('--end-time', type=int, help='结束时间 Unix 秒')
    list_tasks_parser.add_argument('--max-results', type=int, default=10, help='每页数量')
    list_tasks_parser.add_argument('--next-token', help='分页游标')
    list_tasks_parser.set_defaults(func=cmd_list_tasks)
