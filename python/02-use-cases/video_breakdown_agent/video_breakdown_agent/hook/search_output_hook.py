from __future__ import annotations

from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.events import Event
from google.adk.models import LlmResponse


def _is_tool_call_turn(model_response_event: Optional[Event], text: str) -> bool:
    """工具调用回合不做处理，避免干扰 function call。"""
    if model_response_event and model_response_event.get_function_calls():
        return True
    return "transfer_to_agent" in (text or "") or "web_search" in (text or "")


def suppress_search_agent_user_output(
    *,
    callback_context: CallbackContext,
    llm_response: LlmResponse,
    model_response_event: Optional[Event] = None,
) -> Optional[LlmResponse]:
    """
    search_agent 只做检索与回传，不直接面向用户输出正文。
    将其文本暂存到 state，最终由 root agent 统一输出一次，避免重复回复。
    """
    agent_name = getattr(
        getattr(callback_context, "_invocation_context", None), "agent", None
    )
    if not agent_name or getattr(agent_name, "name", "") != "search_agent":
        return llm_response

    if not llm_response or not llm_response.content or not llm_response.content.parts:
        return llm_response

    text = llm_response.content.parts[0].text or ""
    if not text or _is_tool_call_turn(model_response_event, text):
        return llm_response

    state = getattr(callback_context, "state", None)
    if isinstance(state, dict):
        state["search_result"] = text

    # 清空 search_agent 的用户可见输出，避免与 root 最终答复重复展示。
    llm_response.content.parts[0].text = ""
    return llm_response
