import asyncio

from prompts import (
    PARALLEL_GET_INFO_AGENT_PROMPT,
    RAG_SEARCH_AGENT_PROMPT,
    WEB_SEARCH_AGENT_PROMPT,
)
from veadk import Agent, Runner
from veadk.agents.parallel_agent import ParallelAgent
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.tools.builtin_tools.web_search import web_search

rag_search_agent = Agent(
    name="rag_search_agent",
    description="负责根据用户问题，从知识库中搜索相关信息",
    instruction=RAG_SEARCH_AGENT_PROMPT,
)

web_search_agent = Agent(
    name="web_search_agent",
    description="负责根据用户问题，从互联网中搜索相关信息",
    instruction=WEB_SEARCH_AGENT_PROMPT,
    tools=[web_search],
)

parallel_get_info_agent = ParallelAgent(
    name="parallel_get_info_agent",
    description="根据用户需求，并行执行子任务，快速获取相关信息",
    instruction=PARALLEL_GET_INFO_AGENT_PROMPT,
    # enable web_search_agent if you want to observe how two parallel agents work
    # sub_agents=[rag_search_agent, web_search_agent],
    sub_agents=[rag_search_agent],
)


app_name = "veadk_playground_app"
user_id = "veadk_playground_user"
session_id = "veadk_playground_session"

short_term_memory = ShortTermMemory()

runner = Runner(
    agent=parallel_get_info_agent,
    short_term_memory=short_term_memory,
    app_name=app_name,
    user_id=user_id,
)


async def main():
    response = await runner.run(
        messages="我想买一台火山引擎虚拟机，用来做图像处理，可以帮我介绍一下哪个规格更适合我吗？",
        session_id=session_id,
    )
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
