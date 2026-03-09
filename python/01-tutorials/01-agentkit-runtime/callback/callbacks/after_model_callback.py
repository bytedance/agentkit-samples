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
    It is invoked after the agent receives a response from the large language model (LLM).
    Mainly used for post-processing the original response from the model.
    Note: PII filtering has been moved to after_tool_callback for better security.
    """
    logger.info("--- [Model Call After] ---")
    logger.debug(
        f"[Callback DEBUG] after_model_callback received llm_response: {llm_response}"
    )
    # PII filtering has been moved to after_tool_callback for better security.
    return None
