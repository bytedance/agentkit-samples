# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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
"""byted-vms-aicall · 火山云通信智能外呼 Skill 脚本.

封装的 TOP Action:
    - QueryRobotCallScripts    list_scripts    查询可用机器人话术
    - CreateTocRobotCallTask   create_task     创建外呼任务
    - QueryTocRobotCallTask    query_task      查询任务状态/结果
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _topclient import call_top, emit, fail  # noqa: E402


def cmd_list_scripts(args: argparse.Namespace) -> Dict[str, Any]:
    body: Dict[str, Any] = {}
    if args.scene:
        body["Scene"] = args.scene
    return call_top("QueryRobotCallScripts", body, method="GET")


def cmd_create_task(args: argparse.Namespace) -> Dict[str, Any]:
    phones = [p.strip() for p in args.phone_list.split(",") if p.strip()]
    variable_values = args.variable_values or "{}"
    # 服务端要求 VariableValues 是字符串 (JSON), 这里若用户传的是合法 JSON 对象/数组也透传成字符串
    try:
        parsed = json.loads(variable_values)
        if not isinstance(parsed, str):
            variable_values = json.dumps(parsed, ensure_ascii=False)
    except json.JSONDecodeError:
        pass
    phone_list = [{"CalledNumber": phone, "VariableValues": variable_values}
                  for phone in phones]
    body: Dict[str, Any] = {
        "ScriptId": args.script_id,
        "PhoneList": phone_list,
    }
    return call_top("CreateTocRobotCallTask", body)


def cmd_query_task(args: argparse.Namespace) -> Dict[str, Any]:
    body: Dict[str, Any] = {"TaskId": args.task_id}
    return call_top("QueryTocRobotCallTask", body, method="GET")


_ACTIONS = {
    "list_scripts": cmd_list_scripts,
    "create_task": cmd_create_task,
    "query_task": cmd_query_task,
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="byted-vms-aicall · 火山云通信智能外呼")
    sub = p.add_subparsers(dest="action", required=True)

    sp = sub.add_parser("list_scripts", help="查询机器人话术 (QueryRobotCallScripts)")
    sp.add_argument("--scene", help="场景: restaurant_booking 等. 不传返回所有可用场景")

    sp = sub.add_parser("create_task", help="创建外呼任务 (CreateTocRobotCallTask)")
    sp.add_argument("--script-id", required=True, help="话术 ID, 由 list_scripts 拿到")
    sp.add_argument("--phone-list", required=True,
                    help="被叫号码 (CalledNumber), 多个用逗号分隔, 最多 15 条")
    sp.add_argument("--variable-values", required=True,
                    help="JSON 字符串, 话术变量值, key 为接口一返回的 Variables.Name."
                         " 例: '{\"餐厅\":\"必胜客\",\"时间\":\"2026-05-29 18:00\",\"人数\":\"3\"}'")

    sp = sub.add_parser("query_task", help="查询任务结果 (QueryTocRobotCallTask)")
    sp.add_argument("--task-id", required=True)

    return p


def main() -> None:
    args = build_parser().parse_args()
    try:
        result = _ACTIONS[args.action](args)
    except BaseException as exc:  # noqa: BLE001
        fail(exc)
        return
    emit(result)


if __name__ == "__main__":
    main()
