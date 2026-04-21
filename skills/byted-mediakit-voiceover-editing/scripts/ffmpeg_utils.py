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
ffmpeg 工具封装：统一使用 imageio-ffmpeg 内嵌二进制，不依赖系统安装。
提供 local 模式下所有音视频操作的 ffmpeg 命令封装。

注意：本模块仅在 local 模式下被导入，所有依赖（imageio-ffmpeg）延迟加载，
cloud/apig 模式不会触发安装或导入。
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

_FFMPEG_EXE: str | None = None


def get_ffmpeg_exe() -> str:
    """获取 ffmpeg 可执行路径：优先 imageio-ffmpeg 内嵌，回退系统 ffmpeg"""
    global _FFMPEG_EXE
    if _FFMPEG_EXE is not None:
        return _FFMPEG_EXE

    # 优先使用 imageio-ffmpeg 内嵌
    try:
        import imageio_ffmpeg

        _FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
        return _FFMPEG_EXE
    except ImportError:
        pass

    # 回退系统 ffmpeg
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        _FFMPEG_EXE = sys_ffmpeg
        return _FFMPEG_EXE

    raise RuntimeError(
        "未找到 ffmpeg。请安装:\n"
        "  - pip install imageio-ffmpeg（推荐，内嵌 ffmpeg 二进制）\n"
        "  - 或系统安装: brew install ffmpeg / apt install ffmpeg"
    )


def _ffmpeg() -> str:
    """懒获取 ffmpeg 路径（首次调用时解析，后续缓存）"""
    return get_ffmpeg_exe()


def _run(cmd: list[str], desc: str = "") -> subprocess.CompletedProcess:
    """执行 ffmpeg 命令，失败时打印 stderr 并抛出异常"""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        err = result.stderr or result.stdout or "unknown error"
        raise RuntimeError(f"ffmpeg 失败 ({desc}): {err[:2000]}")
    return result


# ─────────────────────────────────────────────
# 基础音频操作
# ─────────────────────────────────────────────


def extract_audio(input_file: Path, output_mp3: Path) -> Path:
    """从视频/音频文件提取音频为 mp3"""
    output_mp3.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            _ffmpeg(),
            "-i",
            str(input_file),
            "-vn",
            "-acodec",
            "libmp3lame",
            "-q:a",
            "2",
            "-y",
            str(output_mp3),
        ],
        "extract_audio",
    )
    return output_mp3


def convert_to_wav(
    input_file: Path, output_wav: Path, sample_rate: int = 44100, channels: int = 2
) -> Path:
    """音频转码为 WAV (PCM s16le)"""
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            _ffmpeg(),
            "-i",
            str(input_file),
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            "-y",
            str(output_wav),
        ],
        "convert_to_wav",
    )
    return output_wav


def cut_audio(
    input_file: Path,
    output_file: Path,
    start: float,
    duration: float,
    codec: str = "pcm_s16le",
    fade_ms: float = 5,
) -> Path:
    """按时间戳剪切音频片段，首尾加短 fade 避免接缝爆音。"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    fade_s = fade_ms / 1000.0
    af_parts: list[str] = []
    if fade_s > 0 and duration > fade_s * 2:
        af_parts.append(f"afade=t=in:d={fade_s:.4f}")
        af_parts.append(f"afade=t=out:st={duration - fade_s:.4f}:d={fade_s:.4f}")

    cmd = [
        _ffmpeg(),
        "-ss",
        f"{start:.6f}",
        "-i",
        str(input_file),
        "-t",
        f"{duration:.6f}",
    ]
    if af_parts:
        cmd += ["-af", ",".join(af_parts)]
    cmd += ["-acodec", codec, "-y", str(output_file)]
    _run(cmd, "cut_audio")
    return output_file


def concat_audio(input_files: list[Path], output_file: Path) -> Path:
    """拼接多个音频文件（concat demuxer）"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for p in input_files:
            f.write(f"file '{p}'\n")
        list_path = f.name
    try:
        _run(
            [
                _ffmpeg(),
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_path,
                "-acodec",
                "copy",
                "-y",
                str(output_file),
            ],
            "concat_audio",
        )
    finally:
        Path(list_path).unlink(missing_ok=True)
    return output_file


