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
Local 导出：按 export_request.json 的 Track 结构使用 ffmpeg 在本地合成最终视频。
替代 VOD SubmitDirectEditTaskAsync，无需云端服务。

Track 结构：
  [ [video_elements...], [bg_audio_elements...], [voice_elements...], [text_elements...] ]

每个 element:
  { Type: "video"|"audio"|"text", Source: "...", TargetTime: [start_ms, end_ms], Extra: [...] }
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import ffmpeg_utils as fu
from track_cut_realign import classify_lanes, get_trim, get_volume, realign_export_track


def _resolve_source(source: str, output_dir: Path) -> Path | None:
    """从 Source 字段解析本地文件路径。
    优先裸路径，兼容 vid://, directurl://, file:// 等旧格式前缀。"""
    s = source.strip()
    if not s:
        return None

    # 直接当裸路径尝试
    p = Path(s)
    if p.is_file():
        return p

    # 兼容旧格式：剥离 URL scheme 前缀后重试
    for prefix in ("vid://", "directurl://", "file://"):
        if s.startswith(prefix):
            stripped = s[len(prefix) :]
            sp = Path(stripped)
            if sp.is_file():
                return sp
            break

    # 在 output_dir 下查找（用剥离后或原始路径的文件名）
    raw = s
    for prefix in ("vid://", "directurl://", "file://"):
        if raw.startswith(prefix):
            raw = raw[len(prefix) :]
            break

    candidate = output_dir / raw
    if candidate.is_file():
        return candidate

    name_only = Path(raw).name
    if name_only:
        candidate = output_dir / name_only
        if candidate.is_file():
            return candidate

    return None


def export_local(
    export_request_path: Path,
    output_dir: Path,
    output_filename: str = "export_local.mp4",
) -> Path:
    """
    读取 export_request.json，用 ffmpeg 在本地合成最终视频。

    策略：
    1. 从 video lane 提取/裁剪视频片段 → concat 为无音轨视频
    2. 从 voice lane 提取/裁剪音频片段 → 按 TargetTime 延迟 → amix
    3. 从 bg lane 提取背景音并混合
    4. 将 text lane 生成 ASS 字幕 → burn 到视频
    5. mux 视频 + 混合音频 → 最终输出
    """
    data = json.loads(export_request_path.read_text(encoding="utf-8"))
    track = realign_export_track(data.get("Track", []))

    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="local_export_"))

    try:
        video_lane, audio_lanes, text_lane = classify_lanes(track)

        # Step 1: 处理视频轨
        video_out = _process_video_lane(video_lane, output_dir, work_dir)

        # Step 2: 处理音频轨（人声+背景混合）
        print(f"[local_export] 音频轨数量: {len(audio_lanes)}")
        audio_out = _process_audio_lanes(audio_lanes, output_dir, work_dir)

        # Step 3: 合成视频+音频
        if video_out and audio_out:
            print(f"[local_export] 合成视频+音频: video={video_out}, audio={audio_out}")
            muxed = work_dir / "muxed.mp4"
            fu.compile_video_audio(video_out, audio_out, muxed)
        elif video_out:
            print("[local_export] WARNING: 无音频轨，输出视频将没有声音")
            muxed = video_out
        else:
            raise RuntimeError("无可用的视频轨")

        # Step 4: 字幕压制（如果有 text lane）
        final_output = output_dir / output_filename
        if text_lane:
            from local_subtitle import burn_subtitles

            segments = _text_lane_to_segments(text_lane)
            if segments:
                burn_subtitles(muxed, segments, final_output)
            else:
                shutil.copy2(str(muxed), str(final_output))
        else:
            shutil.copy2(str(muxed), str(final_output))

        return final_output
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _process_video_lane(
    lane: list[dict],
    output_dir: Path,
    work_dir: Path,
) -> Path | None:
    if not lane:
        return None

    segments: list[Path] = []
    for i, el in enumerate(lane):
        raw_source = el.get("Source", "")
        source = _resolve_source(raw_source, output_dir)
        if not source:
            print(f"[WARNING] 视频元素 {i} Source 无法解析为本地文件: {raw_source!r}")
            continue
        trim = get_trim(el.get("Extra", []))
        target = el.get("TargetTime", [0, 0])
        out_seg = work_dir / f"vseg_{i:04d}.mp4"

        if trim:
            start_s = trim[0] / 1000.0
            dur_s = (trim[1] - trim[0]) / 1000.0
            fu.cut_video(source, out_seg, start=start_s, duration=dur_s)
        else:
            start_s = target[0] / 1000.0
            dur_s = (target[1] - target[0]) / 1000.0
            fu.cut_video(source, out_seg, start=start_s, duration=dur_s)
        segments.append(out_seg)

    if not segments:
        return None
    if len(segments) == 1:
        return segments[0]

    concat_out = work_dir / "video_concat.mp4"
    fu.concat_video(segments, concat_out)
    return concat_out


