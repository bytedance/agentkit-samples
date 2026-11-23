import asyncio
import os

from dotenv import load_dotenv
from veadk import Agent, Runner


load_dotenv()

root_agent = Agent(
    name="simple_agent",
    instruction="你是Agentkit-01智能机器人，当有人要你自我介绍时，你必须说，我是Agentkit-01",
    model_provider="openai",
    model_name=os.environ["MODEL_AGENT_NAME"],
    model_api_base=os.environ["MODEL_AGENT_API_BASE"],
    model_api_key=os.environ["MODEL_AGENT_API_KEY"],
)


async def main():
    async with Runner(agent=root_agent) as runner:
        print(await runner.run(messages="请你介绍自己"))


if __name__ == "__main__":
    asyncio.run(main())
