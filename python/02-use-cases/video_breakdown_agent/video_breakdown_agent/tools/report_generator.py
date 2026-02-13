"""
视频分析报告生成工具
兼容新格式（process_video + analyze_segments_vision 输出）和旧格式
"""

import logging
from datetime import datetime
from typing import Optional

from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)

_DEFAULT_HOOK_ANALYSIS = {
    "overall_score": 0.0,
    "visual_impact": 0.0,
    "visual_comment": "",
    "language_hook": 0.0,
    "language_comment": "",
    "emotion_trigger": 0.0,
    "emotion_comment": "",
    "information_density": 0.0,
    "info_comment": "",
    "rhythm_control": 0.0,
    "rhythm_comment": "",
    "hook_type": "未知",
    "hook_type_analysis": "",
    "target_audience": "",
    "strengths": [],
    "weaknesses": [],
    "suggestions": [],
    "competitor_reference": "",
    "retention_prediction": "",
}


def _fallback_hook_from_markdown(markdown: str) -> dict:
    """从 Markdown 兜底提取最基础字段，保证报告阶段可消费。"""
    if not markdown:
        return {}

    import re

    hook = dict(_DEFAULT_HOOK_ANALYSIS)

    score_match = re.search(r"综合评分[:：]\s*([0-9]+(?:\.[0-9]+)?)", markdown)
    if score_match:
        try:
            hook["overall_score"] = float(score_match.group(1))
        except ValueError:
            pass

    type_match = re.search(r"钩子类型[:：]\s*([^\n]+)", markdown)
    if type_match:
        hook["hook_type"] = type_match.group(1).strip()

    retention_match = re.search(r"留存预测[:：]\s*([^\n]+)", markdown)
    if retention_match:
        hook["retention_prediction"] = retention_match.group(1).strip()

    for field, label in (
        ("visual_impact", "视觉冲击力"),
        ("language_hook", "语言钩子"),
        ("emotion_trigger", "情绪唤起"),
        ("information_density", "信息密度"),
        ("rhythm_control", "节奏掌控"),
    ):
        m = re.search(rf"{label}[:：]\s*([0-9]+(?:\.[0-9]+)?)/10", markdown)
        if m:
            try:
                hook[field] = float(m.group(1))
            except ValueError:
                pass
    return hook


def _resolve_report_inputs(
    breakdown_data: Optional[dict],
    hook_analysis: Optional[dict],
    tool_context: Optional[ToolContext],
) -> tuple[dict, dict]:
    """优先使用显式参数；缺失时从 session state 回填。"""
    breakdown = breakdown_data if isinstance(breakdown_data, dict) else {}
    hook = hook_analysis if isinstance(hook_analysis, dict) else {}

    state = getattr(tool_context, "state", None) if tool_context else None
    if not isinstance(state, dict):
        return breakdown, hook

    if not breakdown:
        state_breakdown = state.get("process_video_result")
        if isinstance(state_breakdown, dict):
            breakdown = dict(state_breakdown)

    # 优先使用视觉分析后的分镜结果，提升报告细节质量
    state_vision_segments = state.get("vision_analysis_result")
    if isinstance(state_vision_segments, list) and state_vision_segments:
        if not isinstance(breakdown, dict):
            breakdown = {}
        breakdown["segments"] = state_vision_segments
        if not breakdown.get("segment_count"):
            breakdown["segment_count"] = len(state_vision_segments)

    if not hook:
        state_hook = state.get("hook_analysis_struct") or state.get("hook_analysis")
        if isinstance(state_hook, dict):
            hook = state_hook

    if not hook:
        state_hook_md = state.get("hook_analysis_markdown")
        if isinstance(state_hook_md, str) and state_hook_md.strip():
            hook = _fallback_hook_from_markdown(state_hook_md)

    # BGM 工具可选落盘，若存在则补齐
    state_bgm = state.get("bgm_analysis_result")
    if isinstance(state_bgm, dict) and isinstance(breakdown, dict):
        breakdown.setdefault("bgm_analysis", state_bgm)

    return breakdown, hook


