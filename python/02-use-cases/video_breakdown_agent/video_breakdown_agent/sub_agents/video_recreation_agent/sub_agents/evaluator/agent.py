"""
评估Sub-Agent
"""

from veadk import Agent
from veadk.config import getenv

from ...tools.evaluate_recreated_video import evaluate_recreated_video
from ...utils.types import json_response_config, VideoEvaluationResult
from .prompt import EVALUATOR_INSTRUCTION


def create_evaluator_agent() -> Agent:
    """
    创建评估Agent（骨架实现）
    """

    evaluator_agent = Agent(
        name="evaluator_agent",
        description="评估复刻视频质量，对比原片数据",
        instruction=EVALUATOR_INSTRUCTION,
        tools=[evaluate_recreated_video],  # 集成工具
        generate_content_config=json_response_config,
        output_schema=VideoEvaluationResult,
        output_key="evaluation_result",
        model_extra_config={
            "extra_body": {
                "thinking": {"type": getenv("THINKING_EVALUATOR", "enabled")}
            }
        },
    )

    return evaluator_agent


# 导出
evaluator_agent = create_evaluator_agent()
