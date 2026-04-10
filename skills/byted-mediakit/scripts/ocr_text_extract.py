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
ocr_text_extract.py — 画面文字提取 (OCR)

用法:
  python <SKILL_DIR>/scripts/ocr_text_extract.py '<json_args>'
  python <SKILL_DIR>/scripts/ocr_text_extract.py @params.json

json_args 字段见 references/16-ocr-text-extract.md
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vod_common import init_and_parse, build_media_input, out, bail

def main():
    client, sp, args = init_and_parse()

    t     = args.get("type", "Vid")
    video = args.get("video")
    if not video:
        bail("ocr_text_extract: video 不能为空")

    params = {
        "Input": build_media_input(t, video, sp),
        "Operation": {
            "Type": "Task",
            "Task": {
                "Type": "Ocr",
                "Ocr":  {},
            },
        },
    }
    out(client.submit_media(params, "ocr", sp))

if __name__ == "__main__":
    main()
