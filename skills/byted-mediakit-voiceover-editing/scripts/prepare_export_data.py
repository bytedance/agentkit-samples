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
Step 6a 数据预处理：将 step6 转为 export_request.json + review_import_data.json，注入真实 URL。
输入：output/step6_speech_cut.json, step3, step1, step5
输出：output/export_request.json, output/review_import_data.json
"""

from __future__ import annotations

import argparse
import json
import re
import os
import uuid
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from project_paths import get_project_root


def _load_skill_env() -> None:
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


def _should_export_video_cut(
    has_subtitle: bool,
    has_mute: bool,
) -> bool:
    """
    是否进行导出视频剪辑（移除 mute 段，主时间轴从 0 起无缝拼接）。
    仅当 TALKING_VIDEO_AUTO_EDIT_VIDEO_CUT=1 且（有字幕 or 有音频静音）时生效。默认 1 进行。
    """
    v = (os.getenv("TALKING_VIDEO_AUTO_EDIT_VIDEO_CUT") or "").strip().lower()
    # 默认开启；仅当显式配置为 0/false/no 时关闭
    if v in ("0", "false", "no"):
        return False
    return has_subtitle or has_mute


_OUTPUT_DIR_OVERRIDE: Path | None = None


def _output_dir() -> Path:
    if _OUTPUT_DIR_OVERRIDE is not None:
        _OUTPUT_DIR_OVERRIDE.mkdir(parents=True, exist_ok=True)
        return _OUTPUT_DIR_OVERRIDE
    out = get_project_root() / "output"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _read_json(name: str) -> Dict[str, Any]:
    path = _output_dir() / name
    if not path.exists():
        raise FileNotFoundError(f"缺少文件: {path}")
    return _parse_json_file(path)


def _parse_json_file(path: Path) -> Any:
    """解析 JSON 文件，失败时抛出带路径和上下文的错误"""
    content = path.read_text(encoding="utf-8")
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        lines = content.split("\n")
        ctx = ""
        if e.lineno and 1 <= e.lineno <= len(lines):
            start = max(0, e.lineno - 2)
            end = min(len(lines), e.lineno + 2)
            ctx = "\n".join(f"  {i + 1}: {lines[i]}" for i in range(start, end))
        raise RuntimeError(
            f"JSON 解析失败: {path}\n{e.msg} (line {e.lineno}, col {e.colno})\n{ctx}"
        ) from e


def _write_json(name: str, data: Any) -> Path:
    path = _output_dir() / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _get_play_url_safe(api: Any, type_: str, source: str, space: str) -> Optional[str]:
    try:
        return api.get_play_url(
            type=type_, source=source, space_name=space, expired_minutes=60
        )
    except Exception:
        return None


# 字幕结尾不携带的标点
_SUBTITLE_TRAILING_PUNCT = "，。！？、；：\"\"''"


def _strip_subtitle_punctuation(text: str) -> str:
    """字幕结尾不携带标点"""
    s = text.rstrip()
    while s and s[-1] in _SUBTITLE_TRAILING_PUNCT:
        s = s[:-1]
    return s


def _sec_to_ms(v: Any) -> int:
    """秒转 ms；float 且 <100 视为秒，否则视为 ms"""
    x = v if isinstance(v, (int, float)) else 0
    return int(x * 1000) if isinstance(x, float) and 0 < x < 100 else int(x)


def _strict_step6_validation_enabled() -> bool:
    """
    Step6a 对 Step5/Step6 产物做强校验（默认开启）。
    设 STEP6A_STRICT_VALIDATE=0/false/no 可关闭（用于紧急绕过历史不规范数据）。
    """
    v = (os.getenv("STEP6A_STRICT_VALIDATE") or "").strip().lower()
    if v in ("0", "false", "no"):
        return False
    return True


def _normalize_rule_name(s: str) -> str:
    """将 rules_read 条目归一化为文件名（忽略路径）。"""
    s2 = (s or "").strip().replace("\\", "/")
    if not s2:
        return ""
    return s2.split("/")[-1]


def _validate_rules_read(step6: Dict[str, Any]) -> List[str]:
    """
    强制要求 step6 顶层带 rules_read 且覆盖 references/用户规则 下 README + 1~10。
    """
    required = [
        "README.md",
        "1-核心原则.md",
        "2-语气词检测.md",
        "3-静音段处理.md",
        "4-重复句检测.md",
        "5-卡顿词.md",
        "6-句内重复检测.md",
        "7-连续语气词.md",
        "8-重说纠正.md",
        "9-残句检测.md",
        "10-顺句词删除.md",
    ]
    rr = step6.get("rules_read")
    if not isinstance(rr, list) or not rr:
        return [
            "[强校验] step6 顶层缺少 rules_read（或为空）。"
            "请按 Step5 要求在 step6_speech_cut.json 顶层写入 rules_read/rules_applied/rules_version_note。"
        ]
    got = {_normalize_rule_name(x) for x in rr if isinstance(x, str)}
    got.discard("")
    missing = [x for x in required if x not in got]
    if missing:
        return [
            "[强校验] rules_read 不完整，缺少: "
            + ", ".join(missing)
            + "。请按 Step5 强制阅读清单补齐。"
        ]
    return []


def _validate_concat_action_time(step6: Dict[str, Any]) -> List[str]:
    """
    防止“被删内容仍播放/音频重复”的典型根因：
    - concat.actionTime 必须为仅保留区间
    - actionTime spans 必须递增、互不重叠、且处于 segment 源时间范围内
    """
    issues: List[str] = []
    segments = step6.get("optimized_segments") or step6.get("sentences") or []
    if not isinstance(segments, list):
        return issues

    for idx, seg in enumerate(segments):
        if not isinstance(seg, dict):
            continue
        action = (seg.get("action") or "").lower()
        if action != "concat":
            continue
        action_time = seg.get("actionTime")
        if not isinstance(action_time, list) or not action_time:
            issues.append(f"[强校验] concat 段缺少 actionTime: segment_idx={idx}")
            continue
        seg_start = int(seg.get("start_time") or 0)
        seg_end = int(seg.get("end_time") or 0)
        spans: list[tuple[int, int]] = []
        for j, s in enumerate(action_time):
            if not isinstance(s, dict):
                issues.append(f"[强校验] actionTime[{j}] 非对象: segment_idx={idx}")
                continue
            st = int(s.get("start_time") or 0)
            et = int(s.get("end_time") or 0)
            if et <= st:
                issues.append(
                    f"[强校验] actionTime[{j}] end<=start: segment_idx={idx} span=({st}-{et})"
                )
                continue
            spans.append((st, et))

        if not spans:
            continue
        spans.sort(key=lambda x: x[0])
        # 不重叠、递增（允许相邻贴边）
        for (s0, e0), (s1, e1) in zip(spans, spans[1:]):
            if s1 < e0:
                issues.append(
                    f"[强校验] concat actionTime spans 重叠: segment_idx={idx} prev=({s0}-{e0}) next=({s1}-{e1})"
                )
                break
        # 必须处于 segment 范围内（允许容差 50ms）
        tol = 50
        min_s = spans[0][0]
        max_e = spans[-1][1]
        if seg_end > 0 and (min_s < seg_start - tol or max_e > seg_end + tol):
            issues.append(
                f"[强校验] concat actionTime 越界: segment_idx={idx} "
                f"segment=({seg_start}-{seg_end}) keep=({min_s}-{max_e})"
            )
    return issues


def _step6_fingerprint(step6_path: Path) -> Dict[str, Any]:
    """
    计算 step6 文件指纹，用于防止“改了 step6 但没重跑 Step6a”：
    - path: 绝对路径
    - mtime_ms: 修改时间（毫秒）
    - sha1: 文件内容 sha1（40 hex）
    """
    data = step6_path.read_bytes()
    return {
        "path": str(step6_path.resolve()),
        "mtime_ms": int(step6_path.stat().st_mtime * 1000),
        "sha1": hashlib.sha1(data).hexdigest(),
    }


def _correct_segment_times_from_step5(
    step6_segments: List[Dict],
    step5_segments: List[Dict],
) -> None:
    """
    以 step5 字级时间戳为准：segment 的 start/end 取首字出现和末字结束时间。
    支持 step6 合并多段 step5 的情况（按时间重叠匹配）。
    """
    for seg in step6_segments:
        action = (seg.get("action") or "keep").lower()
        if action == "concat":
            continue  # concat 以 Agent/step6 为准，不校正，避免覆盖正确删前留后区间
        if action != "keep":
            continue
        seg_start = int(seg.get("start_time") or 0)
        seg_end = int(seg.get("end_time") or 0)
        first_ms = 999999999
        last_ms = 0
        found = False
        seg_start_safe = max(0, seg_start)  # 负值按 0 处理，避免 overlap 漏匹配
        for s5 in step5_segments:
            s5_start = _sec_to_ms(s5.get("start_time"))
            s5_end = _sec_to_ms(s5.get("end_time"))
            if s5_end <= seg_start_safe or s5_start >= seg_end:
                continue
            words = s5.get("words") or []
            valid_words = [
                w
                for w in words
                if (
                    int(w.get("start_time") or -1) >= 0
                    and int(w.get("end_time") or -1) >= 0
                )
            ]
            if not valid_words:
                continue
            found = True
            w_first = min(int(w.get("start_time") or 0) for w in valid_words)
            w_last = max(int(w.get("end_time") or 0) for w in valid_words)
            first_ms = min(first_ms, w_first)
            last_ms = max(last_ms, w_last)
        if found and action == "keep":
            action_time = seg.get("actionTime") or []
            if action_time:
                action_time[0]["start_time"] = first_ms
                action_time[-1]["end_time"] = last_ms
            seg["start_time"] = first_ms
            seg["end_time"] = last_ms


def _text_from_step5_words(
    step5_segments: List[Dict], start_ms: int, end_ms: int
) -> str:
    """从 step5 words 中按时间范围提取文本"""
    chars = []
    for s5 in step5_segments:
        for w in s5.get("words") or []:
            ws = int(w.get("start_time") or -1)
            we = int(w.get("end_time") or -1)
            if ws < 0 or we < 0:
                continue
            if we <= start_ms or ws >= end_ms:
                continue
            chars.append(str(w.get("text") or ""))
    return _strip_subtitle_punctuation("".join(chars))


def _first_speech_start_ms(step5_segments: List[Dict]) -> int:
    """首个有字级时间戳的 segment 的首字 start_time（ms）"""
    for s5 in step5_segments:
        words = [
            w for w in (s5.get("words") or []) if int(w.get("start_time") or -1) >= 0
        ]
        if words:
            return min(int(w.get("start_time") or 0) for w in words)
    return 0


def _expand_concat_segments(
    segments: List[Dict],
    step5_segments: List[Dict],
    deleted_parts: Optional[List[Dict]] = None,
) -> List[Dict]:
    """
    将 concat 段展开为三段：保留 + 静音(间隙) + 保留。
    静音段为 actionTime 各 span 之间的间隙，action 为 mute。
    开头静音：以 step5 首字 start_time 为准，覆盖 0 到首字前的全部静音。
    deleted_parts：用于 fallback：当 seg_start 误写成保留区起始时，从此查找删前区间。
    """
    GAP_MIN_MS = 50  # 间隙超过此值才插入静音段
    first_speech_ms = _first_speech_start_ms(step5_segments)
    expanded = []

    def _fix_leading_mute(seg: Dict) -> Dict:
        """开头静音：end_time 应延伸至首字 start_time（如 630），而非 ASR utterance 的 230"""
        if (seg.get("action") or "").lower() != "mute":
            return seg
        st = int(seg.get("start_time") or 0)
        et = int(seg.get("end_time") or 0)
        if st == 0 and et < first_speech_ms and first_speech_ms > 0:
            out = dict(seg)
            out["end_time"] = first_speech_ms
            at = out.get("actionTime") or []
            if at:
                at = [{**at[0], "end_time": first_speech_ms}]
            out["actionTime"] = at
            out["reason"] = f"开头 0-{first_speech_ms}ms 无说话，音频做静音处理"
            return out
        return seg

    for seg in segments:
        action = (seg.get("action") or "keep").lower()
        if action != "concat":
            expanded.append(_fix_leading_mute(seg))
            continue
        action_time = seg.get("actionTime") or []
        seg_start = int(seg.get("start_time") or 0)
        seg_end = int(seg.get("end_time") or 0)
        if not action_time:
            expanded.append(seg)
            continue
        spans = [
            (int(s.get("start_time") or 0), int(s.get("end_time") or 0))
            for s in action_time
        ]
        spans.sort(key=lambda x: x[0])
        # 删前留后：仅 1 个 span 且在 keep 前有删前内容 → 插入 leading mute
        span_start = spans[0][0]
        leading_s, leading_e = None, None
        if seg_start < span_start:
            leading_s, leading_e = seg_start, span_start
        elif deleted_parts and len(spans) == 1:
            # fallback：seg_start 误写成保留区起始时，从 deleted_parts 查找与 source_text 对应的删前区间
            src = (seg.get("source_text") or "").strip()
            for d in deleted_parts:
                ds = int(d.get("start_time") or 0)
                de = int(d.get("end_time") or 0)
                dt = (d.get("deleted_text") or "").strip()
                if (
                    ds < span_start
                    and de <= span_start + 100
                    and src
                    and dt
                    and dt in src
                ):
                    leading_s, leading_e = ds, span_start
                    break
        if leading_s is not None and leading_e is not None:
            muted_text = _text_from_step5_words(step5_segments, leading_s, leading_e)
            leading_reason = (
                f"句内静音 {leading_s}-{leading_e}ms，删除「{muted_text}」"
                if muted_text
                else f"句内静音 {leading_s}-{leading_e}ms，无说话，静音处理"
            )
            expanded.append(
                {
                    "text": muted_text or "",
                    "source_text": muted_text or "",
                    "start_time": leading_s,
                    "end_time": leading_e,
                    "reason": leading_reason,
                    "action": "mute",
                    "actionTime": [{"start_time": leading_s, "end_time": leading_e}],
                }
            )
            expanded.append(
                {
                    "text": _text_from_step5_words(
                        step5_segments, spans[0][0], spans[0][1]
                    ),
                    "source_text": seg.get("source_text", ""),
                    "start_time": spans[0][0],
                    "end_time": spans[0][1],
                    "reason": seg.get("reason", ""),
                    "action": "keep",
                    "actionTime": [
                        {"start_time": spans[0][0], "end_time": spans[0][1]}
                    ],
                }
            )
            continue
        if len(spans) < 2:
            expanded.append(seg)
            continue
        for i, (s, e) in enumerate(spans):
            expanded.append(
                {
                    "text": _text_from_step5_words(step5_segments, s, e),
                    "source_text": seg.get("source_text", ""),
                    "start_time": s,
                    "end_time": e,
                    "reason": seg.get("reason", ""),
                    "action": "keep",
                    "actionTime": [{"start_time": s, "end_time": e}],
                }
            )
            if i + 1 < len(spans):
                gap_s = e
                gap_e = spans[i + 1][0]
                if gap_e - gap_s >= GAP_MIN_MS:
                    muted_text = _text_from_step5_words(step5_segments, gap_s, gap_e)
                    reason = (
                        f"句内静音 {gap_s}-{gap_e}ms，删除「{muted_text}」"
                        if muted_text
                        else f"句内静音 {gap_s}-{gap_e}ms，无说话，静音处理"
                    )
                    expanded.append(
                        {
                            "text": muted_text or "",
                            "source_text": muted_text or "",
                            "start_time": gap_s,
                            "end_time": gap_e,
                            "reason": reason,
                            "action": "mute",
                            "actionTime": [{"start_time": gap_s, "end_time": gap_e}],
                        }
                    )
    # 若首个有效段起始 > 0，补全开头静音（以 step5 首字为准，覆盖 0 到首字前）
    if expanded and first_speech_ms > 0:
        first = expanded[0]
        first_start = int(first.get("start_time") or 0)
        first_is_leading_mute = (
            (first.get("action") or "").lower() == "mute"
            and first_start == 0
            and int(first.get("end_time") or 0) >= first_speech_ms
        )
        if first_start > 0 and not first_is_leading_mute:
            # 首个段起始 > 0 且非已覆盖 0~首字的 mute，插入开头静音
            leading_muted_text = _text_from_step5_words(
                step5_segments, 0, first_speech_ms
            )
            leading_reason = (
                f"开头 0-{first_speech_ms}ms 无说话，静音处理（无内容）"
                if not leading_muted_text
                else f"开头 0-{first_speech_ms}ms，删除「{leading_muted_text}」"
            )
            expanded.insert(
                0,
                {
                    "text": leading_muted_text or "",
                    "source_text": leading_muted_text or "",
                    "start_time": 0,
                    "end_time": first_speech_ms,
                    "reason": leading_reason,
                    "action": "mute",
                    "actionTime": [{"start_time": 0, "end_time": first_speech_ms}],
                },
            )
    return expanded


def _fix_overlap(expanded: List[Dict]) -> List[Dict]:
    """消除 mute 与 keep 的重叠：mute 的 start/end 裁剪到与前后的间隙内"""
    out = []
    for i, seg in enumerate(expanded):
        if (seg.get("action") or "").lower() != "mute":
            out.append(dict(seg))
            continue
        st = int(seg.get("start_time") or 0)
        et = int(seg.get("end_time") or 0)
        prev_end = int(out[-1]["end_time"]) if out else 0
        next_start = (
            int(expanded[i + 1]["start_time"]) if i + 1 < len(expanded) else et + 1
        )
        st = max(st, prev_end)
        et = min(et, next_start)
        if et > st:
            fixed = {**seg, "start_time": st, "end_time": et}
            fixed["actionTime"] = [{"start_time": st, "end_time": et}]
            out.append(fixed)
    return out


def _extract_removed_from_reason(reason: str) -> str:
    """从 reason 提取 去掉「xxx」/删除「xxx」中的 xxx，多个用顿号拼接"""
    if not reason:
        return ""
    parts = re.findall(r"[去掉刪除]「([^」]+)」", reason)
    return "、".join(p.strip() for p in parts) if parts else ""


def _build_sentences(
    segments: List[Dict],
    step5_segments: Optional[List[Dict]] = None,
    seg_output_range: Optional[Dict[int, Tuple[int, int]]] = None,
    deleted_parts: Optional[List[Dict]] = None,
) -> List[Dict]:
    """从 optimized_segments 生成 review 页 sentences，concat 展开为 保留+静音+保留"""
    STATUS_REMOVED = "removed"
    STATUS_MUTED = "muted"
    STATUS_KEEP = "keep"
    s5 = step5_segments or []
    expanded = _expand_concat_segments(segments, s5, deleted_parts or [])
    expanded = _fix_overlap(expanded)
    out = []
    for i, seg in enumerate(expanded):
        action = (seg.get("action") or "keep").lower()
        status = (
            STATUS_REMOVED
            if action == "delete"
            else (STATUS_MUTED if action == "mute" else STATUS_KEEP)
        )
        start_ms = int(seg.get("start_time") or 0)
        end_ms = int(seg.get("end_time") or 0)
        out_start = start_ms / 1000.0
        out_end = end_ms / 1000.0
        if seg_output_range and i in seg_output_range:
            o0, o1 = seg_output_range[i]
            out_start = o0 / 1000.0
            out_end = o1 / 1000.0
        reason = seg.get("reason") or ""
        reason_tags = (
            [reason] if reason and status in (STATUS_KEEP, STATUS_MUTED) else []
        )
        raw_text = seg.get("text") or seg.get("source_text") or ""
        text = _strip_subtitle_punctuation(str(raw_text))
        if (
            status == STATUS_MUTED
            and reason
            and text
            and (text == reason or (len(text) > 10 and reason in text))
        ):
            text = ""
        removed_text = (
            text
            if status == STATUS_MUTED and text
            else (
                reason
                if status == STATUS_MUTED and reason
                else _extract_removed_from_reason(reason)
            )
        )
        item = {
            "id": str(i + 1),
            "start": out_start,
            "end": out_end,
            "text": text,
            "status": status,
            "reasonTags": reason_tags,
            "operations": [],
        }
        if removed_text:
            item["removedText"] = removed_text
        out.append(item)
    return out


def _build_voice_trim_segments(
    segments: List[Dict],
    step5_segments: Optional[List[Dict]] = None,
    deleted_parts: Optional[List[Dict]] = None,
) -> Tuple[List[Dict], Dict[int, Tuple[int, int]]]:
    """
    生成人声轨的 trim 片段，与 _expand_concat_segments 保持一致（含 concat 间隙静音、开头静音），
    确保人声轨与字幕轨时长对齐。
    - keep/concat: 原样保留，concat 的 span 间隙插入静音段
    - mute: 静音段，输出为 a_volume:0
    - delete: 不参与输出
    返回 (voice_segments, segment_idx_to_source_range)
    """
    s5 = step5_segments or []
    expanded = _expand_concat_segments(segments, s5, deleted_parts or [])
    expanded = _fix_overlap(expanded)
    result = []
    seg_source_range: Dict[int, Tuple[int, int]] = {}
    for i, seg in enumerate(expanded):
        action = (seg.get("action") or "keep").lower()
        if action == "delete":
            continue
        action_time = seg.get("actionTime") or []
        is_mute = action == "mute"
        for span in action_time:
            s = int(span.get("start_time") or 0)
            e = int(span.get("end_time") or 0)
            result.append(
                {
                    "target_start_ms": s,
                    "target_end_ms": e,
                    "trim_start_ms": s,
                    "trim_end_ms": e,
                    "is_mute": is_mute,
                    "segment_idx": i,
                }
            )
            if i not in seg_source_range:
                seg_source_range[i] = (s, e)
            else:
                lo, hi = seg_source_range[i]
                seg_source_range[i] = (min(lo, s), max(hi, e))
    result.sort(key=lambda x: x["target_start_ms"])
    return result, seg_source_range


def _apply_time_compensation(voice_segments: List[Dict]) -> None:
    """有留白时，前段结尾 +10ms 补偿"""
    GAP_MS = 10
    for i, vs in enumerate(voice_segments):
        next_start = (
            voice_segments[i + 1]["target_start_ms"]
            if i + 1 < len(voice_segments)
            else vs["target_end_ms"]
        )
        gap = next_start - vs["target_end_ms"]
        if gap > 0:
            add = min(GAP_MS, gap)
            vs["trim_end_ms"] += add
            vs["target_end_ms"] += add


def _rebuild_seg_source_range(voice_segments: List[Dict]) -> Dict[int, Tuple[int, int]]:
    """从补偿后的 voice_segments 重建 seg_source_range（供字幕 TargetTime）"""
    out: Dict[int, Tuple[int, int]] = {}
    for vs in voice_segments:
        idx = vs["segment_idx"]
        s, e = vs["target_start_ms"], vs["target_end_ms"]
        if idx not in out:
            out[idx] = (s, e)
        else:
            lo, hi = out[idx]
            out[idx] = (min(lo, s), max(hi, e))
    return out


def _delete_range_matches(
    delete_range: Tuple[int, int, str],
    d: Dict[str, Any],
) -> bool:
    """判断 delete 段是否与 deleted_part 匹配（时间容差 50ms 或文本重叠）"""
    st, et, src = delete_range
    ds = int(d.get("start_time") or 0)
    de = int(d.get("end_time") or 0)
    dt = (d.get("deleted_text") or "").strip()
    # 时间匹配：容差 50ms
    if abs(ds - st) <= 50 and abs(de - et) <= 50:
        return True
    # 时间重叠：重叠 ≥ 80% 的 delete 段时长
    overlap = max(0, min(et, de) - max(st, ds))
    if et > st and overlap >= 0.8 * (et - st):
        return True
    # 文本匹配：source_text 与 deleted_text 一致或包含
    if src and dt and (src == dt or dt in src or src in dt):
        return True
    return False


def _validate_step6(step6: Dict[str, Any]) -> List[str]:
    """
    自检 step6：delete 段应出现在 deleted_parts，语义重复删除应有对应描述。
    返回错误/警告列表。
    """
    issues: List[str] = []
    segments = step6.get("optimized_segments") or step6.get("sentences") or []
    deleted_parts = step6.get("deleted_parts") or []

    # 收集所有 delete 段的时间范围
    delete_ranges = []
    for seg in segments:
        if (seg.get("action") or "").lower() == "delete":
            st = int(seg.get("start_time") or 0)
            et = int(seg.get("end_time") or 0)
            src = (seg.get("source_text") or "").strip()
            delete_ranges.append((st, et, src))

    # 检查每个 delete 段是否在 deleted_parts 中（时间容差 50ms，或文本重叠视为匹配）
    for st, et, src in delete_ranges:
        matched = any(_delete_range_matches((st, et, src), d) for d in deleted_parts)
        if not matched and src:
            issues.append(
                f"[自检] delete 段 ({st}-{et}) 未在 deleted_parts 中: {src[:30]}... "
                f'请在 deleted_parts 中添加: {{"deleted_text": "...", "description": "...", "start_time": {st}, "end_time": {et}}}'
            )

    return issues


def _element_id(prefix: str, i: int) -> str:
    return f"{prefix}{i:04d}"


def _global_unique_id() -> str:
    """生成全局唯一 ID"""
    return uuid.uuid4().hex[:12]


def _resolve_existing_file_path(path_str: str, output_dir: Path) -> str:
    """解析为磁盘上存在的绝对路径字符串；否则返回原串（供 URL 编码尝试）。"""
    if not path_str or not str(path_str).strip():
        return ""
    p = Path(path_str.strip())
    if p.is_file():
        return str(p.resolve())
    cand = output_dir / path_str.strip()
    if cand.is_file():
        return str(cand.resolve())
    return str(path_str).strip()


def _local_media_url(local_path: str, host: str, port: int) -> str:
    """将本地文件路径转换为审核页可访问的 HTTP URL（须与 serve_review_page /local-media 一致）。"""
    from urllib.parse import quote

    if not local_path:
        return ""
    # quote 默认 safe='/'，保留路径分隔符，便于服务端匹配 /local-media/...
    return f"http://{host}:{port}/local-media{quote(local_path)}"


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """合并重叠区间（ms）。"""
    cleaned = [(int(s), int(e)) for s, e in intervals if int(e) > int(s)]
    if not cleaned:
        return []
    cleaned.sort(key=lambda x: x[0])
    merged: list[tuple[int, int]] = [cleaned[0]]
    for s, e in cleaned[1:]:
        ps, pe = merged[-1]
        if s <= pe:
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))
    return merged


def _clip_text_lane_to_intervals(
    text_lane: list[dict], intervals: list[tuple[int, int]]
) -> list[dict]:
    """
    将字幕 text_lane 裁剪到有效音频区间，避免“无音频但有字幕”：
    - 不相交：丢弃
    - 部分相交：裁剪 TargetTime
    - 跨多个区间：拆分为多个 text 元素（文本相同，时间各自裁剪）
    """
    ivs = _merge_intervals(intervals)
    if not ivs or not text_lane:
        return []

    out: list[dict] = []
    for el in text_lane:
        tt = el.get("TargetTime") or []
        if not isinstance(tt, list) or len(tt) < 2:
            continue
        s0, e0 = int(tt[0]), int(tt[1])
        if e0 <= s0:
            continue
        for s1, e1 in ivs:
            s = max(s0, s1)
            e = min(e0, e1)
            if e > s:
                el2 = dict(el)
                el2["TargetTime"] = [s, e]
                out.append(el2)
    return out


def main() -> None:
    global _OUTPUT_DIR_OVERRIDE
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--step6", default="step6_speech_cut.json", help="step6 JSON 文件名"
    )
    parser.add_argument(
        "--review", default="review_import_data.json", help="review JSON 输出文件名"
    )
    parser.add_argument(
        "--export", default="export_request.json", help="export JSON 输出文件名"
    )
    parser.add_argument("--width", type=int, default=0, help="画布宽度，0 表示自动")
    parser.add_argument("--height", type=int, default=0, help="画布高度，0 表示自动")
    parser.add_argument(
        "--write-step6",
        action="store_true",
        help="将修正后的数据写回 step6 文件（去除 mute、校正时间）",
    )
    parser.add_argument(
        "--platform-selection",
        default="platform_selection.json",
        help="平台选择 JSON（可选，若存在则用其 canvas/video_source）",
    )
    parser.add_argument(
        "--output-dir", default="", help="输出目录，默认 output；可指定 output/<文件名>"
    )
    parser.add_argument(
        "--review-host",
        default="127.0.0.1",
        help="审核页服务地址（local 模式用于生成媒体 URL）",
    )
    parser.add_argument(
        "--review-port",
        type=int,
        default=5173,
        help="审核页服务端口（local 模式用于生成媒体 URL）",
    )
    parser.add_argument(
        "--direct-export",
        action="store_true",
        help="local 模式下跳过审核页直接导出最终视频",
    )
    args = parser.parse_args()

    if args.output_dir:
        out_str = str(args.output_dir).strip()
        proj_root = get_project_root()
        out_base = (proj_root / "output").resolve()
        cand = Path(out_str)

        if cand.is_absolute():
            resolved = cand.resolve()
            try:
                resolved.relative_to(out_base)
            except ValueError:
                raise SystemExit(
                    f"ERROR: --output-dir 必须在 {out_base} 下：{resolved}"
                )
            _OUTPUT_DIR_OVERRIDE = resolved
        else:
            # 约束：只允许 output/<文件名>（相对路径）
            if not out_str.startswith("output/"):
                raise SystemExit(
                    "ERROR: --output-dir 只允许传 `output/<文件名>`（相对路径）"
                )
            resolved = (proj_root / out_str).resolve()
            try:
                resolved.relative_to(out_base)
            except ValueError:
                raise SystemExit(f"ERROR: --output-dir 路径越界：{out_str}")
            _OUTPUT_DIR_OVERRIDE = resolved

        _OUTPUT_DIR_OVERRIDE.mkdir(parents=True, exist_ok=True)
    else:
        from output_dir_resolve import infer_prepare_output_dir

        out_root = get_project_root() / "output"
        if out_root.exists():
            subdirs = [
                d
                for d in out_root.iterdir()
                if d.is_dir() and (d / args.step6).exists()
            ]
            if len(subdirs) > 1:
                print(
                    f"[提示] 检测到多个目录含 {args.step6}: {[d.name for d in subdirs]}，"
                    f"将按文件修改时间选用最新一份；建议显式使用 --output-dir output/<目录名>"
                )
        _OUTPUT_DIR_OVERRIDE = infer_prepare_output_dir(args.step6)
        _OUTPUT_DIR_OVERRIDE.mkdir(parents=True, exist_ok=True)

    _load_skill_env()
    space = os.getenv("VOLC_SPACE_NAME", "").strip()

    # 检测执行模式：优先用 execution_mode 自动检测（基于当前环境变量），
    # 不依赖 step1 历史数据（上次 local 模式的 step1 不应锁定本次模式）
    is_local = False
    _env_is_apig = False
    try:
        from execution_mode import resolve_mode, ExecutionMode

        _current_mode = resolve_mode(interactive=False)
        is_local = _current_mode == ExecutionMode.LOCAL
        _env_is_apig = _current_mode == ExecutionMode.APIG
    except Exception:
        # fallback: 检查 step1（仅当 resolve_mode 不可用时）
        step1_check_path = _output_dir() / "step1_preuploaded.json"
        if step1_check_path.exists():
            _s1_tmp = _parse_json_file(step1_check_path)
            if (
                _s1_tmp.get("_execution_mode") == "local"
                or _s1_tmp.get("AssetType") == "LocalFile"
            ):
                is_local = True

    step6_path = _output_dir() / args.step6
    if not step6_path.exists():
        raise FileNotFoundError(f"缺少文件: {step6_path}")
    step6 = _parse_json_file(step6_path)
    step3 = _read_json("step3_voice_separation_result.json")
    step1 = _read_json("step1_preuploaded.json")
    step5_path = _output_dir() / "step5_play_url.json"
    step5 = _parse_json_file(step5_path) if step5_path.exists() else {}

    # 兼容 optimized_segments 与 sentences 两种格式
    segments = step6.get("optimized_segments") or step6.get("sentences") or []

    # step6 指纹：写入到 review/export 产物，供后续导出时校验
    step6_fp = _step6_fingerprint(step6_path)

    # 强校验（默认开启）：阻断“宿主跳读规则/concat actionTime 不规范”导致的音频重复/被删仍播
    if _strict_step6_validation_enabled():
        strict_issues: List[str] = []
        strict_issues.extend(_validate_rules_read(step6))
        strict_issues.extend(_validate_concat_action_time(step6))
        if strict_issues:
            msg = "\n".join(strict_issues)
            raise SystemExit(
                "ERROR: Step6a 强校验失败（请回到 Step5 修正 step6_speech_cut.json 后重试）。\n"
                + msg
                + "\n\n如需临时绕过（不建议），可设置环境变量 STEP6A_STRICT_VALIDATE=0"
            )

    # 自检：delete 段需在 deleted_parts 中
    for msg in _validate_step6(step6):
        print(msg)

    # 1a. 以 step5 字级时间戳为准修正 segment 起止时间（首字出现、末字结束）
    s5_segs = []
    step5_opt_path = _output_dir() / "step5_asr_optimized.json"
    if step5_opt_path.exists():
        step5_opt = _parse_json_file(step5_opt_path)
        s5_segs = step5_opt.get("optimized_segments") or []
    else:
        # 回退：从 step5_asr_raw_*.json 的 utterances 提取
        for raw_path in sorted(_output_dir().glob("step5_asr_raw_*.json")):
            raw = _parse_json_file(raw_path)
            for u in raw.get("result", {}).get("utterances", []):
                words = u.get("words") or []
                if words:
                    s5_segs.append(
                        {
                            "start_time": u.get("start_time", 0),
                            "end_time": u.get("end_time", 0),
                            "words": [
                                {
                                    "start_time": w.get("start_time", 0),
                                    "end_time": w.get("end_time", 0),
                                }
                                for w in words
                            ],
                        }
                    )
            break
    if s5_segs:
        _correct_segment_times_from_step5(segments, s5_segs)

    # 可选：将修正后的数据写回 step6（去除 mute、已校正时间）
    if args.write_step6:
        seg_key = "optimized_segments" if "optimized_segments" in step6 else "sentences"
        filtered = [
            s for s in segments if (s.get("action") or "keep").lower() != "mute"
        ]
        step6_out = {**step6, seg_key: filtered}
        _write_json(args.step6, step6_out)
        print(
            f"[OK] 已写回 output/{args.step6}（去除 {len(segments) - len(filtered)} 个 mute 段，时间已校正）"
        )

    # URL 解析：local 模式无需 ApiManage/VOD，直接使用本地路径
    api = None
    if is_local:
        print("[信息] local 模式：使用本地文件路径，跳过 VOD API")
    elif space:
        try:
            from api_manage import ApiManage

            api = ApiManage()
        except Exception as e:
            print(f"[警告] ApiManage 加载失败，将尽量使用 JSON 内已有 URL: {e}")

    # 优先使用 platform_selection（Step 5.5 产出，含超分后视频源与画布）
    platform_path = _output_dir() / args.platform_selection
    vid = step1.get("Vid") or step1.get("AssetValue", "")
    video_directurl = step1.get("DirectUrl") or ""
    video_url = step1.get("PlayURL", "")
    if platform_path.exists():
        try:
            plat = _parse_json_file(platform_path)
            vs = plat.get("video_source") or {}
            if vs.get("Vid"):
                vid = vs.get("Vid")
                video_directurl = ""
            elif vs.get("DirectUrl"):
                video_directurl = vs.get("DirectUrl", "")
                vid = ""
            if vs.get("Url"):
                video_url = vs.get("Url", "")
            if (
                plat.get("canvas_width")
                and plat.get("canvas_height")
                and args.width <= 0
                and args.height <= 0
            ):
                args.width = int(plat["canvas_width"])
                args.height = int(plat["canvas_height"])
        except Exception as e:
            print(f"[警告] 读取 platform_selection 失败: {e}")
    if not video_url and api and space:
        if vid:
            video_url = _get_play_url_safe(api, "vid", vid, space)
        elif video_directurl:
            video_url = _get_play_url_safe(api, "directurl", video_directurl, space)
    if not video_url:
        video_url = step1.get("PlayURL", "")
    if not video_url:
        raise ValueError("无法获取主视频 PlayURL，请检查 step1_preuploaded.json")

    # 1. 数据预处理前获取视频源信息（宽高），未指定平台时用原始框高
    video_width, video_height = 1280, 2160  # 默认
    if is_local and (args.width <= 0 or args.height <= 0):
        local_source = step1.get("LocalPath") or step1.get("AssetValue", "")
        if local_source and Path(local_source).is_file():
            try:
                from ffmpeg_utils import probe_video_info

                info = probe_video_info(Path(local_source))
                video_width = int(info.get("Width") or 1280)
                video_height = int(info.get("Height") or 2160)
            except Exception as e:
                print(f"[警告] 获取本地视频尺寸失败，使用默认: {e}")
    elif api and space and (args.width <= 0 or args.height <= 0):
        try:
            if vid:
                info = api.get_play_video_info(vid, space)
                video_width = int(info.get("Width") or 1280)
                video_height = int(info.get("Height") or 2160)
            elif video_directurl:
                info = api.get_video_audio_info("directurl", video_directurl, space)
                video_width = int(info.get("Width") or 1280)
                video_height = int(info.get("Height") or 2160)
        except Exception as e:
            print(f"[警告] 获取视频尺寸失败，使用默认: {e}")
    if video_width <= 0:
        video_width = 1280
    if video_height <= 0:
        video_height = 2160
    if args.width > 0 and args.height > 0:
        video_width, video_height = args.width, args.height

    audio_urls = step3.get("AudioUrls") or []
    voice_info = next(
        (a for a in audio_urls if (a.get("Type") or "").lower() == "voice"), {}
    )
    bg_info = next(
        (a for a in audio_urls if (a.get("Type") or "").lower() == "background"), {}
    )

    # 人声轨必须用 step5（降噪后），ASR 与 actionTime 均基于此
    voice_url = step5.get("PlayURL") or voice_info.get("Url", "")
    voice_direct = step5.get("DirectUrl") or voice_info.get("DirectUrl", "")
    if not voice_url and api and voice_direct and space:
        voice_url = _get_play_url_safe(api, "directurl", voice_direct, space)
    if not voice_url:
        voice_url = voice_info.get("Url") or step5.get("PlayURL", "")

    bg_url = bg_info.get("Url", "")
    bg_direct = bg_info.get("DirectUrl", "")
    if not bg_url and api and bg_direct and space:
        bg_url = _get_play_url_safe(api, "directurl", bg_direct, space)
    if not bg_url:
        bg_url = bg_info.get("Url", "")

    # local 模式：为审核页生成 HTTP 可访问的媒体 URL（解析 output 下相对路径）
    if is_local:
        _rh, _rp = args.review_host, args.review_port
        _od = _output_dir()
        v_for_preview = (
            _resolve_existing_file_path(str(video_url), _od) if video_url else ""
        )
        vo_for_preview = (
            _resolve_existing_file_path(str(voice_url), _od) if voice_url else ""
        )
        if not vo_for_preview and voice_direct:
            vo_for_preview = _resolve_existing_file_path(str(voice_direct), _od)
        bg_for_preview = _resolve_existing_file_path(str(bg_url), _od) if bg_url else ""
        if not bg_for_preview and bg_direct:
            bg_for_preview = _resolve_existing_file_path(str(bg_direct), _od)
        video_review_url = (
            _local_media_url(v_for_preview, _rh, _rp) if v_for_preview else ""
        )
        voice_review_url = (
            _local_media_url(vo_for_preview, _rh, _rp) if vo_for_preview else ""
        )
        bg_review_url = (
            _local_media_url(bg_for_preview, _rh, _rp) if bg_for_preview else ""
        )
    else:
        video_review_url = video_url
        voice_review_url = voice_url
        bg_review_url = bg_url

    # 总时长 (ms) - 取最后 segment 的 end_time
    total_ms = max((int(s.get("end_time") or 0) for s in segments), default=0)

    # Voice trim 片段（concat 的每个 actionTime span 独立为一段）
    # TargetTime 使用 step6 源时间 start_time/end_time，与 trim 一致
    deleted_parts = step6.get("deleted_parts") or []
    voice_segments, seg_source_range = _build_voice_trim_segments(
        segments, s5_segs, deleted_parts
    )
    _apply_time_compensation(voice_segments)
    seg_source_range = _rebuild_seg_source_range(voice_segments)

    # Sentences 使用 step6 源时间，concat 展开为 保留+静音(间隙)+保留（展开后每段自有时长，不再用 seg_source_range）
    sentences = _build_sentences(
        segments,
        step5_segments=s5_segs,
        seg_output_range=None,
        deleted_parts=deleted_parts,
    )

    # 视频轨（单元素，全时长），主视频自带音轨需静音（人声/背景由独立轨提供）
    # Extra 含 transform（参考 review_import_data 489-501 完整结构）与 a_volume，均带全局唯一 ID
    vid_id = _element_id("vid", 0)
    video_transform = {
        "ID": _global_unique_id(),
        "Type": "transform",
        "Width": video_width,
        "Height": video_height,
        "PosX": 0,
        "PosY": 0,
        "Rotation": 0,
        "FlipX": False,
        "FlipY": False,
        "ScaleX": 1,
        "ScaleY": 1,
    }
    video_volume = {
        "ID": _global_unique_id(),
        "Type": "a_volume",
        "Volume": 0,
    }
    if is_local:
        local_video_path = step1.get("LocalPath") or step1.get("AssetValue", "")
        video_source_raw = local_video_path or vid or ""
        video_source = (
            _local_media_url(local_video_path, _rh, _rp)
            if local_video_path
            else video_source_raw
        )
    else:
        video_source = (
            f"vid://{vid}"
            if vid
            else (
                f"directurl://{video_directurl}"
                if video_directurl
                else "directurl://video"
            )
        )
        video_source_raw = video_source  # cloud/apig 无需区分
    video_lane = [
        {
            "ID": vid_id,
            "Type": "video",
            "Source": video_source,
            "TargetTime": [0, total_ms],
            "Extra": [video_transform, video_volume],
            "UserData": {
                "id": vid_id,
                "name": "main",
                "source": video_source,
                "type": "video",
                "url": video_review_url,
                "width": video_width,
                "height": video_height,
                "aspectRatio": video_width / video_height if video_height else 1,
                "originalDuration": total_ms / 1000.0,
                "laneLabel": "视频",
            },
        }
    ]

    # 人声轨（多个 trim 片段），严格遵守 step6 action：mute → a_volume:0
    # UserData.status='muted' 供审核页展示静音段样式（与字幕轨一致）
    # Extra 子项均带唯一 ID
    voice_lane = []
    for i, vs in enumerate(voice_segments):
        voice_id = _element_id("voice", i)
        extra = [
            {
                "ID": _global_unique_id(),
                "Type": "trim",
                "StartTime": vs["trim_start_ms"],
                "EndTime": vs["trim_end_ms"],
            }
        ]
        if vs.get("is_mute"):
            extra.append(
                {
                    "ID": _global_unique_id(),
                    "Type": "a_volume",
                    "Volume": 0,
                }
            )
        ud = {
            "id": voice_id,
            "source": voice_direct or "voice",
            "type": "audio",
            "url": voice_review_url,
        }
        if i == 0:
            ud["laneLabel"] = "人声"
        if vs.get("is_mute"):
            ud["status"] = "muted"
        if is_local:
            voice_source_raw = voice_direct or voice_url
            voice_source = (
                _local_media_url(voice_source_raw, _rh, _rp) if voice_source_raw else ""
            )
        else:
            voice_source = f"directurl://{voice_direct}" if voice_direct else voice_url
            voice_source_raw = voice_source  # cloud/apig 无需区分
        voice_lane.append(
            {
                "ID": voice_id,
                "Type": "audio",
                "Source": voice_source,
                "TargetTime": [vs["target_start_ms"], vs["target_end_ms"]],
                "Extra": extra,
                "UserData": ud,
            }
        )

    # 背景轨
    bg_id = _element_id("bg", 0)
    if is_local:
        bg_source_raw = bg_direct or bg_url or ""
        bg_source = _local_media_url(bg_source_raw, _rh, _rp) if bg_source_raw else ""
    else:
        bg_source = f"directurl://{bg_direct}" if bg_direct else (bg_url or "")
        bg_source_raw = bg_source  # cloud/apig 无需区分
    bg_lane = (
        [
            {
                "ID": bg_id,
                "Type": "audio",
                "Source": bg_source,
                "TargetTime": [0, total_ms],
                "Extra": [
                    {
                        "ID": _global_unique_id(),
                        "Type": "a_volume",
                        "Volume": 0.3,
                    }
                ],
                "UserData": {
                    "id": bg_id,
                    "source": bg_direct or "bg",
                    "type": "audio",
                    "url": bg_review_url or "",
                    "laneLabel": "背景",
                },
            }
        ]
        if (bg_url or bg_review_url)
        else []
    )

    # baseTrack 顺序：视频、背景、人声、字幕（字幕由 buildMergedTrack 追加）
    base_track = (
        [video_lane, bg_lane, voice_lane] if bg_lane else [video_lane, voice_lane]
    )

    # 静音人声 ID 列表，供审核页按 ID 应用红色样式（SDK 可能不解析 trackStyle 时用）
    muted_voice_ids = []
    for el in voice_lane:
        ud = el.get("UserData") or {}
        if ud.get("status") == "muted" or any(
            x and x.get("Type") == "a_volume" and x.get("Volume") == 0
            for x in (el.get("Extra") or [])
        ):
            vid = el.get("ID") or ud.get("id")
            if vid:
                muted_voice_ids.append(vid)

    # review_import_data（含 canvas 供预览页 describeProject 使用）
    review_data = {
        "sentences": sentences,
        "track": base_track,
        "canvas": {"Width": video_width, "Height": video_height},
        "mutedVoiceIds": muted_voice_ids,
        "_execution_mode": "local"
        if is_local
        else ("apig" if _env_is_apig else "cloud"),
        "_source_step6": step6_fp,
    }
    _write_json(args.review, review_data)
    print(f"[OK] 已生成 output/{args.review}")

    # export_request（服务端格式）
    # 字幕安全区与字体：左右 8%，距底 10%，文本区域高度按画布 12%，统一字体大小
    MARGIN_H_PCT = 0.08
    MARGIN_BOTTOM_PCT = 0.10
    SUB_HEIGHT_RATIO = 0.12
    SUBTITLE_FONT_SIZE = 50

    def _subtitle_position(cw: int, ch: int) -> dict:
        pos_x = int(cw * MARGIN_H_PCT)
        sub_width = int(cw * (1 - 2 * MARGIN_H_PCT))
        sub_height = int(ch * SUB_HEIGHT_RATIO)
        pos_y = int(ch * (1 - MARGIN_BOTTOM_PCT)) - sub_height
        return {"PosX": pos_x, "PosY": pos_y, "Width": sub_width, "Height": sub_height}

    sub_pos = _subtitle_position(video_width, video_height)
    _FONT_TYPE = (
        "https://lf3-static.bytednsdoc.com/obj/eden-cn/ljhwz_kvc/"
        "ljhwZthlaukjlkulzlp/ai_mediakit/字体/okt1LEaq5CAm0EAoBSFfACgGel7AdgEnVADspZ.zip"
    )

    def _text_extra() -> list:
        return [
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
            },
        ]

    text_lane = []
    for i, s in enumerate(sentences):
        if (s.get("status") or "").lower() in ("removed", "muted"):
            continue
        text = str(s.get("text") or "")
        if not text.strip():
            continue
        out_range = seg_source_range.get(i)
        if out_range:
            start_ms, end_ms = out_range[0], out_range[1]
        else:
            start_ms = int((s.get("start") or 0) * 1000)
            end_ms = int((s.get("end") or 0) * 1000)
        if start_ms >= end_ms:
            continue
        text_lane.append(
            {
                "ID": "element" + _global_unique_id(),
                "Type": "text",
                "TargetTime": [start_ms, end_ms],
                "Text": text,
                "FontType": _FONT_TYPE,
                "FontSize": SUBTITLE_FONT_SIZE,
                "FontColor": "#ffffffff",
                "ShadowColor": "#00000000",
                "LineMaxWidth": 1,
                "AlignType": 1,
                "Extra": _text_extra(),
                "UserData": {
                    "fontFamily": "noto sans",
                    "fontTypeUrl": _FONT_TYPE,
                    "fontTypeRef": _FONT_TYPE,
                },
            }
        )

    has_mute = any(vs.get("is_mute") for vs in voice_segments)
    has_subtitle = not _skip_subtitle_export() and len(text_lane) > 0
    # export_request 使用原始路径（供 ffmpeg / VOD），base_track 使用 /local-media/ URL（供审核页预览）
    video_source_for_export = video_source_raw if is_local else video_source
    do_video_cut = _should_export_video_cut(has_subtitle, has_mute)

    def _voice_extra(vs):
        ex = [
            {
                "ID": _global_unique_id(),
                "Type": "trim",
                "StartTime": vs["trim_start_ms"],
                "EndTime": vs["trim_end_ms"],
            }
        ]
        if vs.get("is_mute"):
            ex.append({"ID": _global_unique_id(), "Type": "a_volume", "Volume": 0})
        return ex

    def _video_trim_extra(trim_start: int, trim_end: int):
        t = dict(video_transform)
        t["ID"] = _global_unique_id()
        v = dict(video_volume)
        v["ID"] = _global_unique_id()
        return [t, v, {"Type": "trim", "StartTime": trim_start, "EndTime": trim_end}]

    if do_video_cut:
        # 以音频为准：排除音量为 0（is_mute）的片段、时长=0 的片段；片段间直接拼接（无间隔）
        keep_voice = [
            vs
            for vs in voice_segments
            if not vs.get("is_mute")  # 音量为 0 的移除
            and (vs["trim_end_ms"] - vs["trim_start_ms"]) > 0
        ]
        cumul = 0
        for vs in keep_voice:
            dur = vs["trim_end_ms"] - vs["trim_start_ms"]
            vs["out_start_ms"] = cumul
            vs["out_end_ms"] = cumul + dur
            cumul += dur
        total_output_ms = cumul

        _export_voice_src = (
            (voice_direct or voice_url)
            if is_local
            else (f"directurl://{voice_direct}" if voice_direct else voice_url)
        )
        export_voice_lane = [
            {
                "Type": "audio",
                "Source": _export_voice_src,
                "TargetTime": [vs["out_start_ms"], vs["out_end_ms"]],
                "Extra": [
                    {
                        "Type": "trim",
                        "StartTime": vs["trim_start_ms"],
                        "EndTime": vs["trim_end_ms"],
                    }
                ],
            }
            for vs in keep_voice
        ]
        export_video_lane = [
            {
                "Type": "video",
                "Source": video_source_for_export,
                "TargetTime": [vs["out_start_ms"], vs["out_end_ms"]],
                "Extra": _video_trim_extra(vs["trim_start_ms"], vs["trim_end_ms"]),
            }
            for vs in keep_voice
        ]
        by_seg: Dict[int, List[Dict]] = {}
        for vs in keep_voice:
            idx = vs["segment_idx"]
            if idx not in by_seg:
                by_seg[idx] = []
            by_seg[idx].append(vs)
        cut_text_lane = []
        for i, s in enumerate(sentences):
            if (s.get("status") or "").lower() in ("removed", "muted"):
                continue
            text = str(s.get("text") or "")
            if not text.strip():
                continue
            grp = by_seg.get(i)
            if not grp:
                continue
            out_start = min(v["out_start_ms"] for v in grp)
            out_end = max(v["out_end_ms"] for v in grp)
            cut_text_lane.append(
                {
                    "ID": "element" + _global_unique_id(),
                    "Type": "text",
                    "TargetTime": [out_start, out_end],
                    "Text": text,
                    "FontType": _FONT_TYPE,
                    "FontSize": SUBTITLE_FONT_SIZE,
                    "FontColor": "#ffffffff",
                    "ShadowColor": "#00000000",
                    "LineMaxWidth": 1,
                    "AlignType": 1,
                    "Extra": _text_extra(),
                    "UserData": {
                        "fontFamily": "noto sans",
                        "fontTypeUrl": _FONT_TYPE,
                        "fontTypeRef": _FONT_TYPE,
                    },
                }
            )

        # 字幕与音频对齐：仅保留在人声有效区间内的字幕（按 out_start/out_end）
        audio_intervals = [
            (int(v["out_start_ms"]), int(v["out_end_ms"]))
            for v in keep_voice
            if int(v["out_end_ms"]) > int(v["out_start_ms"])
        ]
        cut_text_lane = _clip_text_lane_to_intervals(cut_text_lane, audio_intervals)
        export_track_clean = [export_video_lane]
        if bg_url:
            export_track_clean.append(
                [
                    {
                        "Type": "audio",
                        "Source": (bg_direct or bg_url)
                        if is_local
                        else (f"directurl://{bg_direct}" if bg_direct else bg_url),
                        "TargetTime": [0, total_output_ms],
                        "Extra": [
                            {
                                "Type": "trim",
                                "StartTime": 0,
                                "EndTime": total_output_ms,
                            },
                            {
                                "ID": _global_unique_id(),
                                "Type": "a_volume",
                                "Volume": 0.3,
                            },
                        ],
                    }
                ]
            )
        export_track_clean.append(export_voice_lane)
        if not _skip_subtitle_export():
            export_track_clean.append(cut_text_lane)
        else:
            print("[提示] VOD_EXPORT_SKIP_SUBTITLE=1，导出时跳过字幕压制")
        print(
            "[提示] TALKING_VIDEO_AUTO_EDIT_VIDEO_CUT=1 且（有字幕或音频静音），已移除 mute 段并无缝拼接"
        )
    else:
        _else_voice_src = (
            (voice_direct or voice_url)
            if is_local
            else (f"directurl://{voice_direct}" if voice_direct else voice_url)
        )
        export_voice_lane = [
            {
                "Type": "audio",
                "Source": _else_voice_src,
                "TargetTime": [vs["target_start_ms"], vs["target_end_ms"]],
                "Extra": _voice_extra(vs),
            }
            for vs in voice_segments
        ]
        export_video_extra = [video_transform, video_volume]
        export_track_clean = [
            [
                {
                    "Type": "video",
                    "Source": video_source_for_export,
                    "TargetTime": [0, total_ms],
                    "Extra": export_video_extra,
                }
            ],
        ]
        if bg_url:
            export_track_clean.append(
                [
                    {
                        "Type": "audio",
                        "Source": (bg_direct or bg_url)
                        if is_local
                        else (f"directurl://{bg_direct}" if bg_direct else bg_url),
                        "TargetTime": [0, total_ms],
                        "Extra": [
                            {
                                "ID": _global_unique_id(),
                                "Type": "a_volume",
                                "Volume": 0.3,
                            }
                        ],
                    }
                ]
            )
        export_track_clean.append(export_voice_lane)
        if not _skip_subtitle_export():
            # 字幕与音频对齐：仅保留在人声有效区间内的字幕（按 target_start/target_end）
            audio_intervals = [
                (int(v["target_start_ms"]), int(v["target_end_ms"]))
                for v in voice_segments
                if not v.get("is_mute")
                and int(v["target_end_ms"]) > int(v["target_start_ms"])
            ]
            clipped = _clip_text_lane_to_intervals(text_lane, audio_intervals)
            export_track_clean.append(clipped)
        else:
            print("[提示] VOD_EXPORT_SKIP_SUBTITLE=1，导出时跳过字幕压制")

    export_request = {
        "Canvas": {"Width": video_width, "Height": video_height},
        "Track": export_track_clean,
        "Upload": {"SpaceName": space, "VideoName": "口播剪辑"},
        "Uploader": space,
        "_execution_mode": "local"
        if is_local
        else ("apig" if _env_is_apig else "cloud"),
        "_source_step6": step6_fp,
    }
    _write_json(args.export, export_request)
    print(f"[OK] 已生成 output/{args.export}")

    # 输出导出提交数据结构文档到 output，便于记录与查阅
    _skill_dir = Path(__file__).resolve().parents[1]
    _schema_path = _skill_dir / "reference" / "内置" / "导出提交数据结构.md"
    if _schema_path.is_file():
        _out_schema = _output_dir() / "导出提交数据结构.md"
        _out_schema.write_text(
            _schema_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
        print("[OK] 已输出 导出提交数据结构.md 到 output 目录")

    if is_local and args.direct_export:
        print("\n[local] --direct-export：跳过审核页，直接使用 ffmpeg 导出最终视频...")
        from local_export import export_local

        export_req_path = _output_dir() / args.export
        result_path = export_local(
            export_request_path=export_req_path,
            output_dir=_output_dir(),
            output_filename="export_direct.mp4",
        )
        print(f"[local] 导出完成 → {result_path}")
    elif is_local:
        print(
            f"\n[local] 本地模式审核页媒体服务: http://{args.review_host}:{args.review_port}/local-media/..."
        )
        print("[local] 请启动审核页服务: python serve_review_page.py")
        print("[local] 如需跳过审核页直接导出，使用: --direct-export")
        print("CHECKPOINT: 两份 JSON 已生成，track 使用本地媒体 URL")
    else:
        print("CHECKPOINT: 两份 JSON 已生成，track 使用真实 URL")


if __name__ == "__main__":
    main()
