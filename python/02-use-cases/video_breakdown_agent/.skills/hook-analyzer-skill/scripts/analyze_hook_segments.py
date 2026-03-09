"""
从分镜拆解结果中提取前三秒分镜数据，构造钩子分析上下文。

Usage:
    python scripts/analyze_hook_segments.py <breakdown_json_file>
    cat breakdown.json | python scripts/analyze_hook_segments.py -

Examples:
    python scripts/analyze_hook_segments.py breakdown_result.json
    echo '{"segments":[...]}' | python scripts/analyze_hook_segments.py -
"""

import json
import sys


def analyze_hook_segments(breakdown_data: dict) -> dict:
    """
    提取并分析视频前三秒的分镜数据，为钩子分析提供结构化上下文。

    Args:
        breakdown_data: 完整的分镜拆解结果（包含 segments 字段）

    Returns:
        dict: 前三秒分镜的结构化分析上下文
    """
    segments = breakdown_data.get("segments", [])

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
        end_time = seg.get("end_time", 0)
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

    # 为每个分镜构造详细信息
    for s in first_segments:
        frame_urls = s.get("frame_urls", [])

        segment_info = {
            "index": s.get("segment_index", 0),
            "start_time": s.get("start_time", 0),
            "end_time": s.get("end_time", 0),
            "duration": s.get("duration", 0),
            "visual_content": s.get("visual_content", ""),
            "speech_text": s.get("speech_text", ""),
            "shot_type": s.get("shot_type", ""),
            "camera_movement": s.get("camera_movement", ""),
            "function_tag": s.get("function_tag", ""),
            "headline": s.get("headline", ""),
            "content_tags": s.get("content_tags", []),
            "voice_type": s.get("voice_type", ""),
            "clip_url": s.get("clip_url", ""),
        }

        # 关键帧图片（供 vision 模型使用），每个分镜最多取前3帧
        if frame_urls:
            segment_info["frame_images"] = [
                {"type": "image_url", "image_url": {"url": url}}
                for url in frame_urls[:3]
            ]
            segment_info["frame_count"] = len(frame_urls)
        else:
            segment_info["frame_images"] = []
            segment_info["frame_count"] = 0

        context["segments"].append(segment_info)

    total_frames = sum(s.get("frame_count", 0) for s in context["segments"])
    print(
        f"前三秒提取完成: {len(first_segments)}个分镜, "
        f"总时长{cumulative_time:.1f}s, 关键帧{total_frames}张",
        file=sys.stderr,
    )

    return context


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_hook_segments.py <breakdown_json_file>")
        print("       cat breakdown.json | python analyze_hook_segments.py -")
        sys.exit(1)

    source = sys.argv[1]

    if source == "-":
        data = json.load(sys.stdin)
    else:
        with open(source, "r", encoding="utf-8") as f:
            data = json.load(f)

    result = analyze_hook_segments(data)
    print(json.dumps(result, ensure_ascii=False, indent=2))
