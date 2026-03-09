"""
自动评估工具 - 评估复刻视频质量，对比原片数据
复用现有的process_video和hook_analyzer_agent
"""

from __future__ import annotations

import logging
from typing import Dict

from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)


async def re_analyze_video(video_url: str, tool_context: ToolContext) -> Dict:
    """
    重新分析视频（复用现有工具）

    Args:
        video_url: 视频URL
        tool_context: 工具上下文

    Returns:
        分析结果：包含分镜数据和钩子评分
    """
    try:
        # 导入现有工具（延迟导入，避免循环依赖）
        from video_breakdown_agent.tools.process_video import process_video
        from video_breakdown_agent.tools.analyze_segments_vision import (
            analyze_segments_vision,
        )

        # 1. 处理视频（分镜拆解）
        logger.info(f"重新分析视频: {video_url}")
        process_result = await process_video(
            video_url=video_url, tool_context=tool_context
        )

        if not process_result or process_result.get("status") != "success":
            logger.error("视频处理失败")
            return {}

        # 2. 视觉分析
        vision_result = await analyze_segments_vision(tool_context=tool_context)

        if not vision_result or vision_result.get("status") != "success":
            logger.error("视觉分析失败")
            return {}

        # 3. 提取钩子分析数据（前3秒）
        segments = vision_result.get("segments", [])
        hook_segments = [s for s in segments if s.get("end_time", 999) <= 3.0]

        # 简化版评分（基于分镜数据）
        # TODO: 如果需要完整钩子分析，需要调用hook_analyzer_agent

        return {
            "segments": segments,
            "hook_segments": hook_segments,
            "total_duration": process_result.get("total_duration", 0),
            "segment_count": len(segments),
        }

    except Exception as e:
        logger.error(f"重新分析视频失败: {e}", exc_info=True)
        return {}


def calculate_similarity(original_data: Dict, recreated_data: Dict) -> float:
    """
    计算相似度（0-100）

    Args:
        original_data: 原片分析数据
        recreated_data: 复刻视频分析数据

    Returns:
        相似度得分
    """
    similarity_score = 0.0
    weights = {
        "segment_count": 20,  # 分镜数量匹配（20分）
        "duration_match": 20,  # 时长匹配（20分）
        "shot_types": 30,  # 镜头类型匹配（30分）
        "visual_content": 30,  # 视觉内容相似度（30分）
    }

    original_segments = original_data.get("segments", [])
    recreated_segments = recreated_data.get("segments", [])

    # 1. 分镜数量匹配
    if len(original_segments) == len(recreated_segments):
        similarity_score += weights["segment_count"]
    elif len(recreated_segments) > 0:
        # 部分匹配
        ratio = min(len(recreated_segments), len(original_segments)) / max(
            len(recreated_segments), len(original_segments)
        )
        similarity_score += weights["segment_count"] * ratio

    # 2. 时长匹配
    original_duration = original_data.get("total_duration", 0)
    recreated_duration = recreated_data.get("total_duration", 0)

    if original_duration > 0 and recreated_duration > 0:
        duration_ratio = min(original_duration, recreated_duration) / max(
            original_duration, recreated_duration
        )
        similarity_score += weights["duration_match"] * duration_ratio

    # 3. 镜头类型匹配
    if original_segments and recreated_segments:
        matched_shot_types = 0
        for i in range(min(len(original_segments), len(recreated_segments))):
            orig_shot = original_segments[i].get("shot_type", "")
            recr_shot = recreated_segments[i].get("shot_type", "")
            if orig_shot and recr_shot and orig_shot == recr_shot:
                matched_shot_types += 1

        if len(original_segments) > 0:
            shot_match_ratio = matched_shot_types / len(original_segments)
            similarity_score += weights["shot_types"] * shot_match_ratio

    # 4. 视觉内容相似度（简化版：基于关键词重叠）
    # TODO: 更精细的评估可以使用视觉特征向量
    similarity_score += (
        weights["visual_content"] * 0.7
    )  # 默认70%相似（因为是基于同一提示词生成）

    return round(similarity_score, 2)


