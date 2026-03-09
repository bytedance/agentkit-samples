"""
前三秒钩子分析 Sub-Agent

简化为单 Agent 模式：
1. hook_analyzer_agent — 使用 vision 模型进行多模态分析
2. after_model_callback 仅做宽松输出修复，不做刚性 schema 校验
"""

import os

from veadk import Agent
from veadk.agents.sequential_agent import SequentialAgent

from video_breakdown_agent.hook.format_hook import soft_fix_hook_output
from video_breakdown_agent.tools.analyze_hook_segments import analyze_hook_segments
from video_breakdown_agent.utils.types import json_response_config
from .prompt import HOOK_ANALYZER_INSTRUCTION, HOOK_FORMAT_INSTRUCTION

# 第一阶段：多模态视觉分析（使用 vision 模型）
hook_analysis_agent = Agent(
    name="hook_analysis_agent",
    model_name=os.getenv("MODEL_VISION_NAME", "doubao-seed-1-6-vision-250815"),
    description="对视频前三秒分镜进行深度钩子分析，具备视觉分析能力，可直接观察关键帧图片进行专业评估",
    instruction=HOOK_ANALYZER_INSTRUCTION,
    tools=[analyze_hook_segments],
    model_extra_config={
        "extra_body": {
            "thinking": {"type": os.getenv("THINKING_HOOK_ANALYZER_AGENT", "disabled")}
        }
    },
)

# 第二阶段：对齐 multimedia 的格式化收口模式
hook_format_agent = Agent(
    name="hook_format_agent",
    model_name=os.getenv("MODEL_FORMAT_NAME", os.getenv("MODEL_AGENT_NAME", "")),
    description="将钩子分析结果格式化为结构化输出并投影为用户可读 Markdown",
    instruction=HOOK_FORMAT_INSTRUCTION,
    generate_content_config=json_response_config,
    output_key="hook_analysis",
    after_model_callback=[soft_fix_hook_output],
    model_extra_config={
        "extra_body": {
            "thinking": {"type": os.getenv("THINKING_HOOK_FORMAT_AGENT", "disabled")}
        }
    },
)

hook_analyzer_agent = SequentialAgent(
    name="hook_analyzer_agent",
    description="前三秒钩子分析顺序流程：先分析，再格式化输出",
    sub_agents=[hook_analysis_agent, hook_format_agent],
)
