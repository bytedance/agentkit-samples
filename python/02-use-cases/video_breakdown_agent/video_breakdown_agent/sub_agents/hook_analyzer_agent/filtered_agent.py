from __future__ import annotations

from typing import AsyncGenerator

from google.adk.agents import InvocationContext
from google.adk.events import Event
from veadk import Agent


class HookAnalysisAgent(Agent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        async for event in super()._run_async_impl(ctx):
            parts = getattr(getattr(event, "content", None), "parts", None) or []
            has_hook_tool_response = any(
                getattr(getattr(part, "function_response", None), "name", "")
                == "analyze_hook_segments"
                for part in parts
            )
            if has_hook_tool_response:
                # 仅隐藏工具响应详情事件，保留后续总结与下游数据链路。
                continue
            yield event
