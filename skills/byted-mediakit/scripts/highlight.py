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
highlight.py — 提交短剧高光剪辑任务（StartExecution - Highlight）

基于大模型多模态高光提取算法，从短剧正片视频中智能提取最精彩的高光片段，
可生成单集摘要、剧集集锦、剧集宣传片等视频素材。

用法:
  python <SKILL_DIR>/scripts/highlight.py '<json_args>' [space_name]
  python <SKILL_DIR>/scripts/highlight.py @params.json [space_name]

JSON 参数说明:
  必选:
    Vids           — 视频 ID 列表（至少 1 个），如 ["v023xxx", "v024xxx"]
  可选:
    Model          — 模型，默认 "Miniseries"（短剧）
    Mode           — 模式，默认 "StorylineCuts"（剧情高光剪辑）
    WithStoryboard — 是否生成分镜脚本，默认 true
    WithOpeningHook— 是否生成开头钩子片段，默认 true

输出:
  成功: {"Status":"Success","RunId":"...","Meta":{...},"MultiInputs":[...]}
  失败: {"error":"..."}
  超时: {"error":"轮询超时...","resume_hint":{"command":"python .../poll_media.py highlight <RunId> <space>"}}
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vod_common import (
    init_and_parse,
    log,
    bail,
    out,
)


# ══════════════════════════════════════════════════════
# 默认配置
# ══════════════════════════════════════════════════════

DEFAULT_MODEL = "Miniseries"
DEFAULT_MODE = "StorylineCuts"
DEFAULT_WITH_STORYBOARD = True
DEFAULT_WITH_OPENING_HOOK = True

# 支持的模型
SUPPORTED_MODELS = {"Miniseries"}

# 支持的模式
SUPPORTED_MODES = {"StorylineCuts"}


# ══════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════

def main():
    api, space_name, args = init_and_parse(argv_pos=1)

    # ── 解析 Vids ──
    vids = args.get("Vids") or args.get("vids") or []
    # 兼容单个 vid 字符串
    if isinstance(vids, str):
        vids = [vids]
    if not vids:
        bail("必须提供 Vids 参数（视频 ID 列表），至少包含 1 个视频 ID")

    # ── 解析可选参数 ──
    model = args.get("Model", DEFAULT_MODEL)
    mode = args.get("Mode", DEFAULT_MODE)
    with_storyboard = args.get("WithStoryboard", DEFAULT_WITH_STORYBOARD)
    with_opening_hook = args.get("WithOpeningHook", DEFAULT_WITH_OPENING_HOOK)

    if model not in SUPPORTED_MODELS:
        bail(f"不支持的 Model: {model}。当前支持: {', '.join(sorted(SUPPORTED_MODELS))}")

    if mode not in SUPPORTED_MODES:
        bail(f"不支持的 Mode: {mode}。当前支持: {', '.join(sorted(SUPPORTED_MODES))}")

    duration = api.sum_media_info_list_duration_seconds(",".join(vids), space_name)
    if duration is None:
        bail("未找到媒资列表，请确认 Vids 及空间名称")

    # 如果 duration 大于 300，则 max_duration 为 180，否则 max_duration 为 60
    if duration > 300:
        max_duration = 180
    else:
        max_duration = 60

    # ── 构造 MultiInputs ──
    multi_inputs = []
    for vid in vids:
        if not vid:
            continue
        multi_inputs.append({
            "Type": "Vid",
            "Vid": vid,
        })

    if not multi_inputs:
        bail("Vids 列表中没有有效的视频 ID")

    # ── 构造请求体 ──
    params = {
        "SpaceName": space_name,
        "MultiInputs": multi_inputs,
        "Operation": {
            "Type": "Task",
            "Task": {
                "Type": "Highlight",
                "Highlight": {
                    "Model": model,
                    "Mode": mode,
                    "Edit": {
                        "Mode": "HighlightClips",
                    },
                    "HighlightCuts": {
                        "WithStoryboard": with_storyboard,
                        "MaxDuration": max_duration,
                    },
                    "OpeningHook": {
                        "WithOpeningHook": with_opening_hook,
                    },
                },
            },
        },
    }

    log(f"提交高光剪辑任务: {len(multi_inputs)} 个视频, Model={model}, Mode={mode}")

    # ── 提交并轮询 ──
    result = api.submit_media(params, "highlight", space_name)
    out(result)


if __name__ == "__main__":
    main()
