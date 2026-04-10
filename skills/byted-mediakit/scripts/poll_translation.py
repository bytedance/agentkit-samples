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
poll_translation.py — 重启 AI 视频翻译项目轮询 / 查询项目详情

用法:
  python <SKILL_DIR>/scripts/poll_translation.py <ProjectId> [space_name]

功能:
  1. 查询指定 ProjectId 的翻译项目状态
  2. 如果项目仍在处理中，持续轮询直到终态
  3. 返回项目详情（含输出视频链接）

输出:
  成功: {"Status":"ProcessSucceed","ProjectId":"xxx","OutputVideo":{...},...}
  处理中: 持续轮询直到终态或超时
  失败: {"Status":"ProcessFailed","error":"..."}
"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_manage import ApiManage
from vod_common import (
    get_space_name,
    log,
    bail,
    out,
    POLL_INTERVAL,
    POLL_MAX,
)

# 导入 video_translation 中的轮询和格式化函数
from video_translation import (
    poll_translation_project,
    TERMINAL_SUCCESS,
    TERMINAL_FAIL,
    SUSPENDED,
    _format_project_result,
)


def main():
    if len(sys.argv) < 2:
        bail("用法: python <SKILL_DIR>/scripts/poll_translation.py <ProjectId> [space_name]")

    project_id = sys.argv[1]

    api = ApiManage()
    space_name = get_space_name(argv_pos=2)

    # 先查一次当前状态
    log(f"查询翻译项目: ProjectId={project_id}")
    try:
        raw = api.get_ai_translation_project({
            "SpaceName": space_name,
            "ProjectId": project_id,
        })
    except Exception as e:
        bail(f"查询翻译项目失败: {e}")

    if isinstance(raw, str):
        raw = json.loads(raw)

    result = raw.get("Result", raw)
    project_info = result.get("ProjectInfo", result)
    status = project_info.get("Status", "")
    log(f"当前状态: {status}")

    # 如果已经是终态，直接返回
    if status in TERMINAL_SUCCESS:
        out(_format_project_result(project_info, status))
        return

    if status in TERMINAL_FAIL:
        out({
            "Status": status,
            "ProjectId": project_id,
            "error": f"翻译任务失败，状态: {status}",
            "detail": project_info,
        })
        return

    if status in SUSPENDED:
        out({
            "Status": status,
            "ProjectId": project_id,
            "message": "翻译任务已暂停，等待人工干预。可通过 ContinueAITranslationWorkflow 恢复。",
            "detail": project_info,
        })
        return

    # 仍在处理中，开始轮询
    log(f"项目仍在处理中，开始持续轮询...")
    result = poll_translation_project(api, project_id, space_name)
    out(result)


if __name__ == "__main__":
    main()
