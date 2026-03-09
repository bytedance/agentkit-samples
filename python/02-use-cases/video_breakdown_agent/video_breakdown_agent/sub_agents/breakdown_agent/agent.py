"""
分镜拆解 Agent
负责接收视频URL/本地文件，完成 FFmpeg 预处理 + ASR + 视觉分析 + BGM 分析
无需外部后端服务，所有逻辑自包含在 tool 中
"""

import os

from veadk import Agent

from video_breakdown_agent.tools.process_video import process_video
from video_breakdown_agent.tools.analyze_segments_vision import analyze_segments_vision
from video_breakdown_agent.tools.analyze_bgm import analyze_bgm
from video_breakdown_agent.tools.video_upload import video_upload_to_tos
from .prompt import BREAKDOWN_AGENT_INSTRUCTION

breakdown_agent = Agent(
    name="breakdown_agent",
    description=(
        "负责视频分镜拆解：视频预处理（FFmpeg + ASR）、"
        "视觉分析（doubao-vision）、BGM 分析。"
        "支持URL链接和本地文件上传，输出完整分镜结构化数据。"
    ),
    instruction=BREAKDOWN_AGENT_INSTRUCTION,
    tools=[
        process_video,
        analyze_segments_vision,
        analyze_bgm,
        video_upload_to_tos,
    ],
    output_key="breakdown_result",  # 结果写入 session.state["breakdown_result"]
    model_extra_config={
        "extra_body": {
            "thinking": {"type": os.getenv("THINKING_BREAKDOWN_AGENT", "disabled")}
        }
    },
)
