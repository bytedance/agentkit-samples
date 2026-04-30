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
image_to_video.py — 图片转视频

用法:
  python <SKILL_DIR>/scripts/image_to_video.py '<json_args>'
  python <SKILL_DIR>/scripts/image_to_video.py @params.json

json_args 字段见 references/05-image-to-video.md
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vod_common import init_and_parse, fmt_src, out, bail


def main():
    client, sp, args = init_and_parse()

    images = args.get("images")
    if not images:
        bail("image_to_video: images 不能为空")
    formatted = []
    for img in images:
        it = img.get("type", "vid")
        isrc = img.get("source", "")
        item = {
            "type": it,
            "source": fmt_src(it, isrc) if it in ("vid", "directurl") else isrc,
        }
        for k in ("duration", "animation_type", "animation_in", "animation_out"):
            if k in img:
                item[k] = img[k]
        formatted.append(item)

    param_obj = {
        "space_name": sp,
        "images": formatted,
        "transitions": args.get("transitions") or [],
    }
    out(client.submit_vcreative("loki://167979998", param_obj, sp))


if __name__ == "__main__":
    main()
