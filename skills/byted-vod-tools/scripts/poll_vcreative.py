#!/usr/bin/env python3
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
poll_vcreative.py — 重启编辑类任务轮询

用法:
  python <SKILL_DIR>/scripts/poll_vcreative.py <task_id> [space_name]
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api_manage import ApiManage
from vod_common import get_space_name, out, bail


def main():
    if len(sys.argv) < 2:
        bail(
            "用法: python <SKILL_DIR>/scripts/poll_vcreative.py <task_id> [space_name]"
        )
    task_id = sys.argv[1]
    api = ApiManage()
    space_name = get_space_name(argv_pos=2)
    result = api.poll_vcreative(task_id, space_name)
    out(result)


if __name__ == "__main__":
    main()
