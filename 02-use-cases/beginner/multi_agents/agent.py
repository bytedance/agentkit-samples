from veadk import Agent, Runner
from veadk.memory.short_term_memory import ShortTermMemory
from sub_agents.sequential_agent import sequential_service_agent
from prompts import CUSTOMER_SERVICE_AGENT_PROMPT, PRE_PROCESS_AGENT_PROMPT
from agentkit.apps import AgentkitAgentServerApp

short_term_memory = ShortTermMemory(
    backend="local"
)  # 指定 local 后端，或直接 ShortTermMemory()

pre_process_agent = Agent(
    name="pre_process_agent",
    description="分析用户需求，提取关键信息",
    instruction=PRE_PROCESS_AGENT_PROMPT,
)

customer_service_agent = Agent(
    name="customer_service_agent",
    description=("你是一个智能客服，根据用户需求，回答用户问题"),
    instruction=CUSTOMER_SERVICE_AGENT_PROMPT,
    sub_agents=[pre_process_agent, sequential_service_agent]
)

root_agent = customer_service_agent

runner = Runner(agent=root_agent)

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)