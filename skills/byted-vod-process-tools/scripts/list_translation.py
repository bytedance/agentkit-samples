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
list_translation.py — 查询 AI 视频翻译项目列表（ListAITranslationProject）

用法:
  python <SKILL_DIR>/scripts/list_translation.py [space_name] [options_json]

  options_json 可选参数（JSON 格式）:
    PageNumber      — 页码，默认 1
    PageSize        — 每页数量，默认 10
    StatusFilter    — 状态过滤（逗号分隔），如 "InProcessing,ProcessSucceed"
    ProjectIdOrTitleFilter — 按项目 ID 或名称过滤

示例:
  # 查看所有项目（默认空间）
  python <SKILL_DIR>/scripts/list_translation.py

  # 带空间名
  python <SKILL_DIR>/scripts/list_translation.py my_space

  # 带过滤条件
  python <SKILL_DIR>/scripts/list_translation.py my_space '{"StatusFilter":"ProcessSucceed","PageSize":5}'

输出:
  {"Projects":[{...},...], "Total": N, "PageNumber": 1, "PageSize": 10}
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_manage import ApiManage
from vod_common import (
    get_space_name,
    log,
    bail,
    out,
)


def main():
    api = ApiManage()

    # space_name: argv[1] 或环境变量
    space_name = get_space_name(argv_pos=1)

    # 可选的 options JSON: argv[2]
    options = {}
    if len(sys.argv) > 2:
        raw = sys.argv[2]
        if raw.startswith("@"):
            fpath = raw[1:]
            if not os.path.isfile(fpath):
                bail(f"参数文件不存在：{fpath}")
            with open(fpath, "r", encoding="utf-8") as f:
                raw = f.read()
        try:
            options = json.loads(raw)
        except json.JSONDecodeError as e:
            bail(f"options JSON 解析失败: {e}")

    # 构造查询参数
    params = {
        "SpaceName": space_name,
    }

    page_number = options.get("PageNumber", 1)
    page_size = options.get("PageSize", 10)
    params["PageNumber"] = page_number
    params["PageSize"] = page_size

    status_filter = options.get("StatusFilter", "")
    if status_filter:
        params["StatusFilter"] = status_filter

    project_filter = options.get("ProjectIdOrTitleFilter", "")
    if project_filter:
        params["ProjectIdOrTitleFilter"] = project_filter

    # 调用接口
    log(
        f"查询翻译项目列表: SpaceName={space_name}, Page={page_number}, Size={page_size}"
    )
    try:
        raw = api.list_ai_translation_project(params)
    except Exception as e:
        bail(f"查询翻译项目列表失败: {e}")

    if isinstance(raw, str):
        raw = json.loads(raw)

    # 检查错误
    resp_meta = raw.get("ResponseMetadata", {})
    error = resp_meta.get("Error", {})
    if error and error.get("Code"):
        bail(f"API 错误: Code={error.get('Code')}, Message={error.get('Message', '')}")

    result = raw.get("Result", raw)
    projects = result.get("Projects", [])

    # 格式化输出
    formatted_projects = []
    for p in projects:
        input_video = p.get("InputVideo") or {}
        output_video = p.get("OutputVideo") or {}
        formatted_projects.append(
            {
                "ProjectId": p.get("ProjectId", ""),
                "Status": p.get("Status", ""),
                "InputVideoTitle": p.get("InputVideoTitle", ""),
                "TranslationTypeList": p.get("TranslationTypeList", []),
                "CreatedAt": p.get("CreatedAt", ""),
                "UpdatedAt": p.get("UpdatedAt", ""),
                "InputVideo": {
                    "Vid": input_video.get("Vid", ""),
                    "Duration": input_video.get("DurationSecond", 0),
                    "Url": input_video.get("Url", ""),
                },
                "OutputVideo": {
                    "Vid": output_video.get("Vid", ""),
                    "Duration": output_video.get("DurationSecond", 0),
                    "Url": output_video.get("Url", ""),
                },
            }
        )

    out(
        {
            "Projects": formatted_projects,
            "Total": len(formatted_projects),
            "PageNumber": page_number,
            "PageSize": page_size,
        }
    )


if __name__ == "__main__":
    main()
