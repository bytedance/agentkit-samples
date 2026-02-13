from __future__ import annotations

from typing import Any, Optional

from google.adk.tools import BaseTool, ToolContext


def suppress_hook_tool_output(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: Any,
) -> Optional[Any]:
    """
    隐藏 analyze_hook_segments 工具的输出详情，避免向用户展示 functionResponse。
    
    设置 skip_summarization=True 后，SDK 不会向用户展示工具调用的详细响应，
    但数据仍然会传递给 SequentialAgent 的下一个步骤（hook_format_agent）。
    """
    if tool.name == "analyze_hook_segments":
        tool_context.actions.skip_summarization = True
    return tool_response
