"""AMK 相关 Pydantic 模型（请求体、响应体、路径参数等，随 API 扩展）。"""

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

from typing import Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
)

TrimMediaKind = Literal["audio", "video"]


class TrimMediaDurationRequest(BaseModel):
    """``POST /api/v1/tools/trim_media_duration`` 请求体。

    Args:
        type (str): **必选字段**，裁剪类型。``audio`` | ``video``。
        source (str): **必选字段**，待剪切的资源 URL，支持 ``http://`` 或 ``https://`` 格式。
        start_time (int | float): **非必选字段**，裁剪开始时间，默认为 ``0``，表示从头开始裁剪；
            最多保留 2 位小数，单位：秒。
        end_time (int | float | None): **非必选字段**，裁剪结束时间，默认为片源结尾；
            最多保留 2 位小数，单位：秒；省略或 ``null`` 表示至片尾。
    """

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    type: TrimMediaKind = Field(
        ...,
        description="裁剪类型（与调用侧聚合节点一致）：audio | video",
    )
    source: str = Field(..., min_length=1, description="待裁剪资源 URL")
    start_time: float = Field(
        default=0.0, ge=0, description="裁剪开始时间（秒），默认从头"
    )
    end_time: float | None = Field(
        default=None,
        ge=0,
        description="裁剪结束时间（秒），省略表示至片源结尾",
    )

    @field_validator("type", mode="before")
    @classmethod
    def type_must_be_audio_or_video_str(cls, v: Any) -> Any:
        if v is None:
            raise ValueError('type 不能为空；须为字符串 "audio" 或 "video"')
        if not isinstance(v, str):
            raise ValueError(
                f'type 须为字符串类型（取值 "audio" | "video"），当前为 {type(v).__name__}'
            )
        return v

    @field_validator("source", mode="before")
    @classmethod
    def source_must_be_str(cls, v: Any) -> Any:
        if v is None:
            raise ValueError(
                "source 不能为空；须为字符串类型，且为 http:// 或 https:// 开头的资源 URL"
            )
        if not isinstance(v, str):
            raise ValueError(
                f"source 须为字符串类型（资源 URL），当前为 {type(v).__name__}；"
                "若为多段资源请使用对应接口的数组字段，勿把列表误传到 source"
            )
        return v

    @field_validator("source")
    @classmethod
    def source_must_be_http(cls, v: str) -> str:
        s = v.strip()
        if not (s.startswith("http://") or s.startswith("https://")):
            raise ValueError("source 须为 http:// 或 https:// 开头的 URL 字符串")
        return s

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def time_fields_must_be_number_or_omit(cls, v: Any, info: ValidationInfo) -> Any:
        field = info.field_name
        if v is None:
            if field == "end_time":
                return None
            raise ValueError(
                "start_time 不能为空（勿传 null）；须为数字类型（秒，≥0），"
                "若从片头开始请省略该字段或传 0"
            )
        if not isinstance(v, (int, float)):
            raise ValueError(f"{field} 须为数字类型（秒），当前为 {type(v).__name__}")
        return v

    @field_validator("start_time", "end_time")
    @classmethod
    def at_most_two_decimal_places(cls, v: float | None) -> float | None:
        if v is None:
            return v
        text = f"{v:.4f}".rstrip("0").rstrip(".")
        if "." in text:
            _, frac = text.split(".", 1)
            if len(frac) > 2:
                raise ValueError("时间最多保留 2 位小数（单位：秒）")
        return v

    def to_api_json(self) -> dict[str, Any]:
        """发给网关的 JSON：省略 ``end_time`` 表示默认到片尾。"""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class TrimMediaDurationResponse(BaseModel):
    """``trim_media_duration`` 返回中的任务信息。

    Returns:
        task_id: 任务查询 id。
        request_id: 日志 id（兼容历史网关字段名 ``requst_id``）。
    """

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    task_id: str = Field(..., description="任务查询 id")
    request_id: str = Field(
        ...,
        validation_alias=AliasChoices("request_id", "requst_id"),
        description="日志 id",
    )

    @field_validator("task_id", "request_id", mode="before")
    @classmethod
    def response_string_ids(cls, v: Any, info: ValidationInfo) -> Any:
        name = info.field_name
        if v is None:
            raise ValueError(f"{name} 不能为空；解析响应时期望非空字符串")
        if not isinstance(v, str):
            raise ValueError(f"{name} 须为字符串类型，当前为 {type(v).__name__}")
        return v


class TrimMediaDurationAsyncResult(BaseModel):
    """调用节点聚合接口的异步返回结构。"""

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    task_id: str | None = Field(default=None, description="任务查询 id")
    request_id: str | None = Field(default=None, description="日志 id")
    error: str | None = Field(default=None, description="报错信息")


ConcatMediaKind = Literal["audio", "video"]
TransitionId = Literal[
    "1182359",
    "1182360",
    "1182358",
    "1182365",
    "1182367",
    "1182368",
    "1182369",
    "1182370",
    "1182373",
    "1182374",
    "1182375",
    "1182378",
]


