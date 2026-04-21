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

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
from dotenv import load_dotenv

from project_paths import get_project_root


def get_script_dir() -> Path:
    return Path(__file__).resolve().parent


def get_output_dir() -> Path:
    return get_project_root() / "output"


def _load_skill_env() -> None:
    """
    Load skill `.env` from `byted-mediakit-voiceover-editing/.env`.
    This keeps behavior stable even when called from other working directories.
    """
    scripts_dir = get_script_dir()
    skill_dir = scripts_dir.parent
    load_dotenv(dotenv_path=skill_dir / ".env", override=False)


def _require_env(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise ValueError(f"Missing required env var: {key}")
    return value


@dataclass(frozen=True)
class VolcAsrConfig:
    api_key: str
    base_url: str

    @staticmethod
    def from_env() -> "VolcAsrConfig":
        _load_skill_env()
        return VolcAsrConfig(
            api_key=_require_env("ASR_API_KEY"),
            base_url=_require_env("ASR_BASE_URL").rstrip("/"),
        )


def _http_post_json(
    url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout_s: int
) -> Dict[str, Any]:
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
    resp.raise_for_status()
    return resp.json()


def submit_bigmodel_task(
    audio_url: str,
    *,
    audio_type: str = "mp3",
    request_id: Optional[str] = None,
    config: Optional[VolcAsrConfig] = None,
    timeout_s: int = 60,
) -> str:
    """
    Submit ASR task (bigmodel). Returns request_id used for polling.
    Audio is referenced by http(s) URL; the service fetches the file (no client-side base64).
    """
    cfg = config or VolcAsrConfig.from_env()
    rid = request_id or str(uuid.uuid4())

    submit_url = f"{cfg.base_url}/submit?api_key={cfg.api_key}"

    payload: Dict[str, Any] = {
        "audio": {"url": audio_url, "type": audio_type},
        "request": {
            "modal_name": "bigmodel",
            "enable_emotion_detection": True,
            "enable_gender_detection": True,
            "enable_speaker_info": True,
            "enable_poi_fc": False,
            "use_itn": True,
            "use_punc": True,
            "enable_ddc": True,
        },
        "user": {"uid": "byted-mediakit-voiceover-editing"},
    }

    headers = {
        "Accept": "*/*",
        "x-api-key": cfg.api_key,
        "x-api-request-id": rid,
        "x-api-resource-id": "volc.seedasr.auc",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
    }

    data = _http_post_json(submit_url, headers, payload, timeout_s=timeout_s)
    # 服务端常见返回：{} 或带 code/message
    if isinstance(data, dict) and (data == {} or data.get("code") in (None, 0, 1000)):
        return rid
    # 兜底：如果返回里有 id/task_id，就用它
    for k in ("id", "task_id", "request_id"):
        v = data.get(k) if isinstance(data, dict) else None
        if isinstance(v, str) and v.strip():
            return v.strip()
    raise RuntimeError(
        f"ASR submit failed: {json.dumps(data, ensure_ascii=False)[:2000]}"
    )


def query_bigmodel_task(
    request_id: str,
    *,
    config: Optional[VolcAsrConfig] = None,
    timeout_s: int = 60,
) -> Dict[str, Any]:
    """
    Query ASR task status/result by request_id.
    """
    cfg = config or VolcAsrConfig.from_env()
    query_url = f"{cfg.base_url}/query?api_key={cfg.api_key}"
    headers = {
        "Accept": "*/*",
        "x-api-key": cfg.api_key,
        "x-api-request-id": request_id,
        "x-api-resource-id": "volc.seedasr.auc",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
    }
    return _http_post_json(query_url, headers, {}, timeout_s=timeout_s)


def transcribe_audio_url(
    audio_url: str,
    *,
    audio_type: str = "mp3",
    interval_s: float = 5.0,
    max_attempts: int = 120,
    config: Optional[VolcAsrConfig] = None,
    output_dir: Optional[Path] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    High-level helper:
    - input: an http(s) audio URL
    - output: (request_id, full query response dict)
    """
    rid = submit_bigmodel_task(audio_url, audio_type=audio_type, config=config)
    last: Dict[str, Any] = {}

    for _ in range(max_attempts):
        time.sleep(interval_s)
        last = query_bigmodel_task(rid, config=config)
        code = last.get("code")
        result = last.get("result") if isinstance(last, dict) else None

        # 完成判定：参考 `volcengine_transcribe.py` 的兼容逻辑
        if isinstance(result, dict) and result.get("additions") is not None:
            out_dir = output_dir if output_dir is not None else get_output_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"asr_raw_{rid}.json").write_text(
                json.dumps(last, ensure_ascii=False), encoding="utf-8"
            )
            return rid, last
        if code == 0:
            out_dir = output_dir if output_dir is not None else get_output_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"asr_raw_{rid}.json").write_text(
                json.dumps(last, ensure_ascii=False), encoding="utf-8"
            )
            return rid, last
        if code == 1000:
            continue
        if (
            isinstance(result, dict)
            and "result" in last
            and (result.get("text") or "") == ""
        ):
            continue

        raise RuntimeError(f"ASR failed: {json.dumps(last, ensure_ascii=False)[:2000]}")

    raise TimeoutError(f"ASR timeout: request_id={rid}")
