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
    在工具调用之后，但在其输出被送回模型之前被调用。
    可用于修改工具的输出，如此处实现的 PII 过滤。
    """
    logger.info(f"  [工具结束] 工具 {tool.name} 已执行。")
    if tool.name == "write_article":
        response_text = deepcopy(tool_response)
    # 过滤PII
    filtered_text = filter_pii(response_text)
    return Content(parts=[Part(text=filtered_text)])


def filter_pii(
    text: str, patterns: Dict[str, str] = None, show_logs: bool = True
) -> str:
    """
    过滤文本中的个人身份信息(PII)。

    :param text: 需要过滤的原始文本
    :param patterns: PII匹配模式字典，默认使用 PII_PATTERNS_CHINESE
    :param show_logs: 是否打印过滤日志
    :return: 过滤后的文本
    """
    # ===========================================================================
    #                           内容审查与过滤配置
    # ===========================================================================

    # --- 敏感词黑名单 ---
    # 用于在 before_model_callback 中拦截不当请求。
    # BLOCKED_WORDS_CHINESE = [
    #     "zanghua",
    #     "minganci",
    #     "bukexiangdeshi",
    # ]

    # --- 个人信息(PII)过滤规则 ---
    # 用于在 after_model_callback 中过滤模型响应中的个人信息。
    PII_PATTERNS_CHINESE = {
        "电话号码": r"1[3-9]\d{9}",
        "身份证号": r"\d{17}[\dXx]",  # 17位数字 + 1位数字或X
        "邮箱": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}",
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
                print(f"✓ 检测到 {pii_type}: {found_pii} → 已隐藏")
            return f"[{pii_type}已隐藏]"

        # 执行替换
        filtered_text = pattern.sub(
            replace_and_log, str(filtered_text) if filtered_text is not None else ""
        )

    return filtered_text
