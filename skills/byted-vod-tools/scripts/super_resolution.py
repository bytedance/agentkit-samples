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
super_resolution.py — AI 超分辨率

用法:
  python <SKILL_DIR>/scripts/super_resolution.py '<json_args>'
  python <SKILL_DIR>/scripts/super_resolution.py @params.json

json_args 字段见 references/13-super-resolution.md
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vod_common import init_and_parse, build_media_input, out, bail

VALID_RES = {"240p", "360p", "480p", "540p", "720p", "1080p", "2k", "4k"}


def main():
    client, sp, args = init_and_parse()

    t = args.get("type", "Vid")
    video = args.get("video")
    if not video:
        bail("super_resolution: video 不能为空")
    res = args.get("Res")
    res_limit = args.get("ResLimit")

    if res and res_limit is not None:
        bail("super_resolution: Res 和 ResLimit 不能同时指定")
    if not res and res_limit is None:
        bail("super_resolution: Res 或 ResLimit 必须指定一个")
    if res and res not in VALID_RES:
        bail(f"super_resolution: Res 必须为 {sorted(VALID_RES)} 之一，得到：{res!r}")
    if res_limit is not None and not (64 <= int(res_limit) <= 2160):
        bail("super_resolution: ResLimit 必须为 64～2160 之间的整数")

    target = {"Res": res} if res else {"ResLimit": int(res_limit)}
    params = {
        "Input": build_media_input(t, video, sp),
        "Operation": {
            "Type": "Task",
            "Task": {
                "Type": "Enhance",
                "Enhance": {
                    "Type": "Moe",
                    "MoeEnhance": {
                        "Config": "common",
                        "Target": target,
                        "VideoStrategy": {"RepairStyle": 1, "RepairStrength": 0},
                    },
                },
            },
        },
    }
    out(client.submit_media(params, "videSuperResolution", sp))


if __name__ == "__main__":
    main()
