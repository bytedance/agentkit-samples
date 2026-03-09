"""
提示词生成Sub-Agent
参考: multimedia/director-agent/src/director_agent/sub_agents/storyboard/agent.py
"""

import os

from veadk import Agent
from veadk.agents.sequential_agent import SequentialAgent
from veadk.config import getenv

from ...tools.generate_video_prompts import generate_video_prompts
from ...tools.style_transfer import style_transfer
from ...hook.format_hook import fix_prompt_output
from ...utils.types import json_response_config, VideoPromptList
from .prompt import PROMPT_GENERATOR_INSTRUCTION, PROMPT_FORMAT_INSTRUCTION


def create_prompt_generator_agent() -> SequentialAgent:
    """
    创建提示词生成Agent（骨架实现）
    """

    # 提示词生成Agent
    prompt_generate_agent = Agent(
        name="prompt_generate_agent",
        description="根据分镜数据生成标准的视频生成提示词",
        instruction=PROMPT_GENERATOR_INSTRUCTION,
        tools=[generate_video_prompts, style_transfer],  # 集成工具
        model_extra_config={
            "extra_body": {
                "thinking": {"type": getenv("THINKING_PROMPT_GENERATOR", "disabled")}
            }
        },
    )

    # 提示词格式化Agent
    prompt_format_agent = Agent(
        name="prompt_format_agent",
        model_name=os.getenv(
            "MODEL_FORMAT_NAME", os.getenv("MODEL_AGENT_NAME", "doubao-seed-1-6-251015")
        ),
        description="将提示词格式化为标准JSON结构",
        instruction=PROMPT_FORMAT_INSTRUCTION,
        generate_content_config=json_response_config,
        output_schema=VideoPromptList,
        output_key="video_prompts",
        after_model_callback=[fix_prompt_output],  # 集成Hook
        model_extra_config={
            "extra_body": {
                "thinking": {"type": getenv("THINKING_PROMPT_FORMAT", "disabled")}
            }
        },
    )

    # 提示词生成流程（生成 → 格式化），格式化完成后由 output_key 直接透传
    prompt_generator_agent = SequentialAgent(
        name="prompt_generator_agent",
        description="提示词生成流程：生成 → 格式化",
        sub_agents=[prompt_generate_agent, prompt_format_agent],
    )

    return prompt_generator_agent


# 导出
prompt_generator_agent = create_prompt_generator_agent()
