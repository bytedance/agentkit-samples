import logging
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types

logger = logging.getLogger(__name__)

# --- 敏感词黑名单 ---
# 用于在 before_model_callback 中拦截不当请求。
BLOCKED_WORDS_CHINESE = [
    "zanghua",
    "minganci",
    "bukexiangdeshi",
]


def before_model_callback(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """
    在调用大语言模型（LLM）之前被调用。
    此回调实现了两个核心功能：
    1.  **护栏（Guardrail）**：检查用户输入是否包含黑名单中的敏感词，如果包含则直接拦截，不将请求发送给模型。
    2.  **请求修改（Request Modification）**：为系统指令添加一个前缀，以演示如何动态修改即将发送给模型的内容。
    """
    logger.info("--- [模型调用前] 检查并修改输入内容 ---")
    agent_name = callback_context.agent_name
    logger.info(f"[Callback] Agent '{agent_name}' 正在准备调用模型。")

    # 提取最新的用户消息文本
    last_user_message = ""
    if llm_request.contents and llm_request.contents[-1].role == "user":
        if llm_request.contents[-1].parts:
            last_user_message = llm_request.contents[-1].parts[0].text or ""
    logger.info(f"[Callback] 检查用户最新消息: '{last_user_message}'")

    # **护栏功能**：检查敏感词
    for word in BLOCKED_WORDS_CHINESE:
        if word.lower() in last_user_message.lower():
            logger.warning(f"检测到敏感词 '{word}'。已拦截该请求。")
            # 返回一个 LlmResponse 对象以跳过对大语言模型的实际调用
            return LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            text="很抱歉，您发送的内容包含不当言论，我无法处理。"
                        )
                    ],
                ),
                partial=True,
            )

    # **请求修改功能**：为系统指令添加前缀
    logger.info("内容安全，准备为系统指令添加前缀。")
    original_instruction = llm_request.config.system_instruction
    prefix = "[由回调函数修改] "

    # 提取原始指令文本
    original_text = ""
    if isinstance(original_instruction, types.Content) and original_instruction.parts:
        original_text = original_instruction.parts[0].text or ""
    elif isinstance(original_instruction, str):
        original_text = original_instruction

    # 组合成新的指令并赋值回去
    modified_text = prefix + original_text
    llm_request.config.system_instruction = modified_text
    logger.info(f"[Callback] 已将系统指令修改为: '{modified_text}'")

    logger.info("[Callback] 继续执行模型调用。")
    # 返回 None 表示允许按照（已修改的）请求继续调用大语言模型
    return None
