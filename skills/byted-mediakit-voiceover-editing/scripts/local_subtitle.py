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
Local 字幕压制：生成 ASS 字幕文件 → ffmpeg 硬压到视频。
适配自 video-translation/scripts/base/burn_subtitle.py。
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from ffmpeg_utils import burn_ass_subtitle, probe_video_info


def _sec_to_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _to_ass_color(hex_color: str) -> str:
    c = hex_color.strip().lstrip("#")
    if len(c) == 8:
        rr, gg, bb, aa = c[0:2], c[2:4], c[4:6], c[6:8]
    elif len(c) == 6:
        rr, gg, bb = c[0:2], c[2:4], c[4:6]
        aa = "00"
    else:
        return "&H00FFFFFF"
    return f"&H{aa}{bb}{gg}{rr}"


def _auto_font_size(width: int, height: int) -> int:
    short_edge = min(width, height)
    return max(24, int(short_edge * 0.045))


def _auto_margin_v(height: int) -> int:
    return max(24, int(height * 0.10))


def _auto_margin_h(width: int) -> int:
    return max(24, int(width * 0.05))


_CJK_RANGES = (
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs
    (0x3400, 0x4DBF),  # CJK Unified Ideographs Extension A
    (0x3040, 0x309F),  # Hiragana
    (0x30A0, 0x30FF),  # Katakana
    (0xAC00, 0xD7AF),  # Hangul Syllables
    (0xFF00, 0xFFEF),  # Halfwidth and Fullwidth Forms
)


def _is_cjk(ch: str) -> bool:
    if not ch:
        return False
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _CJK_RANGES)


def _ass_escape_text(s: str) -> str:
    """避免触发 ASS 覆盖标签或控制序列。"""
    if not s:
        return ""
    return s.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


_BREAK_AFTER_PUNCT = set("，。！？、；：,.;:!?)]}）】》」』”’")
_BREAK_BEFORE_PUNCT = set("，。！？、；：,.;:!?)]}）】》」』”’")


def _char_width(ch: str, *, font_size: int) -> float:
    if ch == "\n":
        return 0.0
    if ch.isspace():
        return font_size * 0.30
    if _is_cjk(ch):
        return font_size * 1.00
    if ch.isalnum():
        return font_size * 0.55
    return font_size * 0.50


def _wrap_text_to_lines(
    text: str,
    *,
    max_width_px: int,
    font_size: int,
    max_lines: int,
) -> list[str]:
    """近似按像素宽度折行（返回不超过 max_lines 行）。"""
    if not text:
        return []
    t = " ".join(text.strip().split())
    if not t:
        return []

    lines: list[str] = []
    buf: list[str] = []
    buf_w = 0.0
    last_break_idx: int | None = None

    def _recalc_last_break() -> None:
        nonlocal last_break_idx
        last_break_idx = None
        for i, c in enumerate(buf):
            if c == " " or c in _BREAK_AFTER_PUNCT:
                last_break_idx = i + 1

    def _flush_upto(idx_exclusive: int) -> str:
        nonlocal buf, buf_w
        out = "".join(buf[:idx_exclusive]).rstrip()
        rest = "".join(buf[idx_exclusive:]).lstrip()
        buf = list(rest)
        buf_w = sum(_char_width(c, font_size=font_size) for c in buf)
        _recalc_last_break()
        return out

    for ch in t:
        buf.append(ch)
        buf_w += _char_width(ch, font_size=font_size)
        if ch == " " or ch in _BREAK_AFTER_PUNCT:
            last_break_idx = len(buf)

        if buf_w <= max_width_px:
            continue

        if len(lines) + 1 >= max_lines:
            continue  # 最后一行交给省略处理

        cut = last_break_idx if last_break_idx else max(1, len(buf) - 1)
        if cut < len(buf) and buf[cut] in _BREAK_BEFORE_PUNCT:
            cut += 1
        line = _flush_upto(cut)
        if line:
            lines.append(line)

    if len(lines) < max_lines and buf:
        lines.append("".join(buf).rstrip())
    return [ln for ln in lines if ln.strip()]


