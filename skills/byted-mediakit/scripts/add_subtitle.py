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
add_subtitle.py — 添加内嵌字幕

用法:
  python <SKILL_DIR>/scripts/add_subtitle.py '<json_args>'
  python <SKILL_DIR>/scripts/add_subtitle.py @params.json

json_args 字段见 references/18-add-subtitle.md
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vod_common import init_and_parse, fmt_src, out, bail

def main():
    client, sp, args = init_and_parse()

    # ── 视频参数 ──
    video = args.get("video")
    if not video:
        bail("add_subtitle: video 不能为空")
    vt = video.get("type", "vid")
    vs = video.get("source", "")
    formatted_video = fmt_src(vt, vs) if vt in ("vid", "directurl") else vs

    # ── 字幕来源（二选一，subtitle_url 优先） ──
    subtitle_url = args.get("subtitle_url")
    text_list    = args.get("text_list")
    if not subtitle_url and not text_list:
        bail("add_subtitle: 必须指定 subtitle_url 或 text_list 中的一个")

    param_obj = {
        "space_name": sp,
        "video":      formatted_video,
    }
    if subtitle_url:
        param_obj["subtitle_url"] = subtitle_url
    elif text_list:
        param_obj["text_list"] = text_list

    # ── 字幕样式配置（可选） ──
    subtitle_config = args.get("subtitle_config")
    if subtitle_config:
        param_obj["subtitle_config"] = subtitle_config

    out(client.submit_vcreative("loki://168214785", param_obj, sp))

if __name__ == "__main__":
    main()
