from google.adk.tools.tool_context import ToolContext


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
