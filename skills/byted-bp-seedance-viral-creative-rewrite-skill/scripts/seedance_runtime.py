# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
from __future__ import annotations

import os
import time
import base64
import mimetypes
from typing import Any, Dict, List, Optional
from pathlib import Path

import httpx

from provider_errors import format_provider_http_error, format_seedance_task_failure


def get_ark_api_key() -> str:
    value = os.environ.get("ARK_API_KEY", "").strip()
    if not value:
        raise RuntimeError("ARK_API_KEY is required for Seedance video generation.")
    return value


def get_ark_base_url() -> str:
    return os.environ.get("ARK_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3")


def is_local_file_path(value: str) -> bool:
    if value.startswith(("http://", "https://", "data:", "asset://")):
        return False
    return Path(value).expanduser().exists()


def image_file_to_data_url(path: str) -> str:
    file_path = Path(path).expanduser().resolve()
    mime = mimetypes.guess_type(str(file_path))[0] or "image/jpeg"
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def get_seedance_model_id() -> str:
    return os.environ.get("SEEDANCE_MODEL_ID", "dreamina-seedance-2-0-260128")


def get_seedance_tasks_path() -> str:
    return os.environ.get("SEEDANCE_TASKS_PATH", "/contents/generations/tasks")


def seedance_verbose() -> bool:
    return (os.environ.get("SEEDANCE_VERBOSE") or "1").strip().lower() in {"1", "true", "yes", "y", "on"}


def _log(message: str) -> None:
    if seedance_verbose():
        print(f"[seedance] {message}", flush=True)


def _normalize_reference_url(value: Optional[str], *, media_kind: str) -> Optional[str]:
    if not value:
        return None
    if is_local_file_path(value):
        if media_kind == "image":
            _log("encode local reference image as base64 data URL")
            return image_file_to_data_url(value)
        raise RuntimeError(
            "Local Seedance references only support product images through base64 data URLs. "
            "Provide a product image for source input; local source videos and local audio references are not supported."
        )
    return value


def build_seedance_content(
    prompt: str,
    *,
    reference_video_url: Optional[str] = None,
    reference_image_url: Optional[str] = None,
    reference_audio_url: Optional[str] = None,
) -> List[Dict[str, Any]]:
    content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
    if reference_image_url:
        content.append({"type": "image_url", "image_url": {"url": reference_image_url}, "role": "reference_image"})
    if reference_video_url:
        content.append({"type": "video_url", "video_url": {"url": reference_video_url}, "role": "reference_video"})
    if reference_audio_url:
        content.append({"type": "audio_url", "audio_url": {"url": reference_audio_url}, "role": "reference_audio"})
    return content


def _deep_find_url(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, str) and obj.startswith("http"):
        return obj
    if isinstance(obj, dict):
        for key in ("video_url", "url", "video_uri"):
            found = _deep_find_url(obj.get(key))
            if found:
                return found
        for value in obj.values():
            found = _deep_find_url(value)
            if found:
                return found
        return None
    if isinstance(obj, list):
        for item in obj:
            found = _deep_find_url(item)
            if found:
                return found
        return None
    return None


def extract_video_url_from_task_result(result: Any) -> str:
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    found = _deep_find_url(item.get("video_url"))
                    if found:
                        return found
        found = _deep_find_url(result.get("output"))
        if found:
            return found
    found = _deep_find_url(result)
    if found:
        return found
    raise RuntimeError("Could not extract video_url from Seedance task result")


def submit_seedance_video_task(
    *,
    prompt: str,
    duration_sec: float,
    ratio: str = "9:16",
    resolution: str = "720p",
    generate_audio: bool = False,
    reference_video_url: Optional[str] = None,
    reference_image_url: Optional[str] = None,
    reference_audio_url: Optional[str] = None,
    model: Optional[str] = None,
    language: str = "zh",
) -> str:
    duration_sec = max(4, min(int(round(duration_sec)), 15))
    normalized_reference_video = _normalize_reference_url(reference_video_url, media_kind="video")
    normalized_reference_image = _normalize_reference_url(reference_image_url, media_kind="image")
    normalized_reference_audio = _normalize_reference_url(reference_audio_url, media_kind="audio")
    content = build_seedance_content(
        prompt,
        reference_video_url=normalized_reference_video,
        reference_image_url=normalized_reference_image,
        reference_audio_url=normalized_reference_audio,
    )
    base_url = get_ark_base_url().rstrip("/")
    api_key = get_ark_api_key()
    create_url = f"{base_url}{get_seedance_tasks_path()}"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model or get_seedance_model_id(),
        "content": content,
        "duration": duration_sec,
        "ratio": ratio,
        "generate_audio": generate_audio,
        "resolution": resolution,
        "watermark": False,
    }
    _log(
        f"submit start model={payload['model']} duration={payload['duration']} ratio={payload['ratio']} "
        f"resolution={payload['resolution']} ref_video={'yes' if normalized_reference_video else 'no'} "
        f"ref_image={'yes' if normalized_reference_image else 'no'}"
    )
    with httpx.Client(timeout=httpx.Timeout(120.0, connect=30.0)) as client:
        resp = client.post(create_url, json=payload, headers=headers)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(format_provider_http_error(exc, provider="Seedance task creation", language=language)) from exc
        task = resp.json()
    task_id = task.get("id") or task.get("task_id")
    if not task_id:
        raise RuntimeError(f"Seedance task id missing: {task}")
    _log(f"submit ok task_id={task_id}")
    return task_id


