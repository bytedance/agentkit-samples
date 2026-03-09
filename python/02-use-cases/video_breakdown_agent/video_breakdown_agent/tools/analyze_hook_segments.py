"""
前三秒分镜提取工具
兼容新格式（process_video + analyze_segments_vision 输出）和旧格式
支持从 tool_context.state 读取完整的 base64 frame_urls
"""

import logging
from typing import Dict, List

from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)


def _get_field(seg: Dict, new_key: str, old_key: str, default=""):
    """兼容新旧字段名"""
    return seg.get(new_key, seg.get(old_key, default))


def analyze_hook_segments(tool_context: ToolContext = None) -> dict:
    """
    提取并分析视频前三秒的分镜数据，为钩子分析提供结构化的上下文信息。

    兼容两种输入格式：
    - 新格式：process_video + analyze_segments_vision 输出（index, start, end, 视觉表现等）
    - 旧格式：后端服务返回（segment_index, start_time, end_time, visual_content等）

    数据来源优先级：
    1. tool_context.state["vision_analysis_result"] — 完整数据（含 base64 frame_urls）
    2. tool_context.state["process_video_result"]["segments"] — 兜底（通常不含视觉分析字段）

    数据传递：
    - 返回给 hook_analysis_agent 的数据包含完整 base64 frame_images
    - 豆包视觉模型需要看到实际图片才能进行视觉评估
    - 完整图片数据同时存储在 tool_context.state["vision_analysis_result"] 中

    Args:
        tool_context: 工具上下文（用于读取完整数据）

    Returns:
        dict: 前三秒分镜的结构化分析上下文（含 base64 frame_images）
    """
    segments: List[Dict] | None = None
    # 优先从 session state 读取完整数据（包含 base64 frame_urls）
    if tool_context is not None:
        vision_result = tool_context.state.get("vision_analysis_result")
        if vision_result and isinstance(vision_result, list):
            segments = vision_result
            logger.info(
                f"[analyze_hook_segments] 从 session state 读取完整数据: {len(segments)} 个分镜"
            )

        if not segments:
            pv = tool_context.state.get("process_video_result")
            if isinstance(pv, dict) and isinstance(pv.get("segments"), list):
                segments = pv.get("segments")
                logger.info(
                    f"[analyze_hook_segments] vision_analysis_result 缺失，回退到 process_video_result: {len(segments)} 个分镜"
                )

    if not segments:
        return {
            "error": "没有分镜数据",
            "segment_count": 0,
            "total_duration": 0,
            "segments": [],
        }

    # 提取前三秒的分镜
    first_segments = []
    cumulative_time = 0

    for seg in segments:
        # 兼容 end / end_time
        end_time = seg.get("end", seg.get("end_time", 0))
        if cumulative_time >= 3.0 and first_segments:
            break
        first_segments.append(seg)
        cumulative_time = end_time

    # 构造分析上下文（支持多模态）
    context = {
        "segment_count": len(first_segments),
        "total_duration": cumulative_time,
        "total_video_segments": len(segments),
        "analysis_mode": "multimodal",
        "segments": [],
    }

    for s in first_segments:
        frame_urls = s.get("frame_urls", [])

        # 兼容新旧字段名
        start_time = s.get("start", s.get("start_time", 0))
        end_time = s.get("end", s.get("end_time", 0))
        index = s.get("index", s.get("segment_index", 0))
        duration = end_time - start_time

        # 视觉表现：新格式在嵌套对象中，旧格式在顶层
        visual_info = s.get("视觉表现", {})
        visual_content = visual_info.get("画面内容", "") if visual_info else ""
        if not visual_content:
            visual_content = s.get("visual_content", "")
            if not visual_content:
                visual_content = s.get("summary", "")

        shot_type = visual_info.get("景别", "") if visual_info else ""
        if not shot_type:
            shot_type = s.get("shot_type", "")

        camera_movement = visual_info.get("运镜", "") if visual_info else ""
        if not camera_movement:
            camera_movement = s.get("camera_movement", "")

        segment_info = {
            "index": index,
            "start_time": start_time,
            "end_time": end_time,
            "duration": round(duration, 2),
            "visual_content": visual_content,
            "speech_text": s.get("speech_text", ""),
            "shot_type": shot_type,
            "camera_movement": camera_movement,
            "function_tag": s.get("功能标签", s.get("function_tag", "")),
            "headline": s.get("画面小标题", s.get("headline", "")),
            "content_tags": s.get("内容标签", s.get("content_tags", [])),
            "voice_type": s.get("语音类型", s.get("voice_type", "")),
            "clip_url": s.get("clip_url", ""),
        }

        # 添加关键帧图片（供 vision 模型使用，保留完整 base64 数据）
        if frame_urls:
            segment_info["frame_count"] = len(frame_urls)
            # 构建标准的 image_url 格式（豆包 vision API 支持）
            segment_info["frame_images"] = [
                {"type": "image_url", "image_url": {"url": url}}
                for url in frame_urls[:3]  # 最多 3 帧
            ]
        else:
            segment_info["frame_images"] = []
            segment_info["frame_count"] = 0

        context["segments"].append(segment_info)

    total_frames = sum(s.get("frame_count", 0) for s in context["segments"])

    logger.info(
        f"前三秒分镜提取完成: {len(first_segments)}个分镜, "
        f"总时长{cumulative_time:.1f}s, 关键帧{total_frames}张（含完整 base64 图片）"
    )
    return context
