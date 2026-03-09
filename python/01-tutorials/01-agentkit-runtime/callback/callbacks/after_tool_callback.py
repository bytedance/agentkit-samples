import logging
import re
from copy import deepcopy
from typing import Any, Dict, Optional

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Content, Part

logger = logging.getLogger(__name__)


def after_tool_callback(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
    tool_response: Dict,
    **kwargs,
) -> Optional[Dict]:
    """
    It is invoked after the agent executes a tool but before its output is sent back to the model.
    Mainly used for post-processing the tool's output, such as PII filtering.
    """
    logger.info(f"  [Tool End] Tool {tool.name} has been executed.")
    if tool.name == "write_article":
        response_text = deepcopy(tool_response)
    # **Post-Processing**：Filters out personal information (PII) from the tool's output.
    filtered_text = filter_pii(response_text)
    return Content(parts=[Part(text=filtered_text)])


def filter_pii(
    text: str, patterns: Dict[str, str] = None, show_logs: bool = True
) -> str:
    """
    Filters out personal information (PII) from the text using predefined patterns.

    :param text: The original text to be filtered.
    :param patterns: A dictionary of PII matching patterns, defaulting to PII_PATTERNS_CHINESE.
    :param show_logs: Whether to print filtering logs.
    :return: The filtered text with PII hidden.
    """
    # ===========================================================================
    #                           Content Review and Filtering Configuration
    # ===========================================================================

    # --- Sensitive Word Blacklist ---
    # Used to intercept inappropriate requests in before_model_callback.
    # BLOCKED_WORDS_CHINESE = [
    #     "zanghua",
    #     "minganci",
    #     "bukexiangdeshi",
    # ]

    # --- Personal Information (PII) Filtering Rules ---
    # Used to filter out personal information (PII) from model responses in after_model_callback.
    PII_PATTERNS_CHINESE = {
        "phone number": r"1[3-9]\d{9}",
        "ID card number": r"\d{17}[\dXx]",  # 17位数字 + 1位数字或X
        "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}",
    }
    if patterns is None:
        patterns = PII_PATTERNS_CHINESE

    filtered_text = text

    for pii_type, pattern_str in patterns.items():
        # 编译正则表达式
        pattern = re.compile(pattern_str)

        # 定义替换函数
        def replace_and_log(match):
            found_pii = match.group(0)
            if show_logs:
                logger.info(f"✓ Detected {pii_type}: {found_pii} → Hidden")
            return f"[{pii_type} Hidden]"

        # 执行替换
        filtered_text = pattern.sub(
            replace_and_log, str(filtered_text) if filtered_text is not None else ""
        )

    return filtered_text
