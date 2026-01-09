# Deploy the agent as AgentkitAgentServerApp into the agentkit platform
from agentkit.apps import AgentkitAgentServerApp
from veadk import Agent, Runner
from veadk.memory.short_term_memory import ShortTermMemory

app_name = "veadk_playground_app_short_term_local"
user_id = "veadk_playground_user_short_term_local"
session_id = "veadk_playground_session_short_term_local"

agent = Agent(
    name="hello_world",
    description="hello world agent",
    instruction="""你是一个智能助手，擅长用中文礼貌回复用户的问题。""",
)
short_term_memory = ShortTermMemory(backend="local")

runner = Runner(
    agent=agent,
    short_term_memory=short_term_memory,
    app_name=app_name,
    user_id=user_id,
)


async def main():
    response1 = await runner.run(messages="我叫VeADK", session_id=session_id)
    print(f"response of round 1: {response1}")

    response2 = await runner.run(messages="你还记得我叫什么吗？", session_id=session_id)
    print(f"response of round 2: {response2}")


# using veadk web for debugging
root_agent = agent

agent_server_app = AgentkitAgentServerApp(
    agent=agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
