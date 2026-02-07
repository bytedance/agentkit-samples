import logging
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.genai import types

logger = logging.getLogger(__name__)


def before_agent_callback(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    """
    It is invoked before the agent begins processing a user request.
    Mainly used to log the start of the session.
    """
    user_input = ""
    if callback_context.user_content and callback_context.user_content.parts:
        last_message = callback_context.user_content.parts[-1]
        user_input = last_message.text if hasattr(last_message, "text") else ""

    logger.info(f"[Callback] User Input: {user_input[:50]}...          ")
    return None
