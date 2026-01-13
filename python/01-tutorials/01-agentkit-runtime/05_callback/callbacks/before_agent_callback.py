import logging
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.genai import types

logger = logging.getLogger(__name__)


def before_agent_callback(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    """
    在智能体开始处理用户请求前被调用。
    主要用于记录会话开始的日志。
    """
    user_input = ""
    if callback_context.user_content and callback_context.user_content.parts:
        last_message = callback_context.user_content.parts[-1]
        user_input = last_message.text if hasattr(last_message, "text") else ""

    logger.info(f"请求内容: {user_input[:50]}...          ")
    return None
