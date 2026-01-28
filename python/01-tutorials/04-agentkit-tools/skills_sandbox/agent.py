from agentkit.apps import AgentkitAgentServerApp
from veadk import Agent
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.tools.builtin_tools.execute_skills import execute_skills
from prompts.prompt import ROOT_AGENT_INSTRUCTION_CN, ROOT_AGENT_INSTRUCTION_EN
import os

app_name = "agent_skills_app"
user_id = "agent_skills_user"
session_id = "agent_skills_session"

ROOT_AGENT_INSTRUCTION = ROOT_AGENT_INSTRUCTION_CN

provider = os.getenv("CLOUD_PROVIDER")
if provider and provider.lower() == "byteplus":
    ROOT_AGENT_INSTRUCTION = ROOT_AGENT_INSTRUCTION_EN

skill_space_id = os.getenv("SKILL_SPACE_ID")
agent = Agent(
    name="skill_agent",
    instruction=ROOT_AGENT_INSTRUCTION,
    skills=[skill_space_id],
    tools=[execute_skills],
)

short_term_memory = ShortTermMemory(backend="local")

# using veadk web for debugging
root_agent = agent

agent_server_app = AgentkitAgentServerApp(
    agent=agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