class ConcatMediaSegmentsRequest(BaseModel):
    """调用层聚合接口 ``concat_media_segments`` 请求体。"""

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    type: ConcatMediaKind = Field(
        ...,
        description="必选，拼接类型：audio | video",
    )
    sources: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="必选，待拼接资源 URL 列表（http:// 或 https://）",
    )
    transitions: list[TransitionId] | None = Field(
        default=None,
        description="可选，转场效果 ID 列表；音频拼接不支持",
    )

    @field_validator("sources", mode="before")
    @classmethod
    def sources_must_be_string_list(cls, v: Any) -> Any:
        if not isinstance(v, list):
            raise ValueError("sources 须为字符串 URL 列表")
        if not v:
            raise ValueError("sources 不能为空；至少提供 1 个资源 URL")
        return v

    @field_validator("sources")
    @classmethod
    def sources_each_must_be_http_url(cls, values: list[str]) -> list[str]:
        for idx, item in enumerate(values):
            if not isinstance(item, str):
                raise ValueError(f"sources[{idx}] 须为字符串 URL")
            s = item.strip()
            if not (s.startswith("http://") or s.startswith("https://")):
                raise ValueError(f"sources[{idx}] 须为 http:// 或 https:// 开头的 URL")
        return values

    @field_validator("transitions", mode="before")
    @classmethod
    def transitions_must_be_string_list_or_none(cls, v: Any) -> Any:
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("transitions 须为字符串列表或省略")
        for idx, item in enumerate(v):
            if not isinstance(item, str):
                raise ValueError(f"transitions[{idx}] 须为字符串转场 ID")
        return v

    @field_validator("transitions")
    @classmethod
    def audio_should_not_pass_transitions(
        cls, v: list[str] | None, info: ValidationInfo
    ) -> list[str] | None:
        media_type = info.data.get("type")
        if media_type == "audio" and v:
            raise ValueError("音频拼接不支持 transitions，请不要传该字段")
        return v

    def to_api_json(self) -> dict[str, Any]:
        """发给底层 API 的 JSON；不必要字段自动省略。"""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class ConcatMediaSegmentsResponse(BaseModel):
    """``concat_media_segments`` 聚合后的任务返回。"""

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    task_id: str = Field(..., description="任务查询 id")
    request_id: str = Field(
        ...,
        validation_alias=AliasChoices("request_id", "requst_id"),
        description="日志 id",
    )


class ConcatMediaSegmentsAsyncResult(BaseModel):
    """调用层聚合方法的异步返回结构。"""

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    task_id: str | None = Field(default=None, description="任务查询 id")
    request_id: str | None = Field(default=None, description="日志 id")
    error: str | None = Field(default=None, description="报错信息")


class MuxAudioVideoRequest(BaseModel):
    """``mux_audio_video`` 请求体。"""

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    video_url: str = Field(..., description="输入视频 URL")
    audio_url: str = Field(..., description="输入音频 URL")
    is_audio_reserve: bool = Field(default=True, description="是否保留原视频音频")
    is_video_audio_sync: bool = Field(default=False, description="是否对齐音视频时长")
    sync_mode: Literal["video", "audio"] = Field(
        default="video", description="对齐基准"
    )
    sync_method: Literal["speed", "trim"] = Field(
        default="trim", description="对齐方式"
    )


class ImageToVideoImageItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    image_url: str = Field(..., description="图片 URL")
    duration: float | None = Field(default=3.0, ge=0, description="播放时长（秒）")
    animation_type: (
        Literal[
            "move_up", "move_down", "move_left", "move_right", "zoom_in", "zoom_out"
        ]
        | None
    ) = Field(default=None, description="动画类型")
    animation_in: float | None = Field(
        default=None, ge=0, description="动画开始时间（秒）"
    )
    animation_out: float | None = Field(
        default=None, ge=0, description="动画结束时间（秒）"
    )


class ImageToVideoRequest(BaseModel):
    """``image_to_video`` 请求体。"""

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    images: list[ImageToVideoImageItem] = Field(..., min_length=1, max_length=100)
    transitions: list[TransitionId] | None = Field(
        default=None, description="可选转场效果 ID"
    )


class ExtractAudioRequest(BaseModel):
    """``extract_audio`` 请求体。"""

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    video_url: str = Field(..., description="输入视频 URL")
    format: Literal["mp3", "m4a"] = Field(default="m4a", description="输出音频格式")


class EnhanceVideoRequest(BaseModel):
    """``enhance_video`` 请求体。"""

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    video_url: str = Field(..., description="输入视频 URL")
    tool_version: Literal["standard", "professional"] = Field(
        default="standard",
        description="工具版本：standard 标准版，professional 专业版",
    )
    resolution: (
        Literal["240p", "360p", "480p", "540p", "720p", "1080p", "2k", "4k"] | None
    ) = Field(
        default=None,
        description="目标分辨率；不传/不填写则使用原始分辨率（后端按原分辨率处理）",
    )
    resolution_limit: int | None = Field(
        default=None, ge=64, le=2160, description="目标长宽限制"
    )
    fps: float | None = Field(default=None, gt=0, le=120, description="目标帧率")


TaskStatusStr = Literal["running", "completed", "queued", "failed", "canceled"]


class QueryTaskNormalizedResult(BaseModel):
    """任务查询的标准化返回结构。"""

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    task_id: str | None = Field(default=None, description="任务查询 ID")
    duration: float | None = Field(default=None, description="时长（秒）")
    play_url: str | None = Field(default=None, description="播放地址")
    request_id: str | None = Field(default=None, description="日志 id")
    status: TaskStatusStr = Field(..., description="任务状态")
    task_type: str | None = Field(default=None, description="任务类型")
