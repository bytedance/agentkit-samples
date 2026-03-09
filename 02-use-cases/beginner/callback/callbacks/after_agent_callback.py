import logging
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.genai import types

logger = logging.getLogger(__name__)


def after_agent_callback(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    """
    在智能体完成所有处理，即将结束会话时被调用。
    主要用于记录会话结束的日志。
    """
    logger.info("--- [智能体结束] ---")
    agent_name = callback_context.agent_name
    invocation_id = callback_context.invocation_id

    print(f"\n[Callback] 智能体 '{agent_name}' (会话ID: {invocation_id}) 已结束。")
    return None
