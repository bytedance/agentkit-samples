import asyncio

from prompts import SEQUENTIAL_SERVICE_AGENT_PROMPT
from sub_agents.loop_agent import loop_refine_response_agent
from sub_agents.parallel_agent import parallel_get_info_agent
from veadk import Runner
from veadk.agents.sequential_agent import SequentialAgent
from veadk.memory.short_term_memory import ShortTermMemory

sequential_service_agent = SequentialAgent(
    name="sequential_service_agent",
    description="根据用户需求，逐步执行工作流，生成最佳回复结果",
    instruction=SEQUENTIAL_SERVICE_AGENT_PROMPT,
    sub_agents=[parallel_get_info_agent, loop_refine_response_agent],
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
        messages="我买了一台火山引擎虚拟机，用来做图像处理，但是我感觉性能不是很符合我的需求。给我分析一下怎么回事，如果需要换机器帮我推荐一下更合适的规格。",
        session_id=session_id,
    )
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
