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
clipping.py — 视频/音频裁剪

用法:
  python <SKILL_DIR>/scripts/clipping.py '<json_args>'
  python <SKILL_DIR>/scripts/clipping.py @params.json

json_args 字段见 references/02-clipping.md
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vod_common import init_and_parse, fmt_src, out, bail

def main():
    client, sp, args = init_and_parse()

    t      = args.get("type", "video")
    source = args.get("source")
    if not source:
        bail("clipping: source 不能为空")
    start  = float(args.get("start_time", 0))
    end    = float(args.get("end_time", start + 1))
    if end <= start:
        bail("clipping: end_time 必须大于 start_time")

    param_obj = {
        "space_name": sp,
        "source":     fmt_src(t, source),
        "start_time": start,
        "end_time":   end,
    }
    wf = "loki://158666752" if t == "audio" else "loki://154419276"
    out(client.submit_vcreative(wf, param_obj, sp))

if __name__ == "__main__":
    main()
