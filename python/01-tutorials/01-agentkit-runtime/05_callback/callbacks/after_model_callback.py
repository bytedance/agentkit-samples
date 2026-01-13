import logging
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.genai import types
from google.genai.types import Content

logger = logging.getLogger(__name__)


def after_model_callback(
    callback_context: CallbackContext, llm_response: Content, **kwargs
) -> Optional[types.Content]:
    """
    在从大语言模型（LLM）收到响应之后被调用。
    主要用于对模型的原始响应进行后处理。
    注意：PII 过滤已移至 after_tool_callback 以提高安全性。
    """
    logger.info("--- [模型调用后] ---")
    logger.debug(
        f"[Callback DEBUG] after_model_callback 接收到的 llm_response: {llm_response}"
    )
    # PII filtering has been moved to after_tool_callback for better security.
    return None
