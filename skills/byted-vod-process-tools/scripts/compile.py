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
compile.py — 音视频合成（替换/叠加背景音）

用法:
  python <SKILL_DIR>/scripts/compile.py '<json_args>'
  python <SKILL_DIR>/scripts/compile.py @params.json

json_args 字段见 references/06-compile.md
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vod_common import init_and_parse, fmt_src, out, bail


def main():
    client, sp, args = init_and_parse()

    video = args.get("video")
    if not video:
        bail("compile: video 不能为空")
    audio = args.get("audio")
    if not audio:
        bail("compile: audio 不能为空")
    vt, vs = video.get("type", "vid"), video.get("source", "")
    at, as_ = audio.get("type", "vid"), audio.get("source", "")

    param_obj = {
        "space_name": sp,
        "video": fmt_src(vt, vs) if vt in ("vid", "directurl") else vs,
        "audio": fmt_src(at, as_) if at in ("vid", "directurl") else as_,
        "is_audio_reserve": bool(args.get("is_audio_reserve", True)),
        "is_video_audio_sync": bool(args.get("is_video_audio_sync", False)),
    }
    if param_obj["is_video_audio_sync"]:
        param_obj["sync_mode"] = args.get("sync_mode", "video")
        param_obj["sync_method"] = args.get("sync_method", "trim")

    out(client.submit_vcreative("loki://167984726", param_obj, sp))


if __name__ == "__main__":
    main()
