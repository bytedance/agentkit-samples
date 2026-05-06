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

"""AMK HTTP client: GET/POST/PUT/DELETE, streaming, AMK_ENV host selection."""

from amk_client.api_config import (
    PATH_PARAM_MODELS,
    ApiEntry,
    api_config,
    get_api_entry,
    path_placeholder_names,
    validate_and_format_path,
)
from amk_client.api_path_params import QueryTaskPathParams
from amk_client.api_request import (
    ApiRequest,
    AsyncApiRequest,
    concat_audio,
    concat_media_segments,
    concat_video,
    enhance_video,
    extract_audio,
    image_to_video,
    mux_audio_video,
    normalize_query_task_response,
    query_task,
    query_task_with_polling,
    trim_audio,
    trim_media_duration,
    trim_video,
    understand_video_content,
)
from amk_client.auth_mode import AmkAuthMode
from amk_client.models import (
    ConcatMediaKind,
    ConcatMediaSegmentsAsyncResult,
    ConcatMediaSegmentsRequest,
    ConcatMediaSegmentsResponse,
    EnhanceVideoRequest,
    ExtractAudioRequest,
    ImageToVideoImageItem,
    ImageToVideoRequest,
    MuxAudioVideoRequest,
    QueryTaskNormalizedResult,
    TaskStatusStr,
    TransitionId,
    TrimMediaDurationAsyncResult,
    TrimMediaDurationRequest,
    TrimMediaDurationResponse,
    TrimMediaKind,
)
from amk_client.client import AmkAsyncClient, AmkClient
from amk_client.config import (
    MissingConfigError,
    build_authorization_header,
    default_ark_api_key,
    default_bearer_token,
    normalize_secret,
    require_amk_api_key,
    require_ark_api_key,
    require_credentials_for_mode,
    resolve_base_url,
    resolve_default_auth_mode,
)

__all__ = [
    "AmkAuthMode",
    "AmkAsyncClient",
    "AmkClient",
    "ApiEntry",
    "AsyncApiRequest",
    "ApiRequest",
    "ConcatMediaKind",
    "ConcatMediaSegmentsAsyncResult",
    "concat_audio",
    "concat_media_segments",
    "concat_video",
    "ConcatMediaSegmentsRequest",
    "ConcatMediaSegmentsResponse",
    "EnhanceVideoRequest",
    "enhance_video",
    "ExtractAudioRequest",
    "ImageToVideoImageItem",
    "ImageToVideoRequest",
    "MuxAudioVideoRequest",
    "mux_audio_video",
    "normalize_query_task_response",
    "query_task",
    "query_task_with_polling",
    "QueryTaskNormalizedResult",
    "TaskStatusStr",
    "MissingConfigError",
    "PATH_PARAM_MODELS",
    "QueryTaskPathParams",
    "TrimMediaDurationAsyncResult",
    "TrimMediaDurationRequest",
    "TrimMediaDurationResponse",
    "trim_audio",
    "trim_media_duration",
    "trim_video",
    "TransitionId",
    "understand_video_content",
    "image_to_video",
    "extract_audio",
    "TrimMediaKind",
    "api_config",
    "build_authorization_header",
    "default_ark_api_key",
    "default_bearer_token",
    "get_api_entry",
    "normalize_secret",
    "path_placeholder_names",
    "require_amk_api_key",
    "require_ark_api_key",
    "require_credentials_for_mode",
    "resolve_base_url",
    "resolve_default_auth_mode",
    "validate_and_format_path",
]