def mix_audios(
    tracks: list[tuple[Path, float]], output_file: Path, duration: float | None = None
) -> Path:
    """混合多条音轨，每条可指定音量"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = [_ffmpeg()]
    filter_parts = []
    for i, (path, volume) in enumerate(tracks):
        cmd.extend(["-i", str(path)])
        filter_parts.append(f"[{i}]volume={volume}[a{i}]")
    labels = "".join(f"[a{i}]" for i in range(len(tracks)))
    amix = f"{labels}amix=inputs={len(tracks)}:dropout_transition=0:normalize=0"
    if duration is not None:
        amix += f",atrim=duration={duration:.6f},asetpts=N/SR/TB"
    amix += "[out]"
    filter_parts.append(amix)
    cmd.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[out]",
            "-y",
            str(output_file),
        ]
    )
    _run(cmd, "mix_audios")
    return output_file


def speedup_audio(input_file: Path, output_file: Path, speed: float) -> Path:
    """音频变速（0.5~2.0 使用 atempo，超出范围链式）"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    filters = []
    remaining = max(0.5, min(speed, 4.0))
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining:.4f}")
    _run(
        [
            _ffmpeg(),
            "-i",
            str(input_file),
            "-af",
            ",".join(filters),
            "-y",
            str(output_file),
        ],
        "speedup_audio",
    )
    return output_file


# ─────────────────────────────────────────────
# 基础视频操作
# ─────────────────────────────────────────────


def mute_video(input_file: Path, output_file: Path) -> Path:
    """静音视频（移除音轨和字幕）"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            _ffmpeg(),
            "-i",
            str(input_file),
            "-an",
            "-sn",
            "-vcodec",
            "copy",
            "-y",
            str(output_file),
        ],
        "mute_video",
    )
    return output_file


def cut_video(
    input_file: Path, output_file: Path, start: float, duration: float
) -> Path:
    """按时间戳精确剪切视频片段（重新编码，避免关键帧偏移导致拼接闪烁）"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            _ffmpeg(),
            "-ss",
            f"{start:.6f}",
            "-i",
            str(input_file),
            "-t",
            f"{duration:.6f}",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-an",
            "-y",
            str(output_file),
        ],
        "cut_video",
    )
    return output_file


def concat_video(input_files: list[Path], output_file: Path) -> Path:
    """拼接多个视频文件（concat demuxer + 重新编码保证无缝衔接）"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for p in input_files:
            f.write(f"file '{p}'\n")
        list_path = f.name
    try:
        _run(
            [
                _ffmpeg(),
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_path,
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-an",
                "-y",
                str(output_file),
            ],
            "concat_video",
        )
    finally:
        Path(list_path).unlink(missing_ok=True)
    return output_file


def compile_video_audio(
    video: Path, audio: Path, output_file: Path, keep_video_audio: bool = False
) -> Path:
    """合成视频+音频"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        _ffmpeg(),
        "-i",
        str(video),
        "-i",
        str(audio),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-vcodec",
        "copy",
        "-acodec",
        "aac",
        "-shortest",
        "-y",
        str(output_file),
    ]
    _run(cmd, "compile_video_audio")
    return output_file


