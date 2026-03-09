from agentkit.apps import AgentkitAgentServerApp
from veadk import Agent, Runner
from veadk.memory import ShortTermMemory

from callbacks import (
    after_agent_callback,
    after_model_callback,
    after_tool_callback,
    before_agent_callback,
    before_model_callback,
    before_tool_callback,
)
from tools import write_article

root_agent = Agent(
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

runner = Runner(agent=root_agent)
short_term_memory = ShortTermMemory(backend="local")
agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)


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
    # asyncio.run(main())
    agent_server_app.run(host="0.0.0.0", port=8000)
