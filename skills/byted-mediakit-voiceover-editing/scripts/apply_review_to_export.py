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
审核数据 → 服务端导出格式转换。
输入：审核页 POST body { sentences, baseTrack, mergedTrack }
输出：符合 track_witdh_request 的 export_request
保证：mergedTrack 即用户修改后的最终数据，直接转换不重算。
VeVEditor 可能将 a_volume 作为独立元素，需合并到对应 video/audio 的 Extra。
Extra 所有子项必须包含全局唯一 ID。
默认跳过字幕压制；环境变量 VOD_EXPORT_SKIP_SUBTITLE=0 时启用字幕压制。
"""

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List

# 加载 skill .env 以便读取 VOD_EXPORT_SKIP_SUBTITLE
try:
    from dotenv import load_dotenv

    skill_dir = Path(__file__).resolve().parents[1]
    load_dotenv(dotenv_path=skill_dir / ".env", override=False)
except Exception:
    pass


def _skip_subtitle_export() -> bool:
    """是否跳过字幕压制：默认跳过；设为 0/false/no 时启用字幕压制"""
    v = (os.getenv("VOD_EXPORT_SKIP_SUBTITLE") or "").strip().lower()
    return v not in ("0", "false", "no")


STATUS_REMOVED = "removed"
STATUS_MUTED = "muted"


def _ensure_extra_id(f: Dict) -> Dict:
    """确保 Extra 子项有全局唯一 ID"""
    out = dict(f)
    if not out.get("ID"):
        out["ID"] = uuid.uuid4().hex[:12]
    return out


def _normalize_source(src: str) -> str:
    """VOD 要求 DirectUrl 类型 Source 带 directurl:// 前缀，审核页/编辑器可能返回裸文件名。

    local 模式特殊处理：Source 可能是 /local-media/ URL（审核页传入），
    需转为裸绝对路径供 ffmpeg 使用。
    """
    if not src or not isinstance(src, str):
        return src
    s = src.strip()
    # local 模式: /local-media/ URL → 提取裸绝对路径
    import re
    from urllib.parse import unquote

    m = re.match(r"https?://[^/]+/local-media(/.*)", s)
    if m:
        return unquote(m.group(1))  # 裸绝对路径，如 /Users/.../background.mp3
    if s.startswith(("vid://", "http://", "https://", "directurl://")):
        return s
    # 裸绝对路径（以 / 开头）: local 模式直接使用，不加 directurl://
    if s.startswith("/"):
        return s
    return f"directurl://{s}"


def _collect_volume_by_target(track: List[List[Dict]]) -> Dict[str, float]:
    """收集独立 a_volume 元素，按目标 id 映射 Volume。VeVEditor 中 a_volume 的 UserData.id 指向目标元素"""
    vol_map: Dict[str, float] = {}
    for lane in track or []:
        if not isinstance(lane, list):
            continue
        last_video_audio_id = ""
        for el in lane:
            if not el:
                continue
            typ = (el.get("Type") or "").lower()
            if typ in ("video", "audio"):
                last_video_audio_id = (
                    (el.get("UserData") or {}).get("id")
                    or el.get("ID")
                    or el.get("id")
                    or ""
                )
            elif typ == "a_volume":
                vol = el.get("Volume")
                if vol is None:
                    continue
                try:
                    v = float(vol)
                except (TypeError, ValueError):
                    continue
                ud = el.get("UserData") or {}
                target_id = (
                    ud.get("id")
                    or ud.get("targetId")
                    or el.get("TargetId")
                    or ud.get("parentId")
                    or el.get("ParentId")
                    or ""
                )
                if target_id:
                    vol_map[target_id] = v
                elif last_video_audio_id:
                    vol_map[last_video_audio_id] = v
    return vol_map


SUBTITLE_FONT_SIZE = 50


def _subtitle_position(cw: int, ch: int) -> Dict[str, int]:
    """字幕安全区：左右 8%，距底 10%，文本区域高度按画布 12%"""
    margin_h = 0.08
    margin_bottom = 0.10
    sub_height_ratio = 0.12
    pos_x = int(cw * margin_h)
    sub_width = int(cw * (1 - 2 * margin_h))
    sub_height = int(ch * sub_height_ratio)
    pos_y = int(ch * (1 - margin_bottom)) - sub_height
    return {"PosX": pos_x, "PosY": pos_y, "Width": sub_width, "Height": sub_height}


def normalize_track_for_export(
    track: List[List[Dict]],
    filter_removed: bool = True,
    canvas: Dict[str, int] | None = None,
) -> List[List[Dict]]:
    """将 mergedTrack（审核页格式）转为服务端 Track 格式，保留预览中的音量设置"""
    if not isinstance(track, list):
        return []

    vol_by_id = _collect_volume_by_target(track)

    out = []
    for lane in track:
        if not isinstance(lane, list):
            continue
        elems = []
        for el in lane:
            if not el or not isinstance(el, dict):
                continue
            ud = el.get("UserData") or {}
            typ = (el.get("Type") or "").lower()
            if typ == "text" and _skip_subtitle_export():
                continue  # 环境变量配置：跳过字幕压制
            # 字幕：过滤 removed/muted；音视频：保留 muted（a_volume:0），仅过滤 removed
            if filter_removed:
                if typ == "text" and ud.get("status") in (STATUS_REMOVED, STATUS_MUTED):
                    continue
                if typ in ("video", "audio") and ud.get("status") == STATUS_REMOVED:
                    continue
            if typ in ("a_volume", "equalizer"):
                continue
            tt = el.get("TargetTime") or [0, 0]
            if isinstance(tt, list) and len(tt) >= 2:
                st, et = (
                    int(tt[0]) if tt[0] is not None else 0,
                    int(tt[1]) if tt[1] is not None else 0,
                )
                st, et = max(0, st), max(st + 1, et) if et <= st else max(0, et)
                tt = [st, et]
            else:
                tt = [0, 1]
            clean = {"Type": el.get("Type"), "TargetTime": tt}
            if typ in ("video", "audio"):
                clean["Source"] = _normalize_source(el.get("Source", ""))
                extra = el.get("Extra") or []
                clean["Extra"] = []
                has_volume = False
                el_id = ud.get("id") or el.get("ID") or el.get("id") or "el"
                for f in extra:
                    if not f or not isinstance(f, dict):
                        continue
                    t = f.get("Type")
                    if t == "trim":
                        st, et = f.get("StartTime", 0), f.get("EndTime", 0)
                        # 无效 trim（EndTime<=StartTime）时用已归一化的 TargetTime，避免 VOD failed_run
                        if et <= st:
                            st, et = tt[0], tt[1]
                        clean["Extra"].append(
                            _ensure_extra_id(
                                {
                                    "Type": "trim",
                                    "StartTime": st,
                                    "EndTime": et,
                                }
                            )
                        )
                    elif t == "a_volume":
                        has_volume = True
                        clean["Extra"].append(
                            _ensure_extra_id(
                                {"Type": "a_volume", "Volume": f.get("Volume", 1)}
                            )
                        )
                    elif t == "transform" and typ == "video":
                        clean["Extra"].append(
                            _ensure_extra_id(
                                {
                                    "Type": "transform",
                                    "Width": f.get("Width", 1280),
                                    "Height": f.get("Height", 720),
                                    "PosX": f.get("PosX", 0),
                                    "PosY": f.get("PosY", 0),
                                    "Rotation": f.get("Rotation", 0),
                                    "FlipX": f.get("FlipX", False),
                                    "FlipY": f.get("FlipY", False),
                                    "ScaleX": f.get("ScaleX", 1),
                                    "ScaleY": f.get("ScaleY", 1),
                                }
                            )
                        )
                if not has_volume:
                    vol = vol_by_id.get(el_id)
                    if vol is not None:
                        clean["Extra"].append(
                            _ensure_extra_id({"Type": "a_volume", "Volume": vol})
                        )
                    elif typ == "audio" and ud.get("status") == STATUS_MUTED:
                        clean["Extra"].append(
                            _ensure_extra_id({"Type": "a_volume", "Volume": 0})
                        )
            elif typ == "text":
                _font_type_default = (
                    "https://lf3-static.bytednsdoc.com/obj/eden-cn/ljhwz_kvc/"
                    "ljhwZthlaukjlkulzlp/ai_mediakit/字体/okt1LEaq5CAm0EAoBSFfACgGel7AdgEnVADspZ.zip"
                )
                clean["Text"] = el.get("Text", "")
                clean["FontType"] = el.get("FontType", _font_type_default)
                clean["FontSize"] = SUBTITLE_FONT_SIZE
                clean["FontColor"] = el.get("FontColor", "#ffffffff")
                clean["ShadowColor"] = el.get("ShadowColor", "#00000000")
                clean["LineMaxWidth"] = el.get("LineMaxWidth", 1)
                clean["AlignType"] = 1
                cw = canvas.get("Width") if canvas else None
                ch = canvas.get("Height") if canvas else None
                sub_pos = (
                    _subtitle_position(int(cw), int(ch))
                    if (
                        cw is not None
                        and ch is not None
                        and int(cw) > 0
                        and int(ch) > 0
                    )
                    else None
                )
                if sub_pos:
                    clean["Extra"] = [
                        _ensure_extra_id(
                            {
                                "Type": "transform",
                                "PosX": sub_pos["PosX"],
                                "PosY": sub_pos["PosY"],
                                "Width": sub_pos["Width"],
                                "Height": sub_pos["Height"],
                                "Rotation": 0,
                                "FlipX": False,
                                "FlipY": False,
                                "Alpha": 1,
                            }
                        )
                    ]
                else:
                    clean["Extra"] = []
            else:
                continue
            elems.append(clean)
        if elems:  # 跳过空轨（如整轨为字幕且已配置跳过时）
            out.append(elems)
    return out


def apply_review_to_export(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    从审核页 POST body 生成 export_request。
    使用 mergedTrack 作为数据源，保证与用户审核结果一致。
    """
    sentences = body.get("sentences") or []
    merged_track = body.get("mergedTrack") or body.get("exportTrack") or []

    # Canvas：优先使用审核页传入的（含 updateProject 同步的变更），否则默认
    canvas = body.get("Canvas") or body.get("canvas") or {}
    canvas = {
        "Width": canvas.get("Width") or 1280,
        "Height": canvas.get("Height") or 2160,
        **{k: v for k, v in canvas.items() if k not in ("Width", "Height")},
    }

    track_export = normalize_track_for_export(
        merged_track, filter_removed=True, canvas=canvas
    )

    # 二次校验：确保所有 audio/video 的 Source 带 directurl:// 前缀（防止遗漏）
    for lane in track_export:
        for el in lane or []:
            if (
                el
                and isinstance(el, dict)
                and (el.get("Type") or "").lower() in ("video", "audio")
            ):
                src = el.get("Source", "")
                if src:
                    el["Source"] = _normalize_source(src)

    # 与本地 export 一致：单段全时长视频 + 多段人声(含 mute) 时，按保留人声做时间轴剪辑（对齐 prepare_export_data do_video_cut / VOD）
    from track_cut_realign import realign_export_track

    track_export = realign_export_track(track_export)

    # 保留 Upload / Uploader（来自原始 export_request，由 save-review / export_server 传入）
    upload = body.get("Upload") or body.get("_upload") or {}
    uploader = body.get("Uploader") or body.get("_uploader") or ""

    result = {
        "Canvas": canvas,
        "Track": track_export,
        "_meta": {
            "sentences_count": len(sentences),
            "track_lanes": len(track_export),
        },
    }
    if upload:
        result["Upload"] = upload
    if uploader:
        result["Uploader"] = uploader

    print("=== 审核页面转化后的导出数据 (apply_review_to_export 输出) ===")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print("=== 转化后数据结束 ===")

    return result
