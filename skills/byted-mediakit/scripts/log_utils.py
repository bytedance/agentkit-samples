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
log_utils.py — 零依赖的日志/错误工具函数。

从 vod_common.py 中提取，用于打破以下循环引用：
  api_manage -> vod_transport -> vod_common -> api_manage

本模块不 import 项目内其他模块，可被任意模块安全导入。
"""

import sys
import json
import time


def log(msg: str):
    """输出带时间戳的日志到 stderr。"""
    print(f"[info] {time.strftime('%Y-%m-%d %H:%M:%S')} {msg}", file=sys.stderr, flush=True)


def bail(msg: str):
    """输出 JSON 格式的错误信息到 stdout 并退出。"""
    print(json.dumps({"error": f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"}, ensure_ascii=False))
    sys.exit(1)


def out(data):
    """输出 JSON 或字符串到 stdout。"""
    print(json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data)
