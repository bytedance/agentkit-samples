import logging
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.genai import types

logger = logging.getLogger(__name__)


def after_agent_callback(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    """
    It is invoked when the agent has completed all processing and is about to end the session.
    It is primarily used to log the end of the session.
    """
    logger.info("--- [Agent End] ---")
    agent_name = callback_context.agent_name
    invocation_id = callback_context.invocation_id

    print(f"\n[Callback] Agent '{agent_name}' (session ID: {invocation_id}) has ended.")
    return None
