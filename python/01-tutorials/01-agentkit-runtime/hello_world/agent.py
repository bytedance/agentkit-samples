# Deploy the agent as AgentkitAgentServerApp into the agentkit platform
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

from agentkit.apps import AgentkitAgentServerApp
from veadk import Agent, Runner
from veadk.memory.short_term_memory import ShortTermMemory
from prompts.prompt import ROOT_AGENT_INSTRUCTION_CN, ROOT_AGENT_INSTRUCTION_EN

app_name = "veadk_playground_app_short_term_local"
user_id = "veadk_playground_user_short_term_local"
session_id = "veadk_playground_session_short_term_local"

ROOT_AGENT_INSTRUCTION = ROOT_AGENT_INSTRUCTION_CN

provider = os.getenv("CLOUD_PROVIDER")
if provider and provider.lower() == "byteplus":
    ROOT_AGENT_INSTRUCTION = ROOT_AGENT_INSTRUCTION_EN

agent = Agent(
    name="hello_world",
    model_name=os.getenv("MODEL_AGENT_NAME", "deepseek-v3-2-251201"),
    description="hello world agent",
    instruction=ROOT_AGENT_INSTRUCTION,
)
short_term_memory = ShortTermMemory(backend="local")

runner = Runner(
    agent=agent,
    short_term_memory=short_term_memory,
    app_name=app_name,
    user_id=user_id,
)


async def main():
    response1 = await runner.run(messages="My name is ADK", session_id=session_id)
    print(f"response of round 1: {response1}")

    response2 = await runner.run(messages="What is my name?", session_id=session_id)
    print(f"response of round 2: {response2}")


# using veadk web for debugging
root_agent = agent

agent_server_app = AgentkitAgentServerApp(
    agent=agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
