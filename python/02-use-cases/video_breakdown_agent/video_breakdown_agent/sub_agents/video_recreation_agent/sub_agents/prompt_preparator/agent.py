"""
提示词准备Agent - 解析用户提供的视频提示词，准备生成参数
参考: multimedia/director-agent/src/director_agent/sub_agents/video/agent.py
"""

from veadk import Agent
from veadk.config import getenv

from ...tools.direct_video_generation import direct_video_generation
from .prompt import PROMPT_PREPARATION_INSTRUCTION


prompt_preparation_agent = Agent(
    name="prompt_preparation_agent",
    description="解析用户提供的视频提示词，准备生成参数",
    instruction=PROMPT_PREPARATION_INSTRUCTION,
    tools=[direct_video_generation],
    output_key="prompt_preparation_result",
    model_extra_config={
        "extra_body": {"thinking": {"type": getenv("THINKING_PROMPT_PREP", "disabled")}}
    },
)
