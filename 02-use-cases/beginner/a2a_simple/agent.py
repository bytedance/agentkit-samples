from veadk.a2a.remote_ve_agent import RemoteVeAgent
from veadk.agent import Agent

remote_agent = RemoteVeAgent(
    name="a2a_agent",
    url="http://localhost:8001/",  # <--- url from cloud platform
)

def add(a: int, b: int) -> int:
    """Adds two numbers."""
    return a + b

root_agent = Agent(
    name="a2a_sample_agent",
    instruction="You are a helpful assistant.",
    tools=[add],
    sub_agents=[remote_agent],
)