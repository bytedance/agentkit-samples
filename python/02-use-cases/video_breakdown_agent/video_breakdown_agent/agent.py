"""
主编排 Root Agent 定义（veadk web 的唯一真相来源）

VeADK 约束：有 sub_agents 的 Agent 不支持直接挂载 tools，
因此 web_search 等工具封装为独立子 Agent。
"""

import logging
import os

from veadk import Agent
from veadk.agents.sequential_agent import SequentialAgent
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.tools.builtin_tools.web_search import web_search

from .hook.final_output_hook import guard_final_user_output
from .hook.search_output_hook import suppress_search_agent_user_output
from .hook.video_upload_hook import hook_video_upload
from .prompt import ROOT_AGENT_INSTRUCTION
from .sub_agents.breakdown_agent.prompt import BREAKDOWN_AGENT_INSTRUCTION
from .sub_agents.hook_analyzer_agent.prompt import (
    HOOK_ANALYZER_INSTRUCTION,
    HOOK_FORMAT_INSTRUCTION,
)
from .sub_agents.report_generator_agent.prompt import REPORT_AGENT_INSTRUCTION
from .sub_agents.report_generator_agent.direct_output_callback import (
    direct_output_callback,
)
from .hook.format_hook import soft_fix_hook_output
from .tools.process_video import process_video
from .tools.analyze_segments_vision import analyze_segments_vision
from .tools.analyze_bgm import analyze_bgm
from .tools.video_upload import video_upload_to_tos
from .tools.analyze_hook_segments import analyze_hook_segments
from .tools.report_generator import generate_video_report
from .utils.types import json_response_config

logger = logging.getLogger(__name__)

# ==================== 内容安全护栏（LLM Shield） ====================
# 仅当配置了 TOOL_LLM_SHIELD_APP_ID 时启用，否则静默跳过

shield_callbacks = {}
if os.getenv("TOOL_LLM_SHIELD_APP_ID"):
    try:
        from veadk.tools.builtin_tools.llm_shield import content_safety

        shield_callbacks = {
            "before_model_callback": content_safety.before_model_callback,
            "after_model_callback": content_safety.after_model_callback,
        }
        logger.info("内容安全护栏: 已启用 (before_model + after_model)")
    except Exception as e:
        logger.warning(f"llm_shield 加载失败，跳过内容安全护栏: {e}")
else:
    logger.debug("未配置 TOOL_LLM_SHIELD_APP_ID，跳过内容安全护栏")

root_before_model_callback = shield_callbacks.get("before_model_callback")
root_after_model_callbacks = []
if shield_callbacks.get("after_model_callback"):
    root_after_model_callbacks.append(shield_callbacks["after_model_callback"])
# 最后一层输出守卫：仅在泄露过程信息时触发 LLM 重写
root_after_model_callbacks.append(guard_final_user_output)
root_callback_kwargs = {
    "after_model_callback": root_after_model_callbacks,
}
if root_before_model_callback:
    root_callback_kwargs["before_model_callback"] = root_before_model_callback

# ==================== 子 Agent 定义 ====================

# 搜索子 Agent：挂载 web_search 工具
search_agent = Agent(
    name="search_agent",
    description="联网搜索短视频行业资讯、平台规则、热门趋势等实时信息",
    instruction=(
        "你是一个搜索助手。收到用户的搜索请求后，使用 web_search 工具搜索相关信息。\n"
        "你负责检索与整理，不直接面向用户输出最终答复；最终答复由 video_breakdown_agent 统一给出。\n"
        "请将检索结果整理为简洁中文摘要（供 root 复用），不要添加自己的推测，只基于搜索结果回答。\n"
        "格式注意：输出中禁止使用波浪号 ~，数值范围请用 到 或 - 代替（如 1°C到9°C），"
        "避免 Markdown 渲染器将 ~ 误解析为删除线。\n"
        "\n"
        "完成搜索后，必须立即调用 transfer_to_agent，将控制权归还给 video_breakdown_agent。"
    ),
    tools=[web_search],
    after_model_callback=[suppress_search_agent_user_output],
    output_key="search_result",
)

