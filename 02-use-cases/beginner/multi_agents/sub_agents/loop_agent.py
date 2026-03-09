import asyncio

from google.adk.tools.tool_context import ToolContext
from prompts import (
    JUDGE_AGENT_PROMPT,
    LOOP_REFINE_RESPONSE_AGENT_PROMPT,
    REFINE_AGENT_PROMPT,
)
from veadk import Agent, Runner
from veadk.agents.loop_agent import LoopAgent
from veadk.memory.short_term_memory import ShortTermMemory

judge_agent = Agent(
    name="judge_agent",
    description="负责评价客服回复，不进行改写，需给出明确结论、理由及优化方向",
    instruction=JUDGE_AGENT_PROMPT,
)

refine_agent = Agent(
    name="refine_agent",
    description="基于 judge_agent 的评价结果改写回复，确保优化后同时满足 “有用 + 礼貌” 双标准",
    instruction=REFINE_AGENT_PROMPT,
)


def exit_tool(tool_context: ToolContext) -> str:
    print(f"  [Tool Call] exit_loop triggered by {tool_context.agent_name}")
    # tool_context.actions.escalate = True
    tool_context.actions.end_of_agent = True
    return {}


loop_refine_response_agent = LoopAgent(
    name="loop_refine_response_agent",
    description="作为客服回复处理的统筹者，自动触发子 Agent 调用流程，接收最终优化结果并输出",
    instruction=LOOP_REFINE_RESPONSE_AGENT_PROMPT,
    sub_agents=[judge_agent, refine_agent],
    tools=[exit_tool],
    max_iterations=1,
)


app_name = "veadk_playground_app"
user_id = "veadk_playground_user"
session_id = "veadk_playground_session"

short_term_memory = ShortTermMemory()

runner = Runner(
    agent=loop_refine_response_agent,
    short_term_memory=short_term_memory,
    app_name=app_name,
    user_id=user_id,
)


async def main():
    response = await runner.run(
        messages="用户问题：“我买的衣服尺码偏小，能换大一号吗？需要什么流程？” 客服原始回复：“能换。把吊牌留着，自己寄回来，运费先垫上，到时候退你。”",
        session_id=session_id,
    )
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
