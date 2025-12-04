import asyncio
import logging
import re
from copy import deepcopy
from typing import Any, Dict, Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from google.genai.types import Content, Part
from veadk import Agent, Runner

# ===========================================================================
#                                 日志配置
# ===========================================================================
import os


# 获取脚本所在的目录
log_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(log_dir, "debug_output.log")

# 配置日志记录器
log_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# 文件处理器 - DEBUG
file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(log_formatter)
root_logger.addHandler(file_handler)

# 控制台处理器 - INFO
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_formatter)
root_logger.addHandler(console_handler)

# 关闭 litellm 的控制台日志输出
logging.getLogger("litellm").setLevel(logging.INFO)

logger = logging.getLogger(__name__)
logger.info(f"日志文件将写入: {log_file}")


# ===========================================================================
#                           内容审查与过滤配置
# ===========================================================================

# --- 敏感词黑名单 ---
# 用于在 before_model_callback 中拦截不当请求。
BLOCKED_WORDS_CHINESE = [
    "zanghua",
    "minganci",
    "bukexiangdeshi",
]

# --- 个人信息(PII)过滤规则 ---
# 用于在 after_model_callback 中过滤模型响应中的个人信息。
PII_PATTERNS_CHINESE = {
    "电话号码": r"1[3-9]\d{9}",
    "身份证号": r"\d{17}[\dXx]",  # 17位数字 + 1位数字或X
    "邮箱": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}",
}


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
        filtered_text = pattern.sub(replace_and_log, filtered_text)

    return filtered_text


# ===========================================================================
#                               回调函数定义
# ===========================================================================


def before_agent_callback(
    callback_context: CallbackContext,
) -> Optional[Content]:
    """
    在智能体开始处理用户请求前被调用。
    主要用于记录会话开始的日志。
    """
    user_input = ""
    if callback_context.user_content and callback_context.user_content.parts:
        last_message = callback_context.user_content.parts[-1]
        user_input = last_message.text if hasattr(last_message, "text") else ""

    logger.info(f"请求内容: {user_input[:50]}...          ")
    return None


def before_model_callback(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """
    在调用大语言模型（LLM）之前被调用。
    此回调实现了两个核心功能：
    1.  **护栏（Guardrail）**：检查用户输入是否包含黑名单中的敏感词，如果包含则直接拦截，不将请求发送给模型。
    2.  **请求修改（Request Modification）**：为系统指令添加一个前缀，以演示如何动态修改即将发送给模型的内容。
    """
    logger.info("--- [模型调用前] 检查并修改输入内容 ---")
    agent_name = callback_context.agent_name
    logger.info(f"[Callback] Agent '{agent_name}' 正在准备调用模型。")

    # 提取最新的用户消息文本
    last_user_message = ""
    if llm_request.contents and llm_request.contents[-1].role == "user":
        if llm_request.contents[-1].parts:
            last_user_message = llm_request.contents[-1].parts[0].text or ""
    logger.info(f"[Callback] 检查用户最新消息: '{last_user_message}'")

    # **护栏功能**：检查敏感词
    for word in BLOCKED_WORDS_CHINESE:
        if word.lower() in last_user_message.lower():
            logger.warning(f"检测到敏感词 '{word}'。已拦截该请求。")
            # 返回一个 LlmResponse 对象以跳过对大语言模型的实际调用
            return LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            text="很抱歉，您发送的内容包含不当言论，我无法处理。"
                        )
                    ],
                )
            )

    # **请求修改功能**：为系统指令添加前缀
    logger.info("内容安全，准备为系统指令添加前缀。")
    original_instruction = llm_request.config.system_instruction
    prefix = "[由回调函数修改] "

    # 提取原始指令文本
    original_text = ""
    if isinstance(original_instruction, types.Content) and original_instruction.parts:
        original_text = original_instruction.parts[0].text or ""
    elif isinstance(original_instruction, str):
        original_text = original_instruction

    # 组合成新的指令并赋值回去
    modified_text = prefix + original_text
    llm_request.config.system_instruction = modified_text
    logger.info(f"[Callback] 已将系统指令修改为: '{modified_text}'")

    logger.info("[Callback] 继续执行模型调用。")
    # 返回 None 表示允许按照（已修改的）请求继续调用大语言模型
    return None


def after_model_callback(
    callback_context: CallbackContext, llm_response: Content, **kwargs
) -> Optional[Content]:
    """
    在从大语言模型（LLM）收到响应之后被调用。
    主要用于对模型的原始响应进行后处理。
    注意：PII 过滤已移至 after_tool_callback 以提高安全性。
    """
    logger.info("--- [模型调用后] ---")
    logger.debug(
        f"[Callback DEBUG] after_model_callback 接收到的 llm_response: {llm_response}"
    )
    # PII filtering has been moved to after_tool_callback for better security.
    return None


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


def after_tool_callback(
    tool: "BaseTool",
    args: Dict[str, Any],
    tool_context: "ToolContext",
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


def after_agent_callback(callback_context: CallbackContext) -> Optional[types.Content]:
    """
    在智能体完成所有处理，即将结束会话时被调用。
    主要用于记录会话结束的日志。
    """
    logger.info("--- [智能体结束] ---")
    agent_name = callback_context.agent_name
    invocation_id = callback_context.invocation_id

    print(f"\n[Callback] 智能体 '{agent_name}' (会话ID: {invocation_id}) 已结束。")
    return None


# ===========================================================================
#                           工具和智能体定义
# ===========================================================================


def write_article(topic: str, word_count: int, tool_context: ToolContext) -> str:
    """
    一个简单的工具，根据给定的主题和字数要求生成一篇文章。
    为了演示 PII 过滤功能，其输出硬编码了电话和身份证号。

    :param topic: 文章的主题。
    :param word_count: 文章的字数要求。
    :param tool_context: 工具上下文，由 veadk 框架提供。
    :return: 生成的文章内容字符串。
    """
    return (
        f"这是一篇关于'{topic}'的{word_count}字文章。"
        "我的电话是13812345678，身份证是11010120000101123X。"
    )


# --- 定义智能体 ---
# 将上面定义的回调函数注册到智能体中。
chinese_content_moderator_agent = Agent(
    name="ChineseContentModerator",
    description="一个演示全链路回调和护栏功能的中文内容审查助手。",
    instruction="你是一个内容助手，可以根据用户要求撰写文章。利用好工具",
    tools=[write_article],
    before_agent_callback=before_agent_callback,
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
    after_agent_callback=after_agent_callback,
)

# --- 定义执行器 ---
# Runner 负责管理智能体的执行流程。
runner = Runner(agent=chinese_content_moderator_agent)


root_agent = chinese_content_moderator_agent

# ===========================================================================
#                               主执行函数
# ===========================================================================


async def main():
    """
    主执行函数，用于演示智能体的不同应用场景。
    """
    print("\n" + "=" * 20 + " 场景1: 正常调用，触发工具和PII过滤 " + "=" * 20)
    await runner.run(messages="请帮我写一篇关于'人工智能未来'的500字文章。")

    print("\n" + "=" * 20 + " 场景2: 输入包含敏感词，被护栏拦截 " + "=" * 20)
    await runner.run(messages="你好，我想了解一些关于 zanghua 的信息。")

    print("\n" + "=" * 20 + " 场景3: 工具参数校验失败 " + "=" * 20)
    await runner.run(messages="写一篇关于'太空探索'的文章，字数-100。")


if __name__ == "__main__":
    asyncio.run(main())