def speedup_video(input_file: Path, output_file: Path, speed: float) -> Path:
    """视频变速"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    vf = f"setpts={1.0 / speed:.6f}*PTS"
    af_filters = []
    remaining = max(0.5, min(speed, 4.0))
    while remaining > 2.0:
        af_filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        af_filters.append("atempo=0.5")
        remaining /= 0.5
    af_filters.append(f"atempo={remaining:.4f}")
    _run(
        [
            _ffmpeg(),
            "-i",
            str(input_file),
            "-vf",
            vf,
            "-af",
            ",".join(af_filters),
            "-y",
            str(output_file),
        ],
        "speedup_video",
    )
    return output_file


def flip_video(
    input_file: Path, output_file: Path, flip_x: bool = False, flip_y: bool = False
) -> Path:
    """视频翻转"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    filters = []
    if flip_x:
        filters.append("hflip")
    if flip_y:
        filters.append("vflip")
    if not filters:
        import shutil as sh

        sh.copy2(str(input_file), str(output_file))
        return output_file
    _run(
        [
            _ffmpeg(),
            "-i",
            str(input_file),
            "-vf",
            ",".join(filters),
            "-acodec",
            "copy",
            "-y",
            str(output_file),
        ],
        "flip_video",
    )
    return output_file


# ─────────────────────────────────────────────
# 降噪
# ─────────────────────────────────────────────


def denoise_audio(input_file: Path, output_file: Path, method: str = "afftdn") -> Path:
    """
    人声降噪 (ffmpeg 内置滤镜)。

    method:
      - afftdn: FFT 降噪，适合稳态噪声（推荐）
      - anlmdn: 非局部均值降噪，保真度更高
      - combined: highpass+lowpass+afftdn 组合，最强降噪
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if method == "afftdn":
        af = "afftdn=nf=-25:tn=1"
    elif method == "anlmdn":
        af = "anlmdn=s=7:p=0.002:r=0.002:m=15"
    else:
        af = "highpass=f=80,lowpass=f=8000,afftdn=nf=-20"
    _run(
        [
            _ffmpeg(),
            "-i",
            str(input_file),
            "-af",
            af,
            "-y",
            str(output_file),
        ],
        f"denoise_audio({method})",
    )
    return output_file


# ─────────────────────────────────────────────
# 字幕压制
# ─────────────────────────────────────────────


def burn_ass_subtitle(video_in: Path, ass_file: Path, video_out: Path) -> Path:
    """将 ASS 字幕硬压到视频"""
    video_out.parent.mkdir(parents=True, exist_ok=True)
    escaped = str(ass_file).replace("\\", "/").replace(":", "\\:")
    _run(
        [
            _ffmpeg(),
            "-i",
            str(video_in),
            "-vf",
            f"ass='{escaped}'",
            "-acodec",
            "copy",
            "-y",
            str(video_out),
        ],
        "burn_ass_subtitle",
    )
    return video_out


# ─────────────────────────────────────────────
# 信息查询
# ─────────────────────────────────────────────


def probe_duration(file_path: Path) -> float:
    """获取媒体文件时长（秒）"""
    import re

    result = subprocess.run(
        [_ffmpeg(), "-i", str(file_path), "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", result.stderr)
    if m:
        h, mi, s, cs = (
            int(m.group(1)),
            int(m.group(2)),
            int(m.group(3)),
            int(m.group(4)),
        )
        return h * 3600 + mi * 60 + s + cs / 100.0
    return 0.0


def probe_video_info(file_path: Path) -> dict[str, Any]:
    """获取视频文件信息（宽、高、时长等），使用 ffmpeg -i 解析"""
    import re

    result = subprocess.run(
        [_ffmpeg(), "-i", str(file_path)],
        capture_output=True,
        text=True,
    )
    info: dict[str, Any] = {"Width": 0, "Height": 0, "Duration": 0.0}
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", result.stderr)
    if m:
        h, mi, s, cs = (
            int(m.group(1)),
            int(m.group(2)),
            int(m.group(3)),
            int(m.group(4)),
        )
        info["Duration"] = h * 3600 + mi * 60 + s + cs / 100.0
    m = re.search(r"Stream.*Video:.* (\d{2,5})x(\d{2,5})", result.stderr)
    if m:
        info["Width"] = int(m.group(1))
        info["Height"] = int(m.group(2))
    return info
