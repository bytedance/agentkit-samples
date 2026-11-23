import asyncio
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.tools.agent_tool import AgentTool
from veadk import Agent, Runner


load_dotenv()

remote_http_client = httpx.AsyncClient(
    headers={"Apikey": os.environ["HI_AGENT_API_KEY"]},
    timeout=60,
)
remote_agent = RemoteA2aAgent(
    name="remote_agent",
    description="通过 A2A 连接的远程助手，处理用户要求转交给远程 Agent 的任务。",
    agent_card=str(Path(__file__).with_name("remote_agentcard.json")),
    httpx_client=remote_http_client,
)

root_agent = Agent(
    name="simple_agent",
    instruction="你是人工智能助手。用户要求远程处理时，调用 remote_agent 工具，并返回远程回复。",
    model_provider="openai",
    model_name=os.environ["MODEL_AGENT_NAME"],
    model_api_base=os.environ["MODEL_AGENT_API_BASE"],
    model_api_key=os.environ["MODEL_AGENT_API_KEY"],
    tools=[AgentTool(agent=remote_agent)],
)


async def main():
    async with remote_http_client:
        async with Runner(agent=root_agent) as runner:
            print(
                await runner.run(
                    messages="请让远程 Agent 介绍他自己，然后将他的介绍原封不动的回复给我。"
                )
            )


if __name__ == "__main__":
    asyncio.run(main())
