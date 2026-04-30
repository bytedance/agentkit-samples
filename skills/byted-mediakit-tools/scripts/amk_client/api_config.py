"""AMK HTTP API 注册表：路径、方法、鉴权模式。"""

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

from __future__ import annotations

import re
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict

from amk_client.api_path_params import QueryTaskPathParams
from amk_client.auth_mode import AmkAuthMode

HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH"]

_PATH_PLACEHOLDERS = re.compile(r"\{(\w+)\}")


class ApiEntry(BaseModel):
    """单条 API 配置（不可变）。"""

    model_config = ConfigDict(frozen=True)

    action: str
    auth_mode: AmkAuthMode
    method: HttpMethod = "POST"


# api_name -> 路径参数模型（无路径占位符的 API 不必注册）
PATH_PARAM_MODELS: dict[str, type[BaseModel]] = {
    "query_task": QueryTaskPathParams,
}


api_config: dict[str, ApiEntry] = {
    "understand_video_content": ApiEntry(
        action="/api/v1/chat/completions",
        auth_mode=AmkAuthMode.ARK_AND_MEDIAKIT,
        method="POST",
    ),
    "trim_audio": ApiEntry(
        action="/api/v1/tools/trim-audio",
        auth_mode=AmkAuthMode.MEDIAKIT_ONLY,
        method="POST",
    ),
    "trim_video": ApiEntry(
        action="/api/v1/tools/trim-video",
        auth_mode=AmkAuthMode.MEDIAKIT_ONLY,
        method="POST",
    ),
    # 调用节点聚合：统一由 concat_media_segments(type=audio|video) 分发到底层 concat_* API
    "concat_audio": ApiEntry(
        action="/api/v1/tools/concat-audio",
        auth_mode=AmkAuthMode.MEDIAKIT_ONLY,
        method="POST",
    ),
    "concat_video": ApiEntry(
        action="/api/v1/tools/concat-video",
        auth_mode=AmkAuthMode.MEDIAKIT_ONLY,
        method="POST",
    ),
    "mux_audio_video": ApiEntry(
        action="/api/v1/tools/mux-audio-video",
        auth_mode=AmkAuthMode.MEDIAKIT_ONLY,
        method="POST",
    ),
    "image_to_video": ApiEntry(
        action="/api/v1/tools/image-to-video",
        auth_mode=AmkAuthMode.MEDIAKIT_ONLY,
        method="POST",
    ),
    "extract_audio": ApiEntry(
        action="/api/v1/tools/extract-audio",
        auth_mode=AmkAuthMode.MEDIAKIT_ONLY,
        method="POST",
    ),
    "enhance_video": ApiEntry(
        action="/api/v1/tools/enhance-video",
        auth_mode=AmkAuthMode.MEDIAKIT_ONLY,
        method="POST",
    ),
    "query_task": ApiEntry(
        action="/api/v1/tasks/{task_id}",
        auth_mode=AmkAuthMode.MEDIAKIT_ONLY,
        method="GET",
    ),
}


def get_api_entry(name: str) -> ApiEntry:
    """按注册名取配置；未知名称抛 ``KeyError``。"""
    return api_config[name]


def path_placeholder_names(action: str) -> tuple[str, ...]:
    return tuple(_PATH_PLACEHOLDERS.findall(action))


def validate_and_format_path(
    api_name: str,
    entry: ApiEntry,
    path_params: Mapping[str, Any] | BaseModel | None,
) -> str:
    """用 Pydantic 校验路径参数（若已注册模型），再 ``str.format`` 生成最终 path。"""
    names = path_placeholder_names(entry.action)
    if not names:
        if path_params:
            raise ValueError(
                f"API {api_name!r} 的 action 无路径占位符，不应传入 path_params: {path_params!r}"
            )
        return entry.action

    raw: Mapping[str, Any]
    if path_params is None:
        raw = {}
    elif isinstance(path_params, BaseModel):
        raw = path_params.model_dump()
    else:
        raw = path_params

    model_cls = PATH_PARAM_MODELS.get(api_name)
    if model_cls is not None:
        data = model_cls.model_validate(raw).model_dump()
    else:
        data = dict(raw)

    missing = [n for n in names if n not in data]
    if missing:
        raise ValueError(
            f"API {api_name!r} 缺少路径参数: {missing}；已注册模型时可自动校验类型与约束"
        )

    return entry.action.format(**{n: str(data[n]) for n in names})
