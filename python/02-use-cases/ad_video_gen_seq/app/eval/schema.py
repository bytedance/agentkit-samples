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

from typing import Optional

from google.genai import types
from pydantic import BaseModel, Field

json_response_config = types.GenerateContentConfig(
    response_mime_type="application/json", max_output_tokens=18000
)

max_output_tokens_config = types.GenerateContentConfig(max_output_tokens=18000)


class Status(BaseModel):
    """A status."""

    success: bool = Field(description="如果结果成功则为True，否则为False")
    message: str = Field(description="运行成功该字段为空，否则为错误信息")


class ImageItem(BaseModel):
    """An image."""

    id: int = Field(description="The shot id of the image")
    code: str = Field(description="The code of the image")
    score: float = Field(description="The score of the image")
    reason: str = Field(description="The reason for the score")


class Image(BaseModel):
    """Image list for a shot."""

    shot_id: str = Field(description="The shot id")
    prompt: str = Field(description="The description for generating image")
    action: str = Field(description="The description for generating videos")
    reference: str = Field(description="The reference url for the shot")
    images: list[ImageItem] = Field(description="The list of images")


class ScoredImageList(BaseModel):
    """Image list."""

    scored_image_list: list[Image] = Field(description="The list of images")
    status: Optional[Status] = Field(description="The status of the result")


class VideoItem(BaseModel):
    """A video."""

    id: int = Field(description="The shot id of the video")
    code: str = Field(description="The code of the video")
    score: float = Field(description="The score of the video")
    reason: str = Field(description="The reason for the score")


class Video(BaseModel):
    """Video list for a shot."""

    shot_id: str = Field(description="The shot id")
    prompt: str = Field(description="The description for generating image")
    action: str = Field(description="The description for generating videos")
    reference: str = Field(description="The reference url for the shot")
    videos: list[VideoItem] = Field(description="The list of videos")


class ScoredVideoList(BaseModel):
    """Video list."""

    scored_video_list: list[Video] = Field(description="The list of videos")
    status: Optional[Status] = Field(description="The status of the result")


class EvaluationResult(BaseModel):
    shot_id: str = Field(..., description="镜头编号")
    media_id: str = Field(..., description="媒体编号")
    reason: str = Field(..., description="评分理由")
    scores: float = Field(..., description="综合评分")


class EvaluationList(BaseModel):
    evaluation: EvaluationResult = Field(..., description="评估结果列表")
