from veadk import Agent, Runner
from veadk.memory.short_term_memory import ShortTermMemory

# Deploy the agent as AgentkitAgentServerApp into the agentkit platform
from agentkit.apps import AgentkitAgentServerApp

app_name = "veadk_playground_app_short_term_local"
user_id = "veadk_playground_user_short_term_local"
session_id = "veadk_playground_session_short_term_local"

agent = Agent()
short_term_memory = ShortTermMemory(
    backend="local"
)  # 指定 local 后端，或直接 ShortTermMemory()

runner = Runner(
    agent=agent, short_term_memory=short_term_memory, app_name=app_name, user_id=user_id
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
