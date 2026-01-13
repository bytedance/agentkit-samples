import asyncio

from multi_agents.agent import root_agent
from veadk import Runner
from veadk.memory.short_term_memory import ShortTermMemory

app_name = "veadk_playground_app"
user_id = "veadk_playground_user"
session_id = "veadk_playground_session"

short_term_memory = ShortTermMemory()

runner = Runner(
    agent=root_agent,
    short_term_memory=short_term_memory,
    app_name=app_name,
    user_id=user_id,
)


async def main():
    # 我买了一台火山引擎虚拟机，用来做图像处理，但是我感觉性能不是很符合我的需求。给我分析一下怎么回事，如果需要换机器帮我推荐一下更合适的规格。
    response = await runner.run(
        messages="我想买一台火山引擎虚拟机，用来做图像处理，可以帮我介绍一下哪个规格更适合我吗？",
        session_id=session_id,
    )
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
