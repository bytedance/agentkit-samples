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
Local 音视频操作：剪辑、拼接、合成、混音、变速、翻转。
封装 ffmpeg_utils 函数为与 ApiManage 方法签名对齐的接口。

local 模式下所有操作直接在本地文件上执行，无需 VOD 空间。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import ffmpeg_utils as fu


def local_extract_audio(
    source_path: Path,
    output_dir: Path,
    fmt: str = "mp3",
) -> dict[str, Any]:
    """提取音频，返回兼容 VCreative 结果的 dict"""
    out_file = output_dir / f"extracted_audio.{fmt}"
    fu.extract_audio(source_path, out_file)
    return {
        "Status": "success",
        "OutputJson": {"filename": str(out_file), "url": str(out_file)},
    }


def local_voice_separation(
    source_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """人声/背景分离，返回兼容 GetExecution 结果的 dict"""
    from local_av_separation import separate_voice_background

    voice, bg = separate_voice_background(source_path, output_dir)
    return {
        "Status": "Success",
        "AudioUrls": [
            {"Type": "voice", "DirectUrl": str(voice), "Url": str(voice)},
            {"Type": "background", "DirectUrl": str(bg), "Url": str(bg)},
        ],
    }


def local_denoise(
    source_path: Path,
    output_dir: Path,
    method: str = "afftdn",
) -> dict[str, Any]:
    """人声降噪，返回兼容结果"""
    from local_denoise import denoise_voice

    out = output_dir / "denoised_voice.mp3"
    denoise_voice(source_path, out, method=method)
    return {
        "Status": "Success",
        "VideoUrls": [{"DirectUrl": str(out), "Url": str(out)}],
    }


def local_audio_clipping(
    source_path: Path,
    start_time: float,
    end_time: float,
    output_dir: Path,
) -> dict[str, Any]:
    """音频剪辑"""
    out = output_dir / "clipped_audio.mp3"
    fu.cut_audio(source_path, out, start=start_time, duration=end_time - start_time)
    return {"Status": "success", "OutputJson": {"filename": str(out)}}


def local_video_clipping(
    source_path: Path,
    start_time: float,
    end_time: float,
    output_dir: Path,
) -> dict[str, Any]:
    """视频剪辑"""
    out = output_dir / "clipped_video.mp4"
    fu.cut_video(source_path, out, start=start_time, duration=end_time - start_time)
    return {"Status": "success", "OutputJson": {"filename": str(out)}}


def local_audio_stitching(
    sources: list[Path],
    output_dir: Path,
) -> dict[str, Any]:
    """音频拼接"""
    out = output_dir / "stitched_audio.mp3"
    fu.concat_audio(sources, out)
    return {"Status": "success", "OutputJson": {"filename": str(out)}}


def local_video_stitching(
    sources: list[Path],
    output_dir: Path,
) -> dict[str, Any]:
    """视频拼接"""
    out = output_dir / "stitched_video.mp4"
    fu.concat_video(sources, out)
    return {"Status": "success", "OutputJson": {"filename": str(out)}}


def local_compile_video_audio(
    video_path: Path,
    audio_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """音视频合成"""
    out = output_dir / "compiled.mp4"
    fu.compile_video_audio(video_path, audio_path, out)
    return {"Status": "success", "OutputJson": {"filename": str(out)}}


def local_mix_audios(
    sources: list[tuple[Path, float]],
    output_dir: Path,
    duration: float | None = None,
) -> dict[str, Any]:
    """混音"""
    out = output_dir / "mixed_audio.mp3"
    fu.mix_audios(sources, out, duration=duration)
    return {"Status": "success", "OutputJson": {"filename": str(out)}}


def local_speedup_video(
    source_path: Path,
    speed: float,
    output_dir: Path,
) -> dict[str, Any]:
    """视频变速"""
    out = output_dir / "speedup_video.mp4"
    fu.speedup_video(source_path, out, speed)
    return {"Status": "success", "OutputJson": {"filename": str(out)}}


def local_speedup_audio(
    source_path: Path,
    speed: float,
    output_dir: Path,
) -> dict[str, Any]:
    """音频变速"""
    out = output_dir / "speedup_audio.mp3"
    fu.speedup_audio(source_path, out, speed)
    return {"Status": "success", "OutputJson": {"filename": str(out)}}


def local_flip_video(
    source_path: Path,
    output_dir: Path,
    flip_x: bool = False,
    flip_y: bool = False,
) -> dict[str, Any]:
    """视频翻转"""
    out = output_dir / "flipped_video.mp4"
    fu.flip_video(source_path, out, flip_x=flip_x, flip_y=flip_y)
    return {"Status": "success", "OutputJson": {"filename": str(out)}}


def local_add_subtitle(
    video_path: Path,
    segments: list[dict[str, Any]],
    output_dir: Path,
    **style_kwargs,
) -> dict[str, Any]:
    """字幕压制"""
    from local_subtitle import burn_subtitles

    out = output_dir / "subtitled_video.mp4"
    burn_subtitles(video_path, segments, out, **style_kwargs)
    return {"Status": "success", "OutputJson": {"filename": str(out)}}


def local_get_video_info(source_path: Path) -> dict[str, Any]:
    """获取视频信息（宽高时长等）"""
    info = fu.probe_video_info(source_path)
    return {
        "Width": info.get("Width", 0),
        "Height": info.get("Height", 0),
        "Duration": info.get("Duration", 0.0),
        "PlayURL": str(source_path),
    }
