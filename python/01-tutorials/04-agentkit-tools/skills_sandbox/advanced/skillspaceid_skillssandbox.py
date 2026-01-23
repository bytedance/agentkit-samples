from agentkit.apps import AgentkitAgentServerApp
from veadk import Agent, Runner
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.tools.builtin_tools.execute_skills import execute_skills
import os
import asyncio

app_name = "agent_skills_app"
user_id = "agent_skills_user"
session_id = "agent_skills_skillspaceid_skillssandbox_session"

skill_space_id = os.getenv("SKILL_SPACE_ID")
agent = Agent(
    name="skill_agent",
    instruction="根据用户的需求，调用 execute_skills 工具执行 skills，",
    skills=[skill_space_id],
    tools=[execute_skills],
)

short_term_memory = ShortTermMemory(backend="local")

runner = Runner(
    agent=agent,
    short_term_memory=short_term_memory,
    app_name=app_name,
    user_id=user_id,
)


async def main():
    messages = """
    请运行以下工作流程：
    1. 帮我写一个pdf处理的skill，能够支持加载pdf、编辑pdf和从pdf中提取文字信息即可。
    2. 将写好的 skill 注册到 skill space。
    """
    response = await runner.run(messages=messages, session_id=session_id)
    print(f"response: {response}")


# using veadk web for debugging
root_agent = agent

agent_server_app = AgentkitAgentServerApp(
    agent=agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    asyncio.run(main())
    # agent_server_app.run(host="0.0.0.0", port=8000)
