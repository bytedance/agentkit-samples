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
Local ASR：使用 Qwen3-ASR + Silero VAD 进行本地语音转录。
适配自 video-translation/scripts/base/asr_qwen.py，输出格式对齐 asr_volc.py。

依赖：qwen-asr, torch, soundfile, ffmpeg-python (或 imageio-ffmpeg)
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def _load_silero_vad(device: str = "cpu"):
    import torch

    model, utils = torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        force_reload=False,
        onnx=False,
    )
    model.to(device)
    return model, utils


def _detect_speech_segments(
    audio_path: str,
    vad_model,
    vad_utils,
    device: str = "cpu",
    sampling_rate: int = 16000,
    threshold: float = 0.3,
    min_speech_duration: float = 0.3,
    min_silence_duration: float = 0.15,
) -> list[dict]:
    from ffmpeg_utils import _ffmpeg
    import subprocess
    import soundfile as sf

    fd, temp_wav = tempfile.mkstemp(suffix=".16k.wav")
    os.close(fd)
    try:
        subprocess.run(
            [
                _ffmpeg(),
                "-i",
                audio_path,
                "-ar",
                str(sampling_rate),
                "-ac",
                "1",
                "-f",
                "wav",
                "-y",
                temp_wav,
            ],
            capture_output=True,
            check=True,
        )
        waveform, sr = sf.read(temp_wav)
        if len(waveform.shape) > 1:
            waveform = waveform.mean(axis=1)
        waveform = np.ascontiguousarray(waveform.astype(np.float32))
    finally:
        if os.path.exists(temp_wav):
            os.remove(temp_wav)

    get_speech_timestamps = vad_utils[0]
    speech_timestamps = get_speech_timestamps(
        waveform,
        vad_model,
        sampling_rate=sampling_rate,
        threshold=threshold,
        min_speech_duration_ms=min_speech_duration * 1000,
        min_silence_duration_ms=min_silence_duration * 1000,
    )

    segments = []
    for ts in speech_timestamps:
        segments.append(
            {
                "start": ts["start"] / sampling_rate,
                "end": ts["end"] / sampling_rate,
                "audio": waveform[ts["start"] : ts["end"]],
            }
        )
    return segments


def transcribe_local(
    audio_path: str,
    output_path: Path,
    *,
    model_size: str = "1.7B",
    device: str = "auto",
    language: str | None = None,
) -> dict[str, Any]:
    """
    Local ASR 入口，使用 Qwen3-ASR。
    输出格式与 asr_volc 兼容的 JSON。
    """
    import torch
    from qwen_asr import Qwen3ASRModel

    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Local ASR: Qwen3-ASR-{model_size} on {device}")

    vad_model, vad_utils = _load_silero_vad(device)

    model = Qwen3ASRModel.from_pretrained(
        f"Qwen/Qwen3-ASR-{model_size}",
        dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map=device,
        forced_aligner="Qwen/Qwen3-ForcedAligner-0.6B",
        forced_aligner_kwargs=dict(
            dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
            device_map=device,
        ),
    )

    speech_segments = _detect_speech_segments(audio_path, vad_model, vad_utils, device)
    logger.info(f"检测到 {len(speech_segments)} 个语音片段")

    # 构建与 asr_volc 兼容的结果格式
    result_utterances = []
    for i, segment in enumerate(speech_segments):
        try:
            audio_data = (segment["audio"], 16000)
            results = model.transcribe(
                audio=audio_data, language=language, return_time_stamps=True
            )
        except Exception as e:
            logger.error(f"片段 {i} 转录失败: {e}")
            continue
        if not results or not results[0].text.strip():
            continue

        r = results[0]
        words = []
        if r.time_stamps:
            for wts in r.time_stamps:
                words.append(
                    {
                        "text": wts.text.strip(),
                        "start_time": int((segment["start"] + wts.start_time) * 1000),
                        "end_time": int((segment["start"] + wts.end_time) * 1000),
                    }
                )

        result_utterances.append(
            {
                "text": r.text.strip(),
                "start_time": int(segment["start"] * 1000),
                "end_time": int(segment["end"] * 1000),
                "words": words,
            }
        )

    # 兼容 asr_volc 输出格式
    output = {
        "code": 0,
        "result": {
            "utterances": result_utterances,
            "additions": {"duration": str(int(_get_audio_duration(audio_path) * 1000))},
        },
        "_execution_mode": "local",
        "_model": f"Qwen3-ASR-{model_size}",
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(f"Local ASR 完成，{len(result_utterances)} 条语句 → {output_path}")
    return output


def _get_audio_duration(audio_path: str) -> float:
    try:
        import soundfile as sf

        with sf.SoundFile(audio_path) as f:
            return f.frames / f.samplerate
    except Exception:
        from ffmpeg_utils import probe_duration

        return probe_duration(Path(audio_path))
