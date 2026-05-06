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

"""按 ``api_config`` 发起请求；路径参数经 Pydantic 校验。"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Any, Mapping

import httpx
from pydantic import BaseModel

from amk_client.api_config import get_api_entry, validate_and_format_path
from amk_client.client import AmkAsyncClient, AmkClient
from amk_client.config import MissingConfigError, normalize_secret
from amk_client.models import (
    ConcatMediaSegmentsAsyncResult,
    ConcatMediaSegmentsRequest,
    ConcatMediaSegmentsResponse,
    EnhanceVideoRequest,
    ExtractAudioRequest,
    ImageToVideoRequest,
    MuxAudioVideoRequest,
    QueryTaskNormalizedResult,
    TaskStatusStr,
    TrimMediaDurationAsyncResult,
    TrimMediaDurationRequest,
    TrimMediaDurationResponse,
)


class ApiRequest:
    """封装单个注册 API：路径参数校验 + 按配置的 method/auth_mode 调用 ``AmkClient``。"""

    def __init__(self, api_name: str, *, client: AmkClient | None = None) -> None:
        self.api_name = api_name
        self.entry = get_api_entry(api_name)
        self.client = client if client is not None else AmkClient()

    def build_path(
        self,
        path_params: Mapping[str, Any] | BaseModel | None = None,
    ) -> str:
        return validate_and_format_path(self.api_name, self.entry, path_params)

    def request(
        self,
        *,
        path_params: Mapping[str, Any] | BaseModel | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        path = self.build_path(path_params)
        method = self.entry.method.upper()
        auth_mode = self.entry.auth_mode
        force_new_client_token = bool(kwargs.pop("force_new_client_token", False))
        kwargs = _inject_client_token_if_needed(
            self.api_name, kwargs, force_new_client_token=force_new_client_token
        )
        if method in ("GET", "POST", "PUT", "DELETE"):
            return getattr(self.client, method.lower())(
                path, auth_mode=auth_mode, **kwargs
            )
        return self.client.request(method, path, auth_mode=auth_mode, **kwargs)


class AsyncApiRequest:
    """异步版 API 调用封装。"""

    def __init__(self, api_name: str, *, client: AmkAsyncClient | None = None) -> None:
        self.api_name = api_name
        self.entry = get_api_entry(api_name)
        self.client = client if client is not None else AmkAsyncClient()

    def build_path(
        self,
        path_params: Mapping[str, Any] | BaseModel | None = None,
    ) -> str:
        return validate_and_format_path(self.api_name, self.entry, path_params)

    async def request(
        self,
        *,
        path_params: Mapping[str, Any] | BaseModel | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        path = self.build_path(path_params)
        method = self.entry.method.upper()
        auth_mode = self.entry.auth_mode
        force_new_client_token = bool(kwargs.pop("force_new_client_token", False))
        kwargs = _inject_client_token_if_needed(
            self.api_name, kwargs, force_new_client_token=force_new_client_token
        )
        if method in ("GET", "POST", "PUT", "DELETE"):
            return await getattr(self.client, method.lower())(
                path, auth_mode=auth_mode, **kwargs
            )
        return await self.client.request(method, path, auth_mode=auth_mode, **kwargs)


def _inject_client_token_if_needed(
    api_name: str,
    kwargs: Mapping[str, Any],
    *,
    force_new_client_token: bool = False,
) -> dict[str, Any]:
    """为非视频理解请求按开关注入幂等 token。"""
    patched = dict(kwargs)
    if api_name == "understand_video_content":
        return patched
    enabled = _is_client_token_enabled()
    if not enabled and not force_new_client_token:
        return patched
    payload = patched.get("json")
    if not isinstance(payload, Mapping):
        return patched
    body = dict(payload)
    if force_new_client_token or "client_token" not in body:
        body["client_token"] = uuid.uuid4().hex[:8]
    patched["json"] = body
    return patched


def _is_client_token_enabled() -> bool:
    return (os.getenv("AMK_ENABLE_CLIENT_TOKEN") or "false").strip().lower() == "true"


async def trim_audio(
    payload: TrimMediaDurationRequest,
    *,
    client: AmkAsyncClient | None = None,
) -> httpx.Response:
    use_client = client if client is not None else AmkAsyncClient()
    body = {"audio_url": payload.source, "start_time": payload.start_time}
    if payload.end_time is not None:
        body["end_time"] = payload.end_time
    return await AsyncApiRequest("trim_audio", client=use_client).request(json=body)


async def trim_video(
    payload: TrimMediaDurationRequest,
    *,
    client: AmkAsyncClient | None = None,
) -> httpx.Response:
    use_client = client if client is not None else AmkAsyncClient()
    body = {"video_url": payload.source, "start_time": payload.start_time}
    if payload.end_time is not None:
        body["end_time"] = payload.end_time
    return await AsyncApiRequest("trim_video", client=use_client).request(json=body)


async def trim_media_duration(
    payload: TrimMediaDurationRequest | Mapping[str, Any],
    *,
    client: AmkAsyncClient | None = None,
) -> TrimMediaDurationAsyncResult:
    """聚合方法：按 type 分发 trim_audio/trim_video，异常时返回 error。"""
    try:
        body = (
            payload
            if isinstance(payload, TrimMediaDurationRequest)
            else TrimMediaDurationRequest.model_validate(payload)
        )
        if body.type == "audio":
            res = await trim_audio(body, client=client)
        else:
            res = await trim_video(body, client=client)
        res.raise_for_status()
        data = TrimMediaDurationResponse.model_validate(res.json())
        return TrimMediaDurationAsyncResult(
            task_id=data.task_id, request_id=data.request_id
        )
    except Exception as exc:  # noqa: BLE001 - 统一返回 error 给调用方
        return TrimMediaDurationAsyncResult(error=str(exc))


async def concat_audio(
    payload: ConcatMediaSegmentsRequest,
    *,
    client: AmkAsyncClient | None = None,
) -> httpx.Response:
    use_client = client if client is not None else AmkAsyncClient()
    body = {"audio_urls": payload.sources}
    return await AsyncApiRequest("concat_audio", client=use_client).request(json=body)


async def concat_video(
    payload: ConcatMediaSegmentsRequest,
    *,
    client: AmkAsyncClient | None = None,
) -> httpx.Response:
    use_client = client if client is not None else AmkAsyncClient()
    body = {"video_urls": payload.sources}
    if payload.transitions is not None:
        body["transitions"] = payload.transitions
    return await AsyncApiRequest("concat_video", client=use_client).request(json=body)


async def concat_media_segments(
    payload: ConcatMediaSegmentsRequest | Mapping[str, Any],
    *,
    client: AmkAsyncClient | None = None,
) -> ConcatMediaSegmentsAsyncResult:
    """聚合方法：按 type 分发 concat_audio/concat_video，异常时返回 error。"""
    try:
        body = (
            payload
            if isinstance(payload, ConcatMediaSegmentsRequest)
            else ConcatMediaSegmentsRequest.model_validate(payload)
        )
        if body.type == "audio":
            res = await concat_audio(body, client=client)
        else:
            res = await concat_video(body, client=client)
        res.raise_for_status()
        data = ConcatMediaSegmentsResponse.model_validate(res.json())
        return ConcatMediaSegmentsAsyncResult(
            task_id=data.task_id, request_id=data.request_id
        )
    except Exception as exc:  # noqa: BLE001 - 统一返回 error 给调用方
        return ConcatMediaSegmentsAsyncResult(error=str(exc))


async def understand_video_content(
    prompt: str,
    video_url: str,
    fps: int | float,
    max_frames: int | None = None,
    *,
    client: AmkAsyncClient | None = None,
) -> list[dict[str, Any]]:
    """
    视频理解（固定入参版本）：
    - 接收 prompt、video_url、fps，支持可选 max_frames
    - 内部组装 chat.completions payload
    - 仅返回 choices[].message
    """
    if not prompt.strip():
        raise ValueError("prompt 不能为空")
    if not (video_url.startswith("http://") or video_url.startswith("https://")):
        raise ValueError("video_url 须为 http:// 或 https:// 开头")
    if fps <= 0:
        raise ValueError("fps 必须大于 0")
    if max_frames is not None and max_frames <= 0:
        raise ValueError("max_frames 必须大于 0")
    model_id = normalize_secret(os.environ.get("ARK_MODEL_ID"))
    if model_id is None:
        raise MissingConfigError.missing_env(
            "ARK_MODEL_ID",
            purpose="视频理解 chat.completions 的 model 字段。",
            value_placeholder="<Ark Model ID>",
        )

    use_client = client if client is not None else AmkAsyncClient()
    video_payload: dict[str, Any] = {
        "url": video_url,
        "fps": fps,
    }
    if max_frames is not None:
        video_payload["max_frames"] = max_frames

    request_payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "video_url",
                        "video_url": video_payload,
                    },
                ],
            }
        ],
        "stream": False,
    }
    resp = await AsyncApiRequest("understand_video_content", client=use_client).request(
        json=request_payload
    )
    resp.raise_for_status()
    body = resp.json()
    data = body.get("data") if isinstance(body, Mapping) else None
    container = data if isinstance(data, Mapping) else body
    choices = container.get("choices") if isinstance(container, Mapping) else None
    if not isinstance(choices, list):
        raise ValueError("understand_video_content 响应缺少 choices")

    messages: list[dict[str, Any]] = []
    for choice in choices:
        if isinstance(choice, Mapping) and isinstance(choice.get("message"), Mapping):
            messages.append(dict(choice["message"]))
    return messages


async def mux_audio_video(
    payload: MuxAudioVideoRequest | Mapping[str, Any],
    *,
    client: AmkAsyncClient | None = None,
) -> httpx.Response:
    use_client = client if client is not None else AmkAsyncClient()
    body = (
        payload.model_dump(mode="json", exclude_none=True)
        if isinstance(payload, MuxAudioVideoRequest)
        else MuxAudioVideoRequest.model_validate(payload).model_dump(
            mode="json", exclude_none=True
        )
    )
    return await AsyncApiRequest("mux_audio_video", client=use_client).request(
        json=body
    )


async def image_to_video(
    payload: ImageToVideoRequest | Mapping[str, Any],
    *,
    client: AmkAsyncClient | None = None,
) -> httpx.Response:
    use_client = client if client is not None else AmkAsyncClient()
    body = (
        payload.model_dump(mode="json", exclude_none=True)
        if isinstance(payload, ImageToVideoRequest)
        else ImageToVideoRequest.model_validate(payload).model_dump(
            mode="json", exclude_none=True
        )
    )
    return await AsyncApiRequest("image_to_video", client=use_client).request(json=body)


async def extract_audio(
    payload: ExtractAudioRequest | Mapping[str, Any],
    *,
    client: AmkAsyncClient | None = None,
) -> httpx.Response:
    use_client = client if client is not None else AmkAsyncClient()
    body = (
        payload.model_dump(mode="json", exclude_none=True)
        if isinstance(payload, ExtractAudioRequest)
        else ExtractAudioRequest.model_validate(payload).model_dump(
            mode="json", exclude_none=True
        )
    )
    return await AsyncApiRequest("extract_audio", client=use_client).request(json=body)


async def query_task(
    task_id: str,
    *,
    client: AmkAsyncClient | None = None,
) -> httpx.Response:
    use_client = client if client is not None else AmkAsyncClient()
    return await AsyncApiRequest("query_task", client=use_client).request(
        path_params={"task_id": task_id}
    )


def _extract_play_url(
    task_type: str | None, parsed_result: Mapping[str, Any]
) -> str | None:
    # 优先查找 video_url 和 audio_url，不管任务类型
    video_url = parsed_result.get("video_url") or parsed_result.get("videoa_url")
    audio_url = parsed_result.get("audio_url")
    if video_url:
        return video_url
    if audio_url:
        return audio_url
    return parsed_result.get("play_url")


def normalize_query_task_response(
    payload: Mapping[str, Any],
) -> QueryTaskNormalizedResult:
    # 新接口：status / task_id / result 等在根上；旧接口：包在 Result 里
    if isinstance(payload.get("status"), str):
        task_block: Mapping[str, Any] = payload
    else:
        wrapped = payload.get("Result")
        if not isinstance(wrapped, Mapping):
            raise ValueError("query_task 响应缺少 status 或 Result 对象")
        task_block = wrapped

    status = task_block.get("status")
    if not isinstance(status, str):
        raise ValueError("query_task 响应缺少 status 字段")

    # 新接口通常是根字段；旧接口可能在 Result 内
    task_id = None
    if isinstance(task_block.get("task_id"), str):
        task_id = task_block["task_id"]
    elif isinstance(task_block.get("TaskId"), str):
        task_id = task_block["TaskId"]
    elif isinstance(payload.get("task_id"), str):
        task_id = payload["task_id"]
    elif isinstance(payload.get("TaskId"), str):
        task_id = payload["TaskId"]

    task_type = (
        task_block.get("task_type")
        if isinstance(task_block.get("task_type"), str)
        else None
    )
    request_id = None
    if isinstance(task_block.get("request_id"), str):
        request_id = task_block["request_id"]
    else:
        meta = payload.get("ResponseMetadata")
        if isinstance(meta, Mapping) and isinstance(meta.get("RequestId"), str):
            request_id = meta["RequestId"]

    error = task_block.get("error")
    if status in ("failed", "canceled"):
        raise RuntimeError(str(error or f"task {status}"))

    result_raw = task_block.get("result")
    parsed_result: dict[str, Any] = {}
    if isinstance(result_raw, str) and result_raw.strip():
        parsed = json.loads(result_raw)
        if isinstance(parsed, Mapping):
            parsed_result = dict(parsed)
    elif isinstance(result_raw, Mapping):
        parsed_result = dict(result_raw)

    return QueryTaskNormalizedResult(
        task_id=task_id,
        duration=parsed_result.get("duration"),
        play_url=_extract_play_url(task_type, parsed_result),
        request_id=request_id,
        status=status,  # type: ignore[arg-type]
        task_type=task_type,
    )


async def query_task_with_polling(
    task_id: str,
    interval: int = 5,
    max_retries: int = 6,
    *,
    client: AmkAsyncClient | None = None,
) -> QueryTaskNormalizedResult:
    """
    轮询任务直到完成或失败。

    - status=running/queued: 继续轮询
    - status=completed: 返回标准化结果
    - status=failed/canceled: 抛异常
    """
    if interval <= 0:
        raise ValueError("interval 必须大于 0")
    if max_retries <= 0:
        raise ValueError("max_retries 必须大于 0")

    for attempt in range(max_retries):
        resp = await query_task(task_id, client=client)
        resp.raise_for_status()
        normalized = normalize_query_task_response(resp.json())
        status: TaskStatusStr = normalized.status
        if status == "completed":
            return normalized
        if status in ("running", "queued"):
            if attempt < max_retries - 1:
                await asyncio.sleep(interval)
                continue
            raise TimeoutError("task polling timeout")
        raise RuntimeError(f"unsupported task status: {status}")

    raise TimeoutError("task polling timeout")


async def enhance_video(
    payload: EnhanceVideoRequest | Mapping[str, Any],
    *,
    client: AmkAsyncClient | None = None,
) -> httpx.Response:
    use_client = client if client is not None else AmkAsyncClient()
    body = (
        payload.model_dump(mode="json", exclude_none=True)
        if isinstance(payload, EnhanceVideoRequest)
        else EnhanceVideoRequest.model_validate(payload).model_dump(
            mode="json", exclude_none=True
        )
    )
    return await AsyncApiRequest("enhance_video", client=use_client).request(json=body)
