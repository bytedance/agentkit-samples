"""
报告生成 Agent
整合分镜拆解数据和钩子分析结果，生成专业的视频分析报告
"""

import os

from veadk import Agent

from video_breakdown_agent.tools.report_generator import generate_video_report
from .direct_output_callback import direct_output_callback
from .prompt import REPORT_AGENT_INSTRUCTION

report_generator_agent = Agent(
    name="report_generator_agent",
    description="整合分镜拆解数据和钩子分析结果，生成专业的视频分析报告",
    instruction=REPORT_AGENT_INSTRUCTION,
    tools=[generate_video_report],
    after_tool_callback=[direct_output_callback],
    output_key="final_report",  # 结果写入 session.state["final_report"]
    model_extra_config={
        "extra_body": {
            "thinking": {"type": os.getenv("THINKING_REPORT_AGENT", "disabled")}
        }
    },
)