def _truncate_last_line_with_ellipsis(
    lines: list[str],
    *,
    max_width_px: int,
    font_size: int,
) -> list[str]:
    if not lines:
        return lines
    last = lines[-1].rstrip()
    if not last:
        return lines

    def _w(s: str) -> float:
        return sum(_char_width(c, font_size=font_size) for c in s)

    if _w(last) <= max_width_px:
        return lines

    ell = "…"
    ell_w = _w(ell)
    kept: list[str] = []
    cur = 0.0
    for ch in last:
        cw = _char_width(ch, font_size=font_size)
        if cur + cw + ell_w > max_width_px:
            break
        kept.append(ch)
        cur += cw
    new_last = "".join(kept).rstrip()
    if new_last and new_last[-1] in _BREAK_BEFORE_PUNCT:
        new_last = new_last[:-1].rstrip()
    lines[-1] = (new_last + ell) if new_last else ell
    return lines


def build_ass(
    segments: list[dict[str, Any]],
    width: int,
    height: int,
    *,
    font_name: str = "Arial",
    font_size: int = 0,
    font_color: str = "#FFFFFF",
    outline_color: str = "#000000",
    shadow_color: str = "#000000",
    outline: float = 1.5,
    shadow: float = 2.0,
    margin_l: int = 0,
    margin_r: int = 0,
    margin_v: int = 0,
    max_lines: int = 2,
) -> str:
    """生成 ASS 字幕文本"""
    font_size = font_size if font_size > 0 else _auto_font_size(width, height)
    margin_l = margin_l if margin_l > 0 else _auto_margin_h(width)
    margin_r = margin_r if margin_r > 0 else _auto_margin_h(width)
    margin_v = margin_v if margin_v > 0 else _auto_margin_v(height)

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font_name},{font_size},{_to_ass_color(font_color)},{_to_ass_color(font_color)},"
        f"{_to_ass_color(outline_color)},{_to_ass_color(shadow_color)},"
        f"0,0,0,0,100,100,0,0,1,{outline:.1f},{shadow:.1f},2,{margin_l},{margin_r},{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for seg in segments:
        start = _sec_to_ass_time(float(seg.get("start", seg.get("start_time", 0))))
        end = _sec_to_ass_time(float(seg.get("end", seg.get("end_time", 0))))
        text = str(seg.get("text", seg.get("Text", ""))).strip()
        if text:
            max_w = max(100, int(width - margin_l - margin_r))
            wrapped = _wrap_text_to_lines(
                text, max_width_px=max_w, font_size=font_size, max_lines=max_lines
            )
            if wrapped:
                wrapped = _truncate_last_line_with_ellipsis(
                    wrapped, max_width_px=max_w, font_size=font_size
                )
                # 注意：ASS 换行控制符是 \N，不能被反斜杠转义为 \\N，否则会显示出一个 "\"
                wrapped_escaped = [_ass_escape_text(line) for line in wrapped]
                ass_text = r"\N".join(wrapped_escaped)
            else:
                # 单行同样需要转义（避免 { } 覆盖标签、\ 控制序列）
                ass_text = _ass_escape_text(text)
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{ass_text}")
    return "\n".join(lines) + "\n"


def burn_subtitles(
    video_in: Path,
    segments: list[dict[str, Any]],
    video_out: Path,
    **style_kwargs,
) -> Path:
    """生成 ASS 并硬压到视频"""
    info = probe_video_info(video_in)
    width = info.get("Width", 1280)
    height = info.get("Height", 720)

    ass_text = build_ass(segments, width, height, **style_kwargs)

    with tempfile.TemporaryDirectory(prefix="burn_sub_") as td:
        ass_path = Path(td) / "subtitle.ass"
        ass_path.write_text(ass_text, encoding="utf-8")
        burn_ass_subtitle(video_in, ass_path, video_out)

    return video_out
