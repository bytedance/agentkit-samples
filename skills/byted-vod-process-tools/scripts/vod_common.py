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
vod_common.py — 公共基础模块（被各工具脚本 import）

仅保留与接口调用无关的公共函数：
  - init_and_parse()    统一入口：解析 JSON 参数 + 初始化 ApiManage
  - get_space_name()    space_name 读取
  - fmt_src()           为 vid/directurl 添加协议前缀
  - build_media_input() 构建 SkillStartExecution 的 Input 字段
  - log() / bail() / out()  日志与输出（re-export from log_utils）
"""

import sys
import os
import json

from log_utils import bail  # 从独立模块导入，避免循环引用
from api_manage import ApiManage


# ══════════════════════════════════════════════════════
# 轮询配置常量（保留以供 upload_media.py 等直接引用）
# ══════════════════════════════════════════════════════

POLL_INTERVAL = float(os.environ.get("VOD_POLL_INTERVAL", "5"))
POLL_MAX = int(os.environ.get("VOD_POLL_MAX", "360"))  # 360×5s = 30 分钟


# ══════════════════════════════════════════════════════
# space_name 读取
# ══════════════════════════════════════════════════════


def get_space_name(argv_pos: int = 3) -> str:
    """
    space_name 读取优先级：
      1. 命令行第 argv_pos 个参数
      2. VOLC_SPACE_NAME 环境变量
      3. SPACE_NAME / VOD_SPACE_NAME 环境变量
    """
    if len(sys.argv) > argv_pos:
        return sys.argv[argv_pos]
    sp = os.environ.get("VOLC_SPACE_NAME", "")
    if not sp:
        sp = os.environ.get("SPACE_NAME", "")
    if not sp:
        sp = os.environ.get("VOD_SPACE_NAME", "")
    if not sp:
        bail(
            "未指定 space_name：请通过命令行参数或环境变量 VOD_SPACE_NAME / VOLC_SPACE_NAME 提供。"
        )
    return sp


# ══════════════════════════════════════════════════════
# 统一入口：JSON 参数解析 + ApiManage 初始化
# ══════════════════════════════════════════════════════


def init_and_parse(argv_pos: int = 1, sp_pos: int = None):
    """
    统一前置流程，返回 (api, space_name, args_dict)。

    - argv_pos:  sys.argv 中 JSON 参数的位置（默认 1）
    - sp_pos:    sys.argv 中 space_name 的位置（默认 argv_pos + 1）

    返回的 api 为 ApiManage 实例。
    """
    if len(sys.argv) < argv_pos + 1:
        bail(f"用法: python {sys.argv[0]} '<json_args>'")

    raw = sys.argv[argv_pos]
    # 支持 @file.json 语法
    if raw.startswith("@"):
        fpath = raw[1:]
        if not os.path.isfile(fpath):
            bail(f"参数文件不存在：{fpath}")
        with open(fpath, "r", encoding="utf-8") as f:
            raw = f.read()

    try:
        args = json.loads(raw)
    except json.JSONDecodeError as e:
        bail(f"json_args 解析失败: {e}")

    api = ApiManage()
    sp = get_space_name(argv_pos=sp_pos if sp_pos is not None else argv_pos + 1)
    return api, sp, args


# ══════════════════════════════════════════════════════
# 格式化工具
# ══════════════════════════════════════════════════════


def fmt_src(type_: str, source: str) -> str:
    """为 vid/directurl 类型自动添加协议前缀"""
    return ApiManage._format_source(type_, source)


def build_media_input(type_: str, source: str, space_name: str) -> dict:
    """
    构建 SkillStartExecution 的 Input 字段。
    委托给 ApiManage._build_media_input。
    """
    if type_ not in ("Vid", "DirectUrl"):
        bail(f"type 必须为 Vid 或 DirectUrl，得到：{type_!r}")
    if not source:
        bail("media source 不能为空")
    if not space_name:
        bail("space_name 不能为空")
    return ApiManage._build_media_input(type_, source, space_name)
