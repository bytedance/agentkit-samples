import os
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.tools import tool
from dotenv import load_dotenv
import logging
import asyncio
import json


# Load environment variables (especially OPENAI_API_KEY)
load_dotenv()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# 1. Define tools
@tool
def get_word_length(word: str) -> int:
    """Returns the length of a word."""
    return len(word)


@tool
def add_numbers(a: int, b: int) -> int:
    """Adds two numbers together."""
    return a + b


# Create the agent
# Fix: Ensure environment variables are mapped to the correct arguments
agent = create_agent(
    model=ChatOpenAI(
        model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
        temperature=0,
    ),
    tools=[get_word_length, add_numbers],
    system_prompt="You are a helpful assistant. You have access to tools to help answer questions.",
)


async def run(payload: dict, headers: dict):
    prompt = payload.get("prompt")
    user_id = headers.get("user_id")
    session_id = headers.get("session_id")

    # Default values if still missing
    user_id = user_id or "default_user"
    session_id = session_id or "default_session"

    logger.info(
        f"Running agent with prompt: {prompt}, user_id: {user_id}, session_id: {session_id}"
    )

    inputs = {"messages": [{"role": "user", "content": prompt}]}

    # stream returns an iterator of updates
    # To get the final result, we can just iterate or use invoke
    async for chunk in agent.astream(inputs, stream_mode="updates"):
        # chunk is a dict with node names as keys and state updates as values
        for node, state in chunk.items():
            logger.debug(f"--- Node: {node} ---")

            if "messages" in state:
                last_msg = state["messages"][-1]

                for block in last_msg.content_blocks:
                    event_data = {"content": {"parts": [{"text": block.get("text")}]}}
                    yield json.dumps(event_data)


async def local_test():
    """Helper to run the agent locally without server"""
    print("Running local test...")
    query = "What is the length of the word 'LangChain' and what is that length plus 5?"
    print(f"Query: {query}")
    async for event in run({"prompt": query}, {"user_id": "1", "session_id": "1"}):
        print(f"Received event: {event}")


if __name__ == "__main__":
    asyncio.run(local_test())
