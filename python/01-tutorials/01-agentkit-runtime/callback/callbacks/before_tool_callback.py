import logging
from typing import Any, Dict, Optional

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

logger = logging.getLogger(__name__)


def before_tool_callback(
    tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext, **kwargs
) -> Optional[Dict[str, Any]]:
    """
    It is invoked before the agent executes a tool.
    Mainly used to validate the input parameters of the tool.
    """
    tool_name = tool.name
    logger.info(
        f"--- [Tool Call Before] Validate Parameters for '{tool_name}' Tool ---"
    )

    if tool_name == "write_article":
        word_count = args.get("word_count", 0)
        if not isinstance(word_count, int) or word_count <= 0:
            logger.warning(
                f"Parameter validation failed: word_count ({word_count}) must be a positive integer."
            )
            # return a dictionary as the tool's output, thus skipping the actual execution of the tool
            return {"result": "Error: word_count must be a positive integer."}

    return None