def generate_video_report(
    breakdown_data: Optional[dict] = None,
    hook_analysis: Optional[dict] = None,
    tool_context: ToolContext = None,
) -> str:
    """
    整合分镜拆解结果和钩子分析结果，生成结构化的 Markdown 视频分析报告。

    兼容两种输入格式：
    - 新格式：process_video + analyze_segments_vision + analyze_bgm 输出
    - 旧格式：后端服务返回的数据

    Args:
        breakdown_data: 分镜拆解的完整结果数据
        hook_analysis: 前三秒钩子分析结果（由 hook_analyzer_agent 返回的 JSON）

    Returns:
        str: 格式化的 Markdown 报告
    """
    breakdown_data, hook_analysis = _resolve_report_inputs(
        breakdown_data, hook_analysis, tool_context
    )

    if not breakdown_data:
        logger.warning(
            "报告生成失败：缺少 breakdown_data（state: process_video_result）"
        )
        return (
            "## 报告生成失败\n\n"
            "- 未找到分镜拆解数据（`process_video_result`）。\n"
            "- 请先执行视频分镜拆解，再生成报告。"
        )

    segments_data = breakdown_data.get("segments", [])
    if not segments_data:
        logger.warning("报告生成失败：breakdown_data 缺少 segments")
        return (
            "## 报告生成失败\n\n"
            "- 检测到分镜基础信息，但缺少分镜列表（`segments`）。\n"
            "- 请先完成视觉分镜分析后再生成报告。"
        )

    # 提取基本信息
    duration = breakdown_data.get("duration", 0)
    segment_count = breakdown_data.get("segment_count", 0)
    resolution = breakdown_data.get("resolution", "N/A")

    # BGM 分析：新格式可能在 bgm_analysis 或 bgm 字段
    bgm = breakdown_data.get("bgm_analysis") or breakdown_data.get("bgm") or {}
    scene = breakdown_data.get("scene_analysis") or {}

    # 完整语音文本（新格式特有）
    full_transcript = breakdown_data.get("full_transcript", "")

    # 提取 BGM 信息
    music_style = (
        bgm.get("music_style", {}).get("primary", "N/A")
        if isinstance(bgm.get("music_style"), dict)
        else "N/A"
    )
    emotion = (
        bgm.get("emotion", {}).get("primary", "N/A")
        if isinstance(bgm.get("emotion"), dict)
        else "N/A"
    )
    tempo = (
        bgm.get("tempo", {}).get("bpm_estimate", "N/A")
        if isinstance(bgm.get("tempo"), dict)
        else "N/A"
    )
    tempo_pace = (
        bgm.get("tempo", {}).get("pace", "N/A")
        if isinstance(bgm.get("tempo"), dict)
        else "N/A"
    )
    has_bgm = bgm.get("has_bgm")

    # 提取场景信息
    primary_scene = scene.get("primary_scene", "N/A") if scene else "N/A"
    video_style = scene.get("video_style", {}).get("overall", "N/A") if scene else "N/A"
    target_audience = (
        ", ".join(scene.get("video_style", {}).get("target_audience", []))
        if scene
        else "N/A"
    )

    # 构建钩子分析部分
    hook_section = _build_hook_section(hook_analysis)

    # 构建平台推荐部分
    platform_section = _build_platform_section(scene)

    # 构建分镜概览部分
    segments_section = _build_segments_overview(segments_data)

    # BGM 部分
    if has_bgm is False:
        bgm_section = "## BGM 分析\n- 未检测到背景音乐"
    elif has_bgm is None and music_style == "N/A":
        bgm_section = "## BGM 分析\n- BGM 分析数据暂不可用"
    else:
        bgm_section = f"""## BGM 分析
- **音乐风格**: {music_style}
- **情绪基调**: {emotion}
- **节拍**: {tempo} BPM（{tempo_pace}节奏）"""

    # 语音文本部分
    transcript_section = ""
    if full_transcript:
        transcript_section = f"""
---

## 语音文本

{full_transcript}"""

    report = f"""# 视频分析报告

## 基本信息
- **视频时长**: {duration:.1f}秒
- **分镜数量**: {segment_count}个
- **分辨率**: {resolution}

---

{hook_section}

---

## 分镜概览

{segments_section}

---

{bgm_section}

---

## 场景分析
- **主要场景**: {primary_scene}
- **视频风格**: {video_style}
- **目标受众**: {target_audience}

{platform_section}
{transcript_section}

---

**报告生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

    logger.info(f"报告生成完成，总长度: {len(report)} 字符")
    return report


def _build_hook_section(hook_analysis: dict) -> str:
    """构建前三秒钩子分析部分"""
    if not hook_analysis:
        return (
            "## 前三秒钩子分析\n\n"
            "钩子分析部分数据不完整，已基于可用分镜数据生成主报告。"
        )

    overall = hook_analysis.get("overall_score", 0)
    hook_type = hook_analysis.get("hook_type", "N/A")
    hook_type_analysis = hook_analysis.get("hook_type_analysis", "")
    target_audience = hook_analysis.get("target_audience", "")
    retention = hook_analysis.get("retention_prediction", "N/A")
    competitor_ref = hook_analysis.get("competitor_reference", "")

    # 使用分段展示每个维度（评价内容可能很长，表格不适合）
    dimensions = [
        (
            "视觉冲击力",
            hook_analysis.get("visual_impact", 0),
            hook_analysis.get("visual_comment", ""),
        ),
        (
            "语言钩子",
            hook_analysis.get("language_hook", 0),
            hook_analysis.get("language_comment", ""),
        ),
        (
            "情绪唤起",
            hook_analysis.get("emotion_trigger", 0),
            hook_analysis.get("emotion_comment", ""),
        ),
        (
            "信息密度",
            hook_analysis.get("information_density", 0),
            hook_analysis.get("info_comment", ""),
        ),
        (
            "节奏掌控",
            hook_analysis.get("rhythm_control", 0),
            hook_analysis.get("rhythm_comment", ""),
        ),
    ]

    dimension_sections = []
    for name, score, comment in dimensions:
        dimension_sections.append(f"#### {name}：{score}/10\n> {comment}")
    dimensions_text = "\n\n".join(dimension_sections)

    strengths = hook_analysis.get("strengths", [])
    weaknesses = hook_analysis.get("weaknesses", [])
    suggestions = hook_analysis.get("suggestions", [])

    strengths_text = "\n".join(f"- {s}" for s in strengths) if strengths else "- 暂无"
    weaknesses_text = (
        "\n".join(f"- {w}" for w in weaknesses) if weaknesses else "- 暂无"
    )
    suggestions_text = (
        "\n".join(f"{i + 1}. {s}" for i, s in enumerate(suggestions))
        if suggestions
        else "1. 暂无"
    )

    # 可选字段
    hook_type_detail = f"\n{hook_type_analysis}" if hook_type_analysis else ""
    audience_line = f"\n- **目标受众**: {target_audience}" if target_audience else ""
    competitor_line = f"\n### 竞品参考\n{competitor_ref}" if competitor_ref else ""

    return f"""## 前三秒钩子分析（核心）

