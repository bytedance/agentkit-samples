"""
Root Agent after_model_callback：工具调用防呆

职责（仅处理 function_call 元数据，不改自然语言文本）：
1. 拦截空工具名（name=''）的 function_call，移除该 part 防止 `Tool '' not found` 崩溃。
2. 拦截 transfer_to_agent 缺少 agent_name 的调用，移除并记录日志防止无限循环。

设计原则：
- 仅删除异常 part，不修改正常 part，不改文本内容。
- 异常 part 被移除后，若 parts 列表仍有文本 part，LLM 回复正常展示。
- 若所有 part 都被移除（极端情况），LLM 会进入下一轮重试。
"""

from __future__ import annotations

import logging
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.events import Event
from google.adk.models import LlmResponse

logger = logging.getLogger(__name__)


def guard_tool_calls(
    *,
    callback_context: CallbackContext,
    llm_response: LlmResponse,
    model_response_event: Optional[Event] = None,
) -> Optional[LlmResponse]:
    """拦截异常工具调用 part，防止运行时崩溃和无限循环。"""
    _ = model_response_event

    content = getattr(llm_response, "content", None)
    if not content:
        return llm_response

    parts = getattr(content, "parts", None)
    if not parts:
        return llm_response

    clean_parts = []
    dropped = False

    for part in parts:
        fc = getattr(part, "function_call", None)
        if not fc:
            # 非 function_call part（文本/图片等），保留
            clean_parts.append(part)
            continue

        name = getattr(fc, "name", "") or ""

        # ── 防呆 1：空工具名 ──────────────────────────────────
        if not name.strip():
            logger.warning(
                "[tool_call_guard] 检测到空工具名的 function_call，已移除 (args=%r)",
                str(getattr(fc, "args", ""))[:120],
            )
            dropped = True
            continue

        # ── 防呆 2：transfer_to_agent 缺少 agent_name ────────
        if name == "transfer_to_agent":
            args = getattr(fc, "args", None) or {}
            agent_name = args.get("agent_name", "") if isinstance(args, dict) else ""
            if not agent_name or not str(agent_name).strip():
                logger.warning(
                    "[tool_call_guard] transfer_to_agent 缺少有效 agent_name，"
                    "已移除该调用 (raw_args=%r)",
                    str(args)[:120],
                )
                dropped = True
                continue

        # 正常 function_call，保留
        clean_parts.append(part)

    if dropped:
        llm_response.content.parts = clean_parts

    return llm_response