# ==================== Factory functions (避免 SequentialAgent 共享 parent) ====================


def create_breakdown_agent() -> Agent:
    return Agent(
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
        output_key="breakdown_result",
        model_extra_config={
            "extra_body": {
                "thinking": {"type": os.getenv("THINKING_BREAKDOWN_AGENT", "disabled")}
            }
        },
    )


def create_hook_analyzer_agent() -> SequentialAgent:
    hook_analysis_agent = Agent(
        name="hook_analysis_agent",
        model_name=os.getenv("MODEL_VISION_NAME", "doubao-seed-1-6-vision-250815"),
        description="对视频前三秒分镜进行深度钩子分析，具备视觉分析能力，可直接观察关键帧图片进行专业评估",
        instruction=HOOK_ANALYZER_INSTRUCTION,
        tools=[analyze_hook_segments],
        model_extra_config={
            "extra_body": {
                "thinking": {
                    "type": os.getenv("THINKING_HOOK_ANALYZER_AGENT", "disabled")
                }
            }
        },
    )

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
                "thinking": {
                    "type": os.getenv("THINKING_HOOK_FORMAT_AGENT", "disabled")
                }
            }
        },
    )

    return SequentialAgent(
        name="hook_analyzer_agent",
        description="前三秒钩子分析顺序流程：先分析，再格式化输出",
        sub_agents=[hook_analysis_agent, hook_format_agent],
    )


def create_report_generator_agent() -> Agent:
    return Agent(
        name="report_generator_agent",
        description="整合分镜拆解数据和钩子分析结果，生成专业的视频分析报告",
        instruction=REPORT_AGENT_INSTRUCTION,
        tools=[generate_video_report],
        after_tool_callback=[direct_output_callback],
        output_key="final_report",
        model_extra_config={
            "extra_body": {
                "thinking": {"type": os.getenv("THINKING_REPORT_AGENT", "disabled")}
            }
        },
    )


# ==================== Pipelines ====================

full_analysis_pipeline = SequentialAgent(
    name="full_analysis_pipeline",
    description="完整分析生产线：分镜拆解 -> 钩子分析 -> 报告生成",
    sub_agents=[
        create_breakdown_agent(),
        create_hook_analyzer_agent(),
        create_report_generator_agent(),
    ],
)

hook_only_pipeline = SequentialAgent(
    name="hook_only_pipeline",
    description="钩子分析生产线：分镜拆解 -> 钩子分析",
    sub_agents=[create_breakdown_agent(), create_hook_analyzer_agent()],
)

report_only_pipeline = SequentialAgent(
    name="report_only_pipeline",
    description="报告生产线：补齐分镜 -> 生成报告",
    sub_agents=[create_breakdown_agent(), create_report_generator_agent()],
)

breakdown_only_pipeline = SequentialAgent(
    name="breakdown_only_pipeline",
    description="分镜拆解生产线：仅执行分镜拆解",
    sub_agents=[create_breakdown_agent()],
)

agent = Agent(
    name="video_breakdown_agent",
    description=(
        "专业的视频分镜拆解和深度分析助手，"
        "支持URL链接和本地文件上传，"
        "能够自动拆解视频分镜、分析前三秒钩子、生成专业报告"
    ),
    instruction=ROOT_AGENT_INSTRUCTION,
    sub_agents=[
        full_analysis_pipeline,
        hook_only_pipeline,
        report_only_pipeline,
        breakdown_only_pipeline,
        search_agent,
    ],
    short_term_memory=ShortTermMemory(backend="local"),
    # 拦截 veadk web UI 上传的文件（inline_data → 文本 URL/路径）
    before_agent_callback=hook_video_upload,
    model_extra_config={
        "extra_body": {
            "thinking": {"type": os.getenv("THINKING_ROOT_AGENT", "disabled")}
        }
    },
    **root_callback_kwargs,
)

root_agent = agent