### 综合评分: {overall}/10
- **钩子类型**: {hook_type}{hook_type_detail}{audience_line}

---

### 五维评分详情

{dimensions_text}

---

### 亮点
{strengths_text}

### 待改进
{weaknesses_text}

### 优化建议
{suggestions_text}
{competitor_line}

### 留存预测
**{retention}**"""


def _build_platform_section(scene: dict) -> str:
    """构建平台推荐部分"""
    if not scene:
        return ""

    recommendations = scene.get("platform_recommendations", [])
    if not recommendations:
        return ""

    lines = ["### 平台推荐"]
    for rec in recommendations:
        platform = rec.get("platform", "N/A")
        suitability = rec.get("suitability", "N/A")
        reason = rec.get("reason", "")
        lines.append(f"- **{platform}**（适合度: {suitability}）: {reason}")

    return "\n".join(lines)


def _build_segments_overview(segments: list) -> str:
    """构建分镜概览表格（兼容新旧格式）"""
    if not segments:
        return "暂无分镜数据。"

    lines = [
        "| 镜号 | 时间 | 景别 | 运镜 | 功能标签 | 画面内容 |",
        "|------|------|------|------|----------|----------|",
    ]

    for seg in segments[:10]:
        # 兼容新旧字段名
        index = seg.get("index", seg.get("segment_index", "-"))
        start = seg.get("start", seg.get("start_time", 0))
        end = seg.get("end", seg.get("end_time", 0))
        time_range = f"{start:.1f}s-{end:.1f}s"

        # 视觉表现：新格式在嵌套对象中
        visual_info = seg.get("视觉表现", {})
        shot_type = visual_info.get("景别", "") if visual_info else ""
        if not shot_type:
            shot_type = seg.get("shot_type", "-")

        camera = visual_info.get("运镜", "") if visual_info else ""
        if not camera:
            camera = seg.get("camera_movement", "-")

        func_tag = seg.get("功能标签", seg.get("function_tag", "-"))

        visual = visual_info.get("画面内容", "") if visual_info else ""
        if not visual:
            visual = seg.get("visual_content", seg.get("summary", "-"))

        if len(visual) > 40:
            visual = visual[:37] + "..."

        lines.append(
            f"| {index} | {time_range} | {shot_type} | {camera} | {func_tag} | {visual} |"
        )

    if len(segments) > 10:
        lines.append(f"\n*（仅展示前10个分镜，共{len(segments)}个）*")

    return "\n".join(lines)
