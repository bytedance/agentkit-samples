from google.adk.tools.tool_context import ToolContext


def write_article(topic: str, word_count: int, tool_context: ToolContext) -> str:
    """
    A simple tool that generates an article based on the given topic and word count.
    To demonstrate the PII filtering feature, its output hardcodes a phone number and ID card number.

    :param topic: The topic of the article.
    :param word_count: The word count requirement for the article.
    :param tool_context: The tool context provided by the veadk framework.
    :return: The generated article content string.
    """
    return (
        f"Here is an article about '{topic}' with {word_count} words."
        " My phone number is 13812345678, and my ID card number is 11010120000101123X."
    )
