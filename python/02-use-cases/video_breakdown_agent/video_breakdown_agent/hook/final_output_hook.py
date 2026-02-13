"""
最终输出守卫（Root Agent after_model_callback）

目标：
1. 仅在检测到执行过程/JSON 外泄时触发；
2. 使用 LLM 将输出重写为用户可读 Markdown；
3. 不干预工具调用 envelope，避免破坏编排。
"""

from __future__ import annotations

import os
import json
from typing import Optional

import httpx
from google.adk.agents.callback_context import CallbackContext
from google.adk.events import Event
from google.adk.models import LlmResponse
from veadk.utils.logger import get_logger

logger = get_logger(__name__)


def _get_first_text(llm_response: LlmResponse) -> str:
    if not llm_response or not llm_response.content or not llm_response.content.parts:
        return ""
    return llm_response.content.parts[0].text or ""


def _looks_like_tool_envelope(text: str) -> bool:
    """工具调用包，必须放行，不可改写。"""
    compact = text.replace(" ", "")
    return (
        '"name":"' in compact and '"parameters":' in compact
    ) or '"agent_name":"' in compact


def _event_to_text(event: Optional[Event]) -> str:
    """将 event 尽量转成可检索字符串，便于做鲁棒的工具调用识别。"""
    if event is None:
        return ""
    try:
        if hasattr(event, "model_dump"):
            return json.dumps(event.model_dump(), ensure_ascii=False)
    except Exception:
        pass
    try:
        if hasattr(event, "__dict__"):
            return json.dumps(event.__dict__, ensure_ascii=False, default=str)
    except Exception:
        pass
    return str(event)


def _is_tool_call_turn(
    model_response_event: Optional[Event],
    llm_response: Optional[LlmResponse],
) -> bool:
    """
    判断当前是否是工具调用轮次。
    工具轮次不应被最终输出守卫改写，否则可能破坏 transfer_to_agent 编排。
    """
    # 优先依赖事件级信号，避免仅凭文本误判。
    event_text = _event_to_text(model_response_event).lower()
    if event_text and any(
        marker in event_text
        for marker in (
            "function_call",
            "tool_call",
            "function_response",
            "transfer_to_agent",
        )
    ):
        return True

    text = _get_first_text(llm_response).lower() if llm_response else ""
    # 无事件信息时再回退到文本 envelope 判定。
    if _looks_like_tool_envelope(text):
        return True
    return False


def _needs_llm_repair(text: str) -> bool:
    """是否需要触发最终输出修复。"""
    leak_markers = (
        "<[PLHD",
        '"name":',
        '"parameters":',
    )
    if any(marker in text for marker in leak_markers):
        return True

    # 典型 JSON 外泄：整段以 {} 或 [] 包裹
    stripped = text.strip()
    if (stripped.startswith("{") and stripped.endswith("}")) or (
        stripped.startswith("[") and stripped.endswith("]")
    ):
        return True
    return False


def _call_repair_llm(raw_text: str) -> Optional[str]:
    api_key = os.getenv("MODEL_AGENT_API_KEY", "")
    if not api_key:
        return None

    model = os.getenv("MODEL_AGENT_NAME", "doubao-seed-1-6-251015")
    api_base = os.getenv(
        "MODEL_AGENT_API_BASE", "https://ark.cn-beijing.volces.com/api/v3/"
    )
    api_base = api_base.rstrip("/")
    url = f"{api_base}/chat/completions"

    prompt = (
        "你是一个最终输出清洗器。请将输入内容改写为“面向最终用户”的中文 Markdown 结论，要求：\n"
        "1) 严禁输出任何内部执行过程、工具调用信息、name/parameters、transfer_to_agent、PLHD 标记；\n"
        "2) 严禁输出 JSON、代码块；\n"
        "3) 保留有价值的分析结论（评分、亮点、问题、建议）；\n"
        "4) 若信息不足，给出简短说明并建议用户重试，不要编造。\n"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": raw_text[:12000]},
        ],
        "temperature": 0.2,
        "max_tokens": 1200,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        content = str(content or "").strip()
        return content or None
    except Exception as e:
        logger.warning(f"[final_output_guard] repair llm call failed: {e}")
        return None


def guard_final_user_output(
    *,
    callback_context: CallbackContext,
    llm_response: LlmResponse,
    model_response_event: Optional[Event] = None,
) -> Optional[LlmResponse]:
    """
    Root Agent 最终输出守卫：
    - 纯工具 envelope：放行；
    - 发现泄露：调用 LLM 修复；
    - 失败兜底：保持原文，避免中断主流程。
    """
    agent = callback_context._invocation_context.agent
    if not agent or getattr(agent, "name", "") != "video_breakdown_agent":
        return llm_response

    if _is_tool_call_turn(model_response_event, llm_response):
        return llm_response

    text = _get_first_text(llm_response)
    if not text:
        return llm_response

    if not _needs_llm_repair(text):
        return llm_response

    repaired = _call_repair_llm(text)
    if repaired:
        llm_response.content.parts[0].text = repaired
        logger.info("[final_output_guard] repaired leaked intermediate output by llm")
    return llm_response
