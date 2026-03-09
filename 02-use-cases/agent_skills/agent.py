# Deploy the agent as AgentkitAgentServerApp into the agentkit platform
from agentkit.apps import AgentkitAgentServerApp
from veadk import Agent, Runner
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.tools.builtin_tools.execute_skills import execute_skills

app_name = "agent_skills_app"
user_id = "agent_skills_user"
session_id = "agent_skills_session"

agent = Agent(
    name="skill_agent",
    instruction="根据用户的需求，调用 execute_skills 工具执行 skills，",
    tools=[execute_skills],
)

short_term_memory = ShortTermMemory(backend="local")

runner = Runner(
    agent=agent,
    short_term_memory=short_term_memory,
    app_name=app_name,
    user_id=user_id,
)

# using veadk web for debugging
root_agent = agent

agent_server_app = AgentkitAgentServerApp(
    agent=agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
