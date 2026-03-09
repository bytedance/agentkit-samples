"""
视频生成Sub-Agent
参考: multimedia/director-agent/src/director_agent/sub_agents/video/agent.py
"""

from typing import Any, Optional

from google.adk.tools import BaseTool, ToolContext
from veadk import Agent
from veadk.agents.sequential_agent import SequentialAgent
from veadk.config import getenv

from ...tools.video_generate_http import video_generate
from ...tools.merge_video_segments import merge_segments
from .prompt import VIDEO_GENERATOR_INSTRUCTION


def _skip_after_video_generate(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: Any,
) -> Optional[Any]:
    """video_generate 工具完成后跳过 LLM 总结，直接输出工具结果，阻断重复调用。"""
    tool_context.actions.skip_summarization = True
    return tool_response


def create_video_generator_agent() -> SequentialAgent:
    """
    创建视频生成Agent（骨架实现）
    """

    # 视频生成Agent（调用Doubao-Seedance API）
    video_generate_agent = Agent(
        name="video_generate_agent",
        description="根据提示词批量生成视频分镜",
        instruction=VIDEO_GENERATOR_INSTRUCTION,
        tools=[video_generate],  # 集成工具
        after_tool_callback=_skip_after_video_generate,  # 工具完成后直接输出，阻断重复调用
        model_extra_config={
            "extra_body": {
                "thinking": {"type": getenv("THINKING_VIDEO_GENERATOR", "disabled")}
            }
        },
    )

    # 视频拼接Agent（单分镜自动跳过，多分镜执行拼接）
    video_merge_agent = Agent(
        name="video_merge_agent",
        description="将生成的分镜视频拼接为完整视频（单分镜自动跳过）",
        instruction="""调用 merge_segments 工具，然后根据返回结果展示。

## 强制规则

1. **禁止**复述、展示或引用上一步的任何内容（包括提示词文本、摘要、参数）
2. **只**输出视频链接或错误信息，不输出其他任何文字
3. 工具调用前后，禁止输出确认语、等待提示或解释

## 输出规则

- 工具返回 merged_video_url（不为 null）时：
  仅输出：📺 视频链接：<URL>

- 工具返回单分镜跳过（status 为 skipped）时：
  从工具返回的 video_url 字段展示链接：📺 视频链接：<URL>

- 工具返回 status 为 error 时：
  仅输出简洁的失败原因，不超过一句话。

保持简洁，不重复之前已展示的信息，不输出技术细节。""",
        tools=[merge_segments],
    )

    # 完整视频生成流程（生成 → 拼接/展示）
    video_generator_agent = SequentialAgent(
        name="video_generator_agent",
        description="视频生成流程：生成 → 拼接/展示链接",
        sub_agents=[video_generate_agent, video_merge_agent],
    )

    return video_generator_agent


# 导出
video_generator_agent = create_video_generator_agent()