def poll_seedance_video_task(task_id: str, *, language: str = "zh") -> dict:
    base_url = get_ark_base_url().rstrip("/")
    api_key = get_ark_api_key()
    get_url = f"{base_url}{get_seedance_tasks_path()}/{task_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=httpx.Timeout(120.0, connect=30.0)) as client:
        resp = client.get(get_url, headers=headers)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(format_provider_http_error(exc, provider="Seedance task polling", language=language)) from exc
        return resp.json()


def generate_video_with_seedance(
    *,
    prompt: str,
    duration_sec: float,
    ratio: str = "9:16",
    resolution: str = "720p",
    generate_audio: bool = False,
    reference_video_url: Optional[str] = None,
    reference_image_url: Optional[str] = None,
    reference_audio_url: Optional[str] = None,
    model: Optional[str] = None,
    poll_interval_sec: float = 2.0,
    timeout_sec: float = 600.0,
    language: str = "zh",
) -> str:
    result = generate_video_with_seedance_result(
        prompt=prompt,
        duration_sec=duration_sec,
        ratio=ratio,
        resolution=resolution,
        generate_audio=generate_audio,
        reference_video_url=reference_video_url,
        reference_image_url=reference_image_url,
        reference_audio_url=reference_audio_url,
        model=model,
        poll_interval_sec=poll_interval_sec,
        timeout_sec=timeout_sec,
        language=language,
    )
    return str(result["video_url"])


def generate_video_with_seedance_result(
    *,
    prompt: str,
    duration_sec: float,
    ratio: str = "9:16",
    resolution: str = "720p",
    generate_audio: bool = False,
    reference_video_url: Optional[str] = None,
    reference_image_url: Optional[str] = None,
    reference_audio_url: Optional[str] = None,
    model: Optional[str] = None,
    poll_interval_sec: float = 2.0,
    timeout_sec: float = 600.0,
    language: str = "zh",
) -> Dict[str, Any]:
    poll_interval_sec = float(os.environ.get("SEEDANCE_POLL_INTERVAL_SEC", str(poll_interval_sec)))
    timeout_sec = float(os.environ.get("SEEDANCE_TIMEOUT_SEC", str(timeout_sec)))
    max_audio_safety_retries = int(os.environ.get("SEEDANCE_AUDIO_SAFETY_RETRIES", "1"))
    attempt = 0
    task_ids: List[str] = []
    while True:
        attempt_prompt = prompt
        if attempt > 0:
            attempt_prompt = (
                prompt
                + "\nAudio safety retry: use only sparse abstract ambient instrumental bed, no melody, no motif, "
                "no rhythm hook, no vocals, no lyrics, no speech-like phonemes, no samples, no artist/style imitation."
            )
        task_id = submit_seedance_video_task(
            prompt=attempt_prompt,
            duration_sec=duration_sec,
            ratio=ratio,
            resolution=resolution,
            generate_audio=generate_audio,
            reference_video_url=reference_video_url,
            reference_image_url=reference_image_url,
            reference_audio_url=reference_audio_url,
            model=model,
            language=language,
        )
        task_ids.append(task_id)
        start = time.time()
        last_status: Optional[str] = None
        last_progress_log = start
        while True:
            now = time.time()
            if now - start > timeout_sec:
                if language == "en":
                    raise TimeoutError(
                        f"Seedance generation timeout (task_id={task_id}, elapsed={int(now - start)}s). "
                        "You can retry later with the same prepared plan or inspect this task id in the provider console."
                    )
                raise TimeoutError(
                    f"Seedance 生成超时（task_id={task_id}，elapsed={int(now - start)}s）。"
                    "可以稍后用同一份 prepared plan 重试，或在服务商控制台查看这个任务。"
                )
            current = poll_seedance_video_task(task_id, language=language)
            status = str(current.get("status") or current.get("state") or "unknown")
            if status != last_status:
                elapsed = int(now - start)
                _log(f"poll task_id={task_id} status={status} elapsed={elapsed}s")
                last_status = status
                last_progress_log = now
            elif now - last_progress_log >= 30:
                elapsed = int(now - start)
                _log(f"poll task_id={task_id} status={status} elapsed={elapsed}s still waiting")
                last_progress_log = now
            if status == "succeeded":
                result = current.get("result") or current
                _log(f"task succeeded task_id={task_id}")
                return {
                    "task_id": task_id,
                    "task_ids": task_ids,
                    "video_url": extract_video_url_from_task_result(result),
                    "raw_task": current,
                }
            if status in ("failed", "canceled", "cancelled"):
                error = current.get("error") if isinstance(current, dict) else None
                code = str(error.get("code") or "") if isinstance(error, dict) else ""
                message = str(error.get("message") or current) if isinstance(error, dict) else str(current)
                if generate_audio and code == "OutputAudioSensitiveContentDetected" and attempt < max_audio_safety_retries:
                    attempt += 1
                    _log(f"task audio safety failed task_id={task_id}; retry {attempt}/{max_audio_safety_retries}")
                    break
                raise RuntimeError(format_seedance_task_failure(task_id=task_id, code=code, message=message, language=language))
            time.sleep(poll_interval_sec)
