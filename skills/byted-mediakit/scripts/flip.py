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
flip.py — 视频翻转（上下/左右）

用法:
  python <SKILL_DIR>/scripts/flip.py '<json_args>'
  python <SKILL_DIR>/scripts/flip.py @params.json

json_args 字段见 references/03-flip.md
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vod_common import init_and_parse, fmt_src, out, bail

def main():
    client, sp, args = init_and_parse()

    t      = args.get("type", "vid")
    source = args.get("source")
    if not source:
        bail("flip: source 不能为空")
    param_obj = {
        "space_name": sp,
        "source": fmt_src(t, source),
        "flip_x": bool(args.get("flip_x", False)),
        "flip_y": bool(args.get("flip_y", False)),
    }
    out(client.submit_vcreative("loki://165221855", param_obj, sp))

if __name__ == "__main__":
    main()
