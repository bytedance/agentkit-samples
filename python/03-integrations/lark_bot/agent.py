from veadk import Agent, Runner
from veadk.memory import ShortTermMemory
from veadk.tools.builtin_tools.web_search import web_search

APP_NAME = "LARK_AGENT"

root_agent = Agent(
    name="chatbot",
    description="A chatbot that can help users with their questions.",
    instruction="You are a helpful chatbot that can answer users' questions.",
    short_term_memory=ShortTermMemory(backend="local"),
    tools=[web_search],
)
runner = Runner(agent=root_agent, app_name=APP_NAME)


async def run_agent(prompt: str, user_id: str, session_id: str) -> str:
    print(prompt, user_id, session_id)
    return await runner.run(prompt, user_id, session_id)
