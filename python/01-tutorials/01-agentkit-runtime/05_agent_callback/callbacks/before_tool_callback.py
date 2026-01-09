import logging
from typing import Any, Dict, Optional

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

logger = logging.getLogger(__name__)


def before_tool_callback(
    tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext, **kwargs
) -> Optional[Dict[str, Any]]:
    """
    在工具执行之前被调用。
    主要用于对工具的输入参数进行校验。
    """
    tool_name = tool.name
    logger.info(f"--- [工具调用前] 校验 '{tool_name}' 工具的参数 ---")

    if tool_name == "write_article":
        word_count = args.get("word_count", 0)
        if not isinstance(word_count, int) or word_count <= 0:
            logger.warning(f"参数校验失败：word_count ({word_count}) 必须是正整数。")
            # 返回一个字典作为工具的输出，从而跳过工具的实际执行
            return {"result": "错误：文章字数必须为正整数。"}

    return None
