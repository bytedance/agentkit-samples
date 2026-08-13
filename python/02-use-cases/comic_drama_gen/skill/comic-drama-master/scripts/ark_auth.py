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
Ark 模型调用鉴权工具。

Function Purpose:
    为漫剧 Skill 中所有直连 Ark SDK/HTTP 的脚本提供统一鉴权入口。

Implementation Logic:
    1. 优先读取显式配置的 API Key，兼容本地调试与历史环境变量。
    2. 当 API Key 缺省时，调用 VeADK 的 get_ark_token()，使用云端运行时身份兜底。
    3. 对外分别提供原始 token 和 HTTP Authorization header，避免各脚本重复拼装。
"""

from __future__ import annotations

import os
from collections.abc import Iterable

_COMMON_ARK_KEY_ENV_NAMES = (
    "ARK_API_KEY",
    "MODEL_AGENT_API_KEY",
)


def _iter_env_names(service_env_names: Iterable[str] = ()) -> tuple[str, ...]:
    """
    Function Purpose:
        合并服务专用环境变量和通用 Ark 环境变量，并保持顺序去重。

    Implementation Logic:
        1. 服务专用变量放在前面，例如 MODEL_IMAGE_API_KEY 或 MODEL_VIDEO_API_KEY。
        2. 通用变量放在后面，保证历史配置仍可使用。
        3. 使用 seen 集合去重，避免重复读取同一个变量。
    """
    seen = set()
    names = []
    for name in (*service_env_names, *_COMMON_ARK_KEY_ENV_NAMES):
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return tuple(names)


def get_ark_api_key(*service_env_names: str) -> str:
    """
    Function Purpose:
        获取可用于 Ark SDK 或 OpenAI 兼容接口的 Bearer token。

    Implementation Logic:
        1. 按顺序读取服务专用 API Key 与通用 API Key 环境变量。
        2. 若环境变量为空，则导入并调用 veadk.auth.veauth.ark_veauth.get_ark_token。
        3. 如果两条路径都失败，抛出 RuntimeError，提示本地配置或云端身份授权问题。
    """
    for env_name in _iter_env_names(service_env_names):
        api_key = os.getenv(env_name)
        if api_key:
            return api_key

    try:
        from veadk.auth.veauth.ark_veauth import get_ark_token

        token = get_ark_token()
    except Exception as exc:
        raise RuntimeError(
            "Ark credential is empty. Please set ARK_API_KEY or MODEL_AGENT_API_KEY "
            "for local debugging, or deploy with AgentKit/VeADK cloud identity enabled."
        ) from exc

    if not token:
        raise RuntimeError(
            "Ark credential is empty. Please set ARK_API_KEY or MODEL_AGENT_API_KEY "
            "for local debugging, or deploy with AgentKit/VeADK cloud identity enabled."
        )
    return token


def get_ark_authorization(*service_env_names: str) -> str:
    """
    Function Purpose:
        生成 Ark HTTP API 所需的 Authorization header 值。

    Implementation Logic:
        1. 复用 get_ark_api_key 获取本地 API Key 或云端身份 token。
        2. 按 Ark HTTP API 约定拼接 Bearer token。
    """
    return f"Bearer {get_ark_api_key(*service_env_names)}"
