from __future__ import annotations

from typing import Any, Optional

from google.adk.tools import BaseTool, ToolContext


def direct_output_callback(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: Any,
) -> Optional[Any]:
    """
    让工具结果直接输出，跳过 LLM 总结，避免 veadk web 同时展示“工具输出 + 最终回复”造成重复。
    """
    if tool.name == "generate_video_report":
        tool_context.actions.skip_summarization = True
    return tool_response
