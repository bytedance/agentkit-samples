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
审核页 mergedTrack 常见形态：视频轨单段全时长 + 人声多段（含 mute）。
与 prepare_export_data.py 的 do_video_cut 对齐：去掉 mute 人声对应时间，主时间轴从 0 无缝拼接。

供 local_export、apply_review_to_export（APIG/Cloud 走 VOD）共用。
"""

from __future__ import annotations

from typing import Any


def get_trim(extra: list[dict]) -> tuple[int, int] | None:
    for e in extra or []:
        if e.get("Type") == "trim":
            return int(e.get("StartTime", 0)), int(e.get("EndTime", 0))
    return None


def get_volume(extra: list[dict]) -> float:
    for e in extra or []:
        if e.get("Type") == "a_volume":
            return float(e.get("Volume", 1.0))
    return 1.0


def classify_lanes(track: list[Any]) -> tuple[list[dict], list[list[dict]], list[dict]]:
    video_lane: list[dict] = []
    audio_lanes: list[list[dict]] = []
    text_lane: list[dict] = []

    for lane in track:
        if not isinstance(lane, list) or not lane:
            continue
        first = lane[0] if lane else {}
        lane_type = (first.get("Type") or "").lower()
        if lane_type == "video":
            video_lane = lane
        elif lane_type == "audio":
            audio_lanes.append(lane)
        elif lane_type == "text":
            text_lane = lane

    return video_lane, audio_lanes, text_lane


def realign_lanes_for_voice_cut(
    video_lane: list[dict],
    audio_lanes: list[list[dict]],
    text_lane: list[dict],
) -> tuple[list[dict], list[list[dict]], list[dict]]:
    """与 local_export 原 _realign_track_for_cut 一致。"""
    if len(video_lane) != 1:
        return video_lane, audio_lanes, text_lane

    voice_idx = -1
    max_segs = 0
    for i, lane in enumerate(audio_lanes):
        if len(lane) > max_segs:
            max_segs = len(lane)
            voice_idx = i

    if voice_idx < 0 or max_segs <= 1:
        return video_lane, audio_lanes, text_lane

    voice_lane = audio_lanes[voice_idx]
    has_muted = any(get_volume(el.get("Extra", [])) == 0 for el in voice_lane)
    if not has_muted:
        return video_lane, audio_lanes, text_lane

    video_el = video_lane[0]
    video_source = video_el.get("Source", "")
    video_extras_base = [
        e for e in (video_el.get("Extra") or []) if e.get("Type") != "trim"
    ]

    kept: list[dict] = []
    for el in voice_lane:
        vol = get_volume(el.get("Extra", []))
        if vol == 0:
            continue
        trim = get_trim(el.get("Extra", []))
        target = el.get("TargetTime", [0, 0])
        orig_s = trim[0] if trim else target[0]
        orig_e = trim[1] if trim else target[1]
        if orig_e <= orig_s:
            continue
        kept.append(
            {
                "orig_s": orig_s,
                "orig_e": orig_e,
                "audio_source": el.get("Source", ""),
            }
        )

    if not kept:
        return video_lane, audio_lanes, text_lane

    cumul = 0
    for seg in kept:
        dur = seg["orig_e"] - seg["orig_s"]
        seg["new_s"] = cumul
        seg["new_e"] = cumul + dur
        cumul += dur
    total_new = cumul

    new_video: list[dict] = []
    new_voice: list[dict] = []
    for seg in kept:
        extra = [dict(e) for e in video_extras_base]
        extra.append(
            {"Type": "trim", "StartTime": seg["orig_s"], "EndTime": seg["orig_e"]}
        )
        new_video.append(
            {
                "Type": "video",
                "Source": video_source,
                "TargetTime": [seg["new_s"], seg["new_e"]],
                "Extra": extra,
            }
        )
        new_voice.append(
            {
                "Type": "audio",
                "Source": seg["audio_source"],
                "TargetTime": [seg["new_s"], seg["new_e"]],
                "Extra": [
                    {
                        "Type": "trim",
                        "StartTime": seg["orig_s"],
                        "EndTime": seg["orig_e"],
                    }
                ],
            }
        )

    new_audio_lanes: list[list[dict]] = []
    for i, lane in enumerate(audio_lanes):
        if i == voice_idx:
            new_audio_lanes.append(new_voice)
        else:
            new_bg = []
            for el in lane:
                new_el = dict(el)
                tt = list(new_el.get("TargetTime", [0, 0]))
                tt[1] = min(tt[1], total_new)
                new_el["TargetTime"] = tt
                new_bg.append(new_el)
            new_audio_lanes.append(new_bg)

    new_text: list[dict] = []
    for el in text_lane:
        tt = el.get("TargetTime", [0, 0])
        orig_s, orig_e = tt[0], tt[1]
        mapped_s, mapped_e = None, None
        for seg in kept:
            ov_s = max(orig_s, seg["orig_s"])
            ov_e = min(orig_e, seg["orig_e"])
            if ov_s < ov_e:
                ms = seg["new_s"] + (ov_s - seg["orig_s"])
                me = seg["new_s"] + (ov_e - seg["orig_s"])
                if mapped_s is None:
                    mapped_s = ms
                mapped_e = me
        if mapped_s is not None and mapped_e is not None and mapped_e > mapped_s:
            new_el = dict(el)
            new_el["TargetTime"] = [int(mapped_s), int(mapped_e)]
            new_text.append(new_el)

    print(
        f"[track_cut_realign] 视频剪辑重对齐: 视频 1→{len(new_video)} 段, "
        f"人声 {len(voice_lane)}→{len(new_voice)} 段(去 mute), 总长 {total_new}ms",
    )

    return new_video, new_audio_lanes, new_text


def realign_export_track(track: list[Any]) -> list[Any]:
    """对完整 Track 列表做与人声 mute 对齐的剪辑重排；无需变更时返回原列表。"""
    if not track:
        return track
    video_lane, audio_lanes, text_lane = classify_lanes(track)
    nv, na, nt = realign_lanes_for_voice_cut(video_lane, audio_lanes, text_lane)
    if nv is video_lane:
        return track

    out: list[Any] = []
    ai = 0
    for lane in track:
        if not isinstance(lane, list) or not lane:
            continue
        lane_type = ((lane[0] or {}).get("Type") or "").lower()
        if lane_type == "video":
            out.append(nv)
        elif lane_type == "audio":
            out.append(na[ai])
            ai += 1
        elif lane_type == "text":
            out.append(nt)
        else:
            out.append(lane)
    return out
