"""
视频复刻主Agent
参考: multimedia/director-agent/src/director_agent/agent.py

架构说明（参考 multimedia 最佳实践）：
- Root Agent（video_recreation_agent）：识别任务类型，调用对应的 sub_agent
- recreation_pipeline（SequentialAgent）：标准复刻流程（提示词生成 → 视频生成 → 评估）
- quick_video_agent（SequentialAgent）：快捷流程（解析提示词 → 视频生成）
- Root Agent 不直接挂工具，工具由 sub_agent 持有
"""

from veadk import Agent
from veadk.agents.sequential_agent import SequentialAgent
from veadk.config import getenv

from .prompt import RECREATION_ROOT_AGENT_INSTRUCTION
from .sub_agents.prompt_generator.agent import create_prompt_generator_agent
from .sub_agents.video_generator.agent import create_video_generator_agent
from .sub_agents.evaluator.agent import create_evaluator_agent
from .sub_agents.prompt_preparator.agent import prompt_preparation_agent
from .hook.selection_hook import hook_segment_selection
from .hook.cost_calculator_hook import hook_cost_calculator
from .tools.generate_video_prompts import generate_video_prompts


def create_video_recreation_agent() -> Agent:
    """
    创建视频复刻Agent工厂函数

    架构设计（参考 multimedia/director-agent）：
    - video_recreation_agent: 识别意图，调用 sub_agent
      ├── recreation_pipeline: 标准复刻流程（SequentialAgent）
      │   ├── prompt_generator_agent（独立实例）
      │   ├── video_generator_agent（独立实例）
      │   └── evaluator_agent（独立实例）
      └── quick_video_agent: 快捷生成流程（SequentialAgent）
          ├── prompt_preparation_agent（解析提示词）
          └── video_generator_agent（独立实例）

    注意：使用 factory function 避免 Agent 实例被多个 parent 引用
    """

    # 完整复刻Pipeline（分镜选择 → 提示词生成 → 视频生成 → 评估）
    recreation_pipeline = SequentialAgent(
        name="recreation_pipeline",
        description="完整视频复刻流程：分镜选择 → 提示词生成 → 视频生成 → 评估",
        sub_agents=[
            create_prompt_generator_agent(),  # 生成提示词（独立实例）
            create_video_generator_agent(),  # 生成视频片段（独立实例）
            create_evaluator_agent(),  # 自动评估（独立实例）
        ],
    )

    # 快捷视频生成 Pipeline（解析提示词 → 生成视频）
    quick_video_agent = SequentialAgent(
        name="quick_video_agent",
        description="快捷视频生成：用户提供提示词后直接生成视频（解析提示词 → 生成视频）",
        sub_agents=[
            prompt_preparation_agent,  # 解析提示词，准备数据
            create_video_generator_agent(),  # 生成视频（独立实例，避免与 recreation_pipeline 冲突）
        ],
    )

    video_recreation_agent = Agent(
        name="video_recreation_agent",
        description="基于分镜数据生成视频复刻提示词，调用视频生成模型，支持风格迁移和自动评估",
        instruction=RECREATION_ROOT_AGENT_INSTRUCTION,
        tools=[generate_video_prompts],  # 直接持有工具：用于"仅查看提示词"的灵活调用
        sub_agents=[
            recreation_pipeline,  # 标准流程（完整复刻）
            quick_video_agent,  # 快捷流程（提示词 → 视频）
        ],
        before_agent_callback=hook_segment_selection,  # 处理分镜选择
        after_agent_callback=[hook_cost_calculator],  # 计算费用
        model_extra_config={
            "extra_body": {
                "thinking": {"type": getenv("THINKING_RECREATION_AGENT", "disabled")}
            }
        },
    )

    return video_recreation_agent


# 导出（与现有agent.py保持一致的命名）
video_recreation_agent = create_video_recreation_agent()
root_agent = video_recreation_agent
