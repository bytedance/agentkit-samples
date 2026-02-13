"""
整合分镜拆解数据和钩子分析结果，生成 Markdown 视频分析报告。

Usage:
    python scripts/generate_report.py <breakdown_json> [hook_analysis_json]

Examples:
    python scripts/generate_report.py breakdown.json hook_analysis.json
    python scripts/generate_report.py breakdown.json
    python scripts/generate_report.py breakdown.json hook.json > report.md
"""

import json
import sys
from datetime import datetime


def generate_video_report(breakdown_data: dict, hook_analysis: dict = None) -> str:
    """
    整合分镜拆解结果和钩子分析结果，生成 Markdown 视频分析报告。

    Args:
        breakdown_data: 分镜拆解的完整结果数据
        hook_analysis: 前三秒钩子分析结果（可选）

    Returns:
        str: Markdown 格式报告
    """
    if hook_analysis is None:
        hook_analysis = {}

    duration = breakdown_data.get("duration", 0)
    segment_count = breakdown_data.get("segment_count", 0)
    resolution = breakdown_data.get("resolution", "N/A")
    bgm = breakdown_data.get("bgm_analysis") or {}
    scene = breakdown_data.get("scene_analysis") or {}

    # BGM 信息
    music_style = bgm.get("music_style", {}).get("primary", "N/A") if bgm else "N/A"
    emotion = bgm.get("emotion", {}).get("primary", "N/A") if bgm else "N/A"
    tempo = bgm.get("tempo", {}).get("bpm_estimate", "N/A") if bgm else "N/A"
    tempo_pace = bgm.get("tempo", {}).get("pace", "N/A") if bgm else "N/A"

    # 场景信息
    primary_scene = scene.get("primary_scene", "N/A") if scene else "N/A"
    video_style = scene.get("video_style", {}).get("overall", "N/A") if scene else "N/A"
    target_audience = (
        ", ".join(scene.get("video_style", {}).get("target_audience", []))
        if scene
        else "N/A"
    )

    hook_section = _build_hook_section(hook_analysis)
    platform_section = _build_platform_section(scene)
    segments_section = _build_segments_overview(breakdown_data.get("segments", []))

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

## BGM 分析
- **音乐风格**: {music_style}
- **情绪基调**: {emotion}
- **节拍**: {tempo} BPM（{tempo_pace}节奏）

---

## 场景分析
- **主要场景**: {primary_scene}
- **视频风格**: {video_style}
- **目标受众**: {target_audience}

{platform_section}

---

**报告生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
    return report


def _build_hook_section(hook_analysis: dict) -> str:
    if not hook_analysis:
        return "## 前三秒钩子分析\n\n暂无钩子分析数据。"

    overall = hook_analysis.get("overall_score", 0)
    hook_type = hook_analysis.get("hook_type", "N/A")
    retention = hook_analysis.get("retention_prediction", "N/A")

    scores_table = f"""| 维度 | 得分 | 评价 |
|------|------|------|
| 视觉冲击力 | {hook_analysis.get("visual_impact", 0)}/10 | {hook_analysis.get("visual_comment", "")} |
| 语言钩子 | {hook_analysis.get("language_hook", 0)}/10 | {hook_analysis.get("language_comment", "")} |
| 情绪唤起 | {hook_analysis.get("emotion_trigger", 0)}/10 | {hook_analysis.get("emotion_comment", "")} |
| 信息密度 | {hook_analysis.get("information_density", 0)}/10 | {hook_analysis.get("info_comment", "")} |
| 节奏掌控 | {hook_analysis.get("rhythm_control", 0)}/10 | {hook_analysis.get("rhythm_comment", "")} |"""

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

    return f"""## 前三秒钩子分析（核心）

### 综合评分: {overall}/10

{scores_table}

### 钩子类型
**{hook_type}**

### 优势
{strengths_text}

### 不足
{weaknesses_text}

### 优化建议
{suggestions_text}

### 留存预测
**{retention}**"""


def _build_platform_section(scene: dict) -> str:
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
    if not segments:
        return "暂无分镜数据。"

    lines = [
        "| 镜号 | 时间 | 景别 | 运镜 | 功能标签 | 画面内容 |",
        "|------|------|------|------|----------|----------|",
    ]

    for seg in segments[:10]:
        index = seg.get("segment_index", "-")
        start = seg.get("start_time", 0)
        end = seg.get("end_time", 0)
        time_range = f"{start:.1f}s-{end:.1f}s"
        shot_type = seg.get("shot_type", "-")
        camera = seg.get("camera_movement", "-")
        func_tag = seg.get("function_tag", "-")
        visual = seg.get("visual_content", "-")
        if len(visual) > 40:
            visual = visual[:37] + "..."
        lines.append(
            f"| {index} | {time_range} | {shot_type} | {camera} | {func_tag} | {visual} |"
        )

    if len(segments) > 10:
        lines.append(f"\n*（仅展示前10个分镜，共{len(segments)}个）*")

    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_report.py <breakdown_json> [hook_analysis_json]")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        bd_data = json.load(f)

    hook_data = None
    if len(sys.argv) > 2:
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            hook_data = json.load(f)

    report = generate_video_report(bd_data, hook_data)
    print(report)
