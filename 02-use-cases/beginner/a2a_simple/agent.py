from a2a.types import AgentCapabilities, AgentCard, AgentProvider, AgentSkill
from agentkit.apps import AgentkitA2aApp
from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
from tools.check_prime import check_prime
from tools.roll_die import roll_die
from veadk import Agent, Runner

a2a_app = AgentkitA2aApp()
root_agent = Agent(
    name="hello_world_agent",
    description=(
        "hello world agent that can roll a dice of 8 sides and check prime numbers."
    ),
    instruction="""
      You roll dice and answer questions about the outcome of the dice rolls.
      You can roll dice of different sizes.
      You can use multiple tools in parallel by calling functions in parallel(in one request and in one round).
      It is ok to discuss previous dice roles, and comment on the dice rolls.
      When you are asked to roll a die, you must call the roll_die tool with the number of sides. Be sure to pass in an integer. Do not pass in a string.
      You should never roll a die on your own.
      When checking prime numbers, call the check_prime tool with a list of integers. Be sure to pass in a list of integers. You should never pass in a string.
      You should not check prime numbers before calling the tool.
      When you are asked to roll a die and check prime numbers, you should always make the following two function calls:
      1. You should first call the roll_die tool to get a roll. Wait for the function response before calling the check_prime tool.
      2. After you get the function response from roll_die tool, you should call the check_prime tool with the roll_die result.
        2.1 If user asks you to check primes based on previous rolls, make sure you include the previous rolls in the list.
      3. When you respond, you must include the roll_die result from step 1.
      You should always perform the previous 3 steps when asking for a roll and checking prime numbers.
      You should not rely on the previous history on prime results.
    """,
    tools=[
        roll_die,
        check_prime,
    ],
)

runner = Runner(agent=root_agent)


@a2a_app.agent_executor(runner=runner)
class MyAgentExecutor(A2aAgentExecutor):
    pass


agent_card = AgentCard(
    capabilities=AgentCapabilities(streaming=True),
    description=root_agent.description,
    name=root_agent.name,
    default_input_modes=["text"],
    default_output_modes=["text"],
    provider=AgentProvider(organization="agentkit", url=""),
    skills=[AgentSkill(id="0", name="chat", description="Chat", tags=["chat"])],
    url="http://localhost:8000",
    version="1.0.0",
)

print("agent start successfully ", root_agent.name)

# a2a_app = to_a2a(root_agent, port=8001)
if __name__ == "__main__":
    a2a_app.run(agent_card=agent_card, host="0.0.0.0", port=8000)