def _process_audio_lanes(
    lanes: list[list[dict]],
    output_dir: Path,
    work_dir: Path,
) -> Path | None:
    if not lanes:
        return None

    track_files: list[tuple[Path, float]] = []

    for lane_idx, lane in enumerate(lanes):
        lane_segments: list[Path] = []
        lane_volume = 1.0
        lane_volume_set = False

        for i, el in enumerate(lane):
            raw_source = el.get("Source", "")
            source = _resolve_source(raw_source, output_dir)
            if not source:
                print(
                    f"[WARNING] 音频元素 lane{lane_idx}/{i} Source 无法解析: {raw_source!r}"
                )
                continue
            trim = get_trim(el.get("Extra", []))
            vol = get_volume(el.get("Extra", []))
            if not lane_volume_set and vol > 0:
                lane_volume = vol
                lane_volume_set = True
            target = el.get("TargetTime", [0, 0])
            out_seg = work_dir / f"aseg_{lane_idx}_{i:04d}.wav"

            if trim:
                start_s = trim[0] / 1000.0
                dur_s = (trim[1] - trim[0]) / 1000.0
            else:
                start_s = target[0] / 1000.0
                dur_s = (target[1] - target[0]) / 1000.0

            fu.cut_audio(
                source, out_seg, start=start_s, duration=dur_s, codec="pcm_s16le"
            )

            # 如果 volume 为 0（mute 段），生成静音替代
            if vol == 0:
                silence = work_dir / f"silence_{lane_idx}_{i:04d}.wav"
                fu._run(
                    [
                        fu._ffmpeg(),
                        "-f",
                        "lavfi",
                        "-i",
                        "anullsrc=r=48000:cl=stereo",
                        "-t",
                        f"{dur_s:.6f}",
                        "-acodec",
                        "pcm_s16le",
                        "-y",
                        str(silence),
                    ],
                    "generate silence",
                )
                out_seg = silence

            lane_segments.append(out_seg)

        if not lane_segments:
            continue

        if len(lane_segments) == 1:
            lane_file = lane_segments[0]
        else:
            lane_file = work_dir / f"lane_{lane_idx}.wav"
            fu.concat_audio(lane_segments, lane_file)

        track_files.append((lane_file, lane_volume))

    if not track_files:
        return None
    if len(track_files) == 1:
        return track_files[0][0]

    mixed = work_dir / "mixed_audio.wav"
    fu.mix_audios(track_files, mixed)
    return mixed


def _text_lane_to_segments(lane: list[dict]) -> list[dict[str, Any]]:
    """将 text lane elements 转为字幕 segments"""
    segments = []
    for el in lane:
        target = el.get("TargetTime", [0, 0])
        text = el.get("Text", "").strip()
        if text and len(target) >= 2:
            segments.append(
                {
                    "start": target[0] / 1000.0,
                    "end": target[1] / 1000.0,
                    "text": text,
                }
            )
    return segments