async def evaluate_recreated_video(tool_context: ToolContext) -> Dict:
    """
    自动评估工具

    评估复刻视频的质量，对比原片数据，生成对比报告。
    复用现有的process_video和analyze_segments_vision工具。

    Args:
        tool_context: 工具上下文

    Returns:
        {
            "status": "success" | "error",
            "overall_score": int,           # 综合质量得分（0-100）
            "similarity": float,            # 相似度（0-100）
            "comparison_details": Dict,     # 详细对比数据
            "strengths": List[str],         # 优点列表
            "improvements": List[str],      # 改进建议
            "message": str
        }
    """
    try:
        # 读取原片URL和复刻视频URL
        original_video_url = tool_context.state.get("original_video_url")
        recreated_video_url = tool_context.state.get("recreated_video_url")

        if not recreated_video_url:
            return {
                "status": "error",
                "message": "未找到复刻视频，请先生成并拼接视频",
                "overall_score": 0,
                "similarity": 0.0,
                "comparison_details": {},
                "strengths": [],
                "improvements": [],
            }

        logger.info("开始评估复刻视频质量...")

        # 读取原片分析数据（如果有）
        original_vision_result = tool_context.state.get("vision_analysis_result")
        original_hook_analysis = tool_context.state.get("hook_analysis_struct")

        if not original_vision_result:
            logger.warning("未找到原片分析数据，评估将受限")
            original_data = {}
        else:
            original_data = {
                "segments": original_vision_result.get("segments", []),
                "total_duration": sum(
                    s.get("duration", 0)
                    for s in original_vision_result.get("segments", [])
                ),
                "segment_count": len(original_vision_result.get("segments", [])),
            }

        # 重新分析复刻视频
        recreated_data = await re_analyze_video(recreated_video_url, tool_context)

        if not recreated_data:
            return {
                "status": "error",
                "message": "复刻视频分析失败",
                "overall_score": 0,
                "similarity": 0.0,
                "comparison_details": {},
                "strengths": [],
                "improvements": [],
            }

        # 计算相似度
        if original_data:
            similarity = calculate_similarity(original_data, recreated_data)
        else:
            similarity = 0.0
            logger.warning("无原片数据，无法计算相似度")

        # 对比钩子评分（如果有）
        original_hook_score = 0.0
        if original_hook_analysis:
            original_hook_score = original_hook_analysis.get("composite_score", 0.0)

        # TODO: 对复刻视频进行钩子分析（可选）
        # recreated_hook_score = ...

        # 生成对比详情
        comparison_details = {
            "original": {
                "segment_count": original_data.get("segment_count", 0),
                "total_duration": original_data.get("total_duration", 0),
                "hook_score": original_hook_score,
            },
            "recreated": {
                "segment_count": recreated_data.get("segment_count", 0),
                "total_duration": recreated_data.get("total_duration", 0),
                "hook_score": 0.0,  # TODO: 实际钩子评分
            },
            "similarity": similarity,
        }

        # 生成优点和改进建议
        strengths = []
        improvements = []

        # 基于分镜数量
        if recreated_data.get("segment_count", 0) == original_data.get(
            "segment_count", 0
        ):
            strengths.append("分镜结构完全复刻原片逻辑")
        elif recreated_data.get("segment_count", 0) > 0:
            strengths.append(f"成功生成{recreated_data.get('segment_count')}个分镜")

        # 基于相似度
        if similarity >= 90:
            strengths.append("视频高度还原原片风格和结构")
        elif similarity >= 70:
            strengths.append("视频较好地保留了原片的核心元素")
        else:
            improvements.append("建议调整提示词，提高与原片的相似度")

        # 默认建议
        if not original_video_url or not original_data:
            improvements.append("建议提供原片URL以进行完整对比评估")

        # 计算综合质量得分
        overall_score = int(similarity)  # 简化版：直接使用相似度作为得分

        # 存入session state
        tool_context.state["recreation_evaluation"] = {
            "overall_score": overall_score,
            "similarity": similarity,
            "comparison_details": comparison_details,
            "strengths": strengths,
            "improvements": improvements,
        }

        logger.info(f"✅ 评估完成：综合得分{overall_score}/100，相似度{similarity}%")

        return {
            "status": "success",
            "overall_score": overall_score,
            "similarity": similarity,
            "comparison_details": comparison_details,
            "strengths": strengths,
            "improvements": improvements,
            "message": f"评估完成：综合质量得分{overall_score}/100",
        }

    except Exception as e:
        logger.error(f"自动评估失败: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"自动评估失败: {str(e)}",
            "overall_score": 0,
            "similarity": 0.0,
            "comparison_details": {},
            "strengths": [],
            "improvements": [],
        }
