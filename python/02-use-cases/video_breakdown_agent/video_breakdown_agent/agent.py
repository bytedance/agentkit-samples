"""
主编排 Root Agent 定义（veadk web 的唯一真相来源）

架构说明：root agent 直接持有 web_search 工具，无需独立的 search_agent 子 Agent。
VeADK 支持 Agent 同时持有 tools 和 sub_agents（video_recreation_agent 已验证）。
"""

import logging
import os

from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import ToolContext
from veadk import Agent
from veadk.agents.sequential_agent import SequentialAgent
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.tools.builtin_tools.web_search import web_search

from .hook.final_output_hook import guard_final_user_output
from .hook.tool_call_guard import guard_tool_calls
from .hook.video_upload_hook import hook_video_upload
from .prompt import ROOT_AGENT_INSTRUCTION
from .sub_agents.breakdown_agent.prompt import (
    BREAKDOWN_AGENT_INSTRUCTION,
    HOOK_ANALYSIS_ADDENDUM,
)
from .sub_agents.report_generator_agent.prompt import REPORT_AGENT_INSTRUCTION
from .sub_agents.report_generator_agent.direct_output_callback import (
    direct_output_callback,
)
from .tools.process_video import process_video
from .tools.analyze_segments_vision import analyze_segments_vision
from .tools.analyze_bgm import analyze_bgm
from .tools.video_upload import video_upload_to_tos
from .tools.report_generator import generate_video_report
from .tools.analyze_hook_segments import analyze_hook_segments

# ==================== 视频复刻Agent导入（新增） ====================
from .sub_agents.video_recreation_agent.agent import video_recreation_agent


logger = logging.getLogger(__name__)

# ==================== Monkey-patch: Part.from_function_call args 归一化 ====================
# 问题：云端 LLM 偶发返回 function_call.args = ''（空字符串），
#       google.genai.types.FunctionCall(name, args='') Pydantic 校验直接崩溃，
#       该路径早于所有 after_model_callback，仅 patch json.loads 无法覆盖此分支。
# 修复：包装 Part.from_function_call，强制将非 dict 的 args 归一化为 dict 后再调用原函数。
try:
    import google.genai.types as _genai_types

    # 直接保存原始函数引用（从类访问 staticmethod 已自动解包为普通函数）
    _orig_from_function_call = _genai_types.Part.from_function_call

    def _safe_args(raw_args) -> dict:
        """将任意 args 归一化为 dict：None/''/非 dict 均安全转换。"""
        if raw_args is None or (isinstance(raw_args, str) and not raw_args.strip()):
            return {}
        if isinstance(raw_args, dict):
            return raw_args
        if isinstance(raw_args, str):
            try:
                import json_repair as _jr

                parsed = _jr.loads(raw_args)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    def _patched_from_function_call(name: str, args=None, **kwargs):
        orig_args = args
        safe = _safe_args(args)
        if not isinstance(orig_args, dict):
            logger.warning(
                "[args_patch] Part.from_function_call args 类型异常 (type=%s, repr=%r)，已归一化为 {}",
                type(orig_args).__name__,
                str(orig_args)[:80],
            )
        return _orig_from_function_call(name=name, args=safe, **kwargs)

    # 用 staticmethod 包装后赋回类属性，保持与原调用方式一致
    _genai_types.Part.from_function_call = staticmethod(_patched_from_function_call)
    logger.info("[args_patch] Part.from_function_call 已替换为 args 归一化包装")
except Exception as _args_patch_err:
    logger.warning("[args_patch] 补丁未生效（不影响正常运行）: %s", _args_patch_err)

# ==================== Monkey-patch: lite_llm json.loads 失败兜底 ====================
# 问题：云端 LLM 偶发在 function_call.arguments 后追加多余文字，导致
#       json.loads(arguments) 抛 JSONDecodeError("Extra data")，SDK 未 catch 直接崩溃。
# 修复：仅在 json.loads 抛异常时介入（正常 JSON 路径完全不变）：
#       1. raw_decode：提取首个合法 JSON 对象（覆盖 "Extra data" 场景）
#       2. json_repair：修复更严重的畸形 JSON
#       3. 兜底返回 {}
try:
    import google.adk.models.lite_llm as _lite_llm

    _orig_lite_llm_json = _lite_llm.json  # 保存原始 json 模块引用

    class _SafeJsonProxy:
        """透传所有 json 操作；仅 loads 失败时做 fallback，不影响正常解析路径。"""

        def __getattr__(self, name):
            return getattr(_orig_lite_llm_json, name)

        def loads(self, s, *args, **kwargs):
            try:
                return _orig_lite_llm_json.loads(s, *args, **kwargs)
            except _orig_lite_llm_json.JSONDecodeError as _e:
                # fallback 1: raw_decode —— 提取第一个合法 JSON 对象，忽略尾部多余数据
                try:
                    result, _ = _orig_lite_llm_json.JSONDecoder().raw_decode(str(s))
                    if isinstance(result, dict):
                        logger.warning(
                            "[json_patch] json.loads 失败(%s)，raw_decode 成功，已提取首个 JSON 对象",
                            _e,
                        )
                        return result
                except Exception:
                    pass
                # fallback 2: json_repair
                try:
                    import json_repair as _jr2

                    result = _jr2.loads(str(s))
                    if isinstance(result, dict):
                        logger.warning(
                            "[json_patch] json.loads 失败(%s)，json_repair 成功",
                            _e,
                        )
                        return result
                except Exception:
                    pass
                logger.warning("[json_patch] json.loads 失败(%s)，兜底返回 {}", _e)
                return {}

    _lite_llm.json = _SafeJsonProxy()
    logger.info("[json_patch] lite_llm.json 已替换为失败兜底代理")
