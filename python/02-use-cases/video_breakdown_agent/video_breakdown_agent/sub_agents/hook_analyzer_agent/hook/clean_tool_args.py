"""
Clean hook analyzer tool call args to avoid malformed payloads.
"""

from __future__ import annotations

import logging
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.events import Event
from google.adk.models import LlmResponse

logger = logging.getLogger(__name__)


def clean_analyze_hook_arguments(
    *,
    callback_context: CallbackContext,
    llm_response: LlmResponse,
    model_response_event: Optional[Event] = None,
) -> Optional[LlmResponse]:
    """Force `analyze_hook_segments` function call args to `{}` for stability."""
    _ = model_response_event
    inv = getattr(callback_context, "_invocation_context", None)
    agent = getattr(inv, "agent", None)
    if not agent or getattr(agent, "name", "") != "hook_analysis_agent":
        return llm_response

    content = getattr(llm_response, "content", None)
    parts = getattr(content, "parts", None)
    if not parts:
        return llm_response

    fixed = False
    for part in parts:
        function_call = getattr(part, "function_call", None)
        if not function_call:
            continue
        if getattr(function_call, "name", "") != "analyze_hook_segments":
            continue
        args = getattr(function_call, "args", None)
        if args:
            function_call.args = {}
            fixed = True

    if fixed:
        logger.warning(
            "[clean_tool_args] polluted args detected in hook_analysis_agent, forced to {}"
        )
    return llm_response

