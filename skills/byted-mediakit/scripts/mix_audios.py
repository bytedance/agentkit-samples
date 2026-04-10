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
mix_audios.py — 多轨混音

用法:
  python <SKILL_DIR>/scripts/mix_audios.py '<json_args>'
  python <SKILL_DIR>/scripts/mix_audios.py @params.json

json_args 字段见 references/08-mix-audios.md
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vod_common import init_and_parse, fmt_src, out, bail

def main():
    client, sp, args = init_and_parse()

    audios = args.get("audios")
    if not audios:
        bail("mix_audios: audios 不能为空")
    formatted = []
    for a in audios:
        at  = a.get("type", "vid")
        as_ = a.get("source", "")
        formatted.append(fmt_src(at, as_) if at in ("vid", "directurl") else as_)

    param_obj = {"space_name": sp, "audios": formatted}
    out(client.submit_vcreative("loki://167987532", param_obj, sp))

if __name__ == "__main__":
    main()