except Exception as _json_patch_err:
    logger.warning("[json_patch] 补丁未生效（不影响正常运行）: %s", _json_patch_err)

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
# 工具调用防呆：拦截空工具名 / transfer_to_agent 缺 agent_name（必须在最终输出守卫之前）
root_after_model_callbacks.append(guard_tool_calls)
# 最后一层输出守卫：仅在泄露过程信息时触发 LLM 重写
root_after_model_callbacks.append(guard_final_user_output)
root_callback_kwargs = {
    "after_model_callback": root_after_model_callbacks,
}
if root_before_model_callback:
    root_callback_kwargs["before_model_callback"] = root_before_model_callback

# ==================== Factory functions (避免 SequentialAgent 共享 parent) ====================


def _prime_hook_segments_state(callback_context: CallbackContext):
    """
    在 breakdown_agent(include_hook_analysis=True) 运行前，
    将 session.state 中已有的分镜数据预处理为 hook_segments_context 并回写 state。

    保障机制：
    - 读写对象是 session.state（代码层面），而非对话历史，云端 agentkit 同样可用。
    - 若用户消息中包含新视频 URL（http/https），跳过注入，避免旧数据干扰新视频处理。
    - 若 state 中没有分镜数据，函数无副作用，LLM 走正常工具流程。
    """
    # ① 用户消息含新视频 URL → 跳过注入，让工具处理新视频
    user_content = getattr(callback_context, "user_content", None)
    if user_content:
        for part in getattr(user_content, "parts", []) or []:
            text = getattr(part, "text", "") or ""
            if "http://" in text or "https://" in text:
                logger.debug(
                    "[_prime_hook_segments_state] 检测到新视频URL，跳过state注入"
                )
                return None

    # ② 读取 session.state 并注入 hook_segments_context
    inv = getattr(callback_context, "_invocation_context", None)
    if not inv:
        return None
    state = getattr(callback_context, "state", None)
    if not isinstance(state, dict):
        return None

    tool_ctx = ToolContext(inv)
    context = analyze_hook_segments(tool_ctx)  # 从 state["vision_analysis_result"] 读取

    if context.get("segment_count", 0) > 0:
        state["hook_segments_context"] = context
        logger.info(
            "[_prime_hook_segments_state] 已注入 hook_segments_context: "
            "%d 个分镜，总时长 %.1fs",
            context["segment_count"],
            context.get("total_duration", 0),
        )
    else:
        logger.debug("[_prime_hook_segments_state] state 无分镜数据，跳过注入")

    return None


def create_breakdown_agent(include_hook_analysis: bool = False) -> Agent:
    """
    创建分镜拆解 Agent。

    Args:
        include_hook_analysis: 为 True 时在 instruction 末尾附加钩子分析模板，
                               用于 hook_only_pipeline 和 full_analysis_pipeline。
                               同时注册 before_agent_callback 将 state 中已有的分镜数据
                               预注入为 hook_segments_context，实现代码级 state 保障。
    """
    instruction = BREAKDOWN_AGENT_INSTRUCTION
    if include_hook_analysis:
        instruction += HOOK_ANALYSIS_ADDENDUM
    return Agent(
        name="breakdown_agent",
        description=(
            "负责视频分镜拆解：视频预处理（FFmpeg + ASR）、"
            "视觉分析（doubao-vision）、BGM 分析。"
            "支持URL链接和本地文件上传，输出完整分镜结构化数据。"
        ),
        instruction=instruction,
        tools=[
            process_video,
            analyze_segments_vision,
            analyze_bgm,
            video_upload_to_tos,
        ],
        output_key="breakdown_result",
        before_agent_callback=_prime_hook_segments_state
        if include_hook_analysis
        else None,
        model_extra_config={
            "extra_body": {
                "thinking": {"type": os.getenv("THINKING_BREAKDOWN_AGENT", "disabled")}
            }
        },
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
    description="完整分析生产线：分镜拆解 + 钩子分析 -> 报告生成",
    sub_agents=[
        create_breakdown_agent(include_hook_analysis=True),
        create_report_generator_agent(),
    ],
)

hook_only_pipeline = SequentialAgent(
    name="hook_only_pipeline",
    description="钩子分析生产线：分镜拆解 + 钩子分析（在同一个 Agent 内完成）",
    sub_agents=[create_breakdown_agent(include_hook_analysis=True)],
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
        "能够自动拆解视频分镜、分析前三秒钩子、生成专业报告、复刻爆款视频"
    ),
    instruction=ROOT_AGENT_INSTRUCTION,
    tools=[web_search],
    sub_agents=[
        full_analysis_pipeline,
        hook_only_pipeline,
        report_only_pipeline,
        breakdown_only_pipeline,
        video_recreation_agent,
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
