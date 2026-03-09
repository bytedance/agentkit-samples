import os
import sys

from agentkit.apps import AgentkitAgentServerApp
from veadk import Agent, Runner
from veadk.memory.short_term_memory import ShortTermMemory


# Add current directory to Python path to support sub_agents imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prompts import CUSTOMER_SERVICE_AGENT_PROMPT, PRE_PROCESS_AGENT_PROMPT
from sub_agents.sequential_agent import sequential_service_agent

short_term_memory = ShortTermMemory(
    backend="local"
)  # 指定 local 后端，或直接 ShortTermMemory()

pre_process_agent = Agent(
    name="pre_process_agent",
    description="星辰电商智能客服的需求分析师，负责识别问题类型、提取关键信息、生成处理策略",
    instruction=PRE_PROCESS_AGENT_PROMPT,
)

customer_service_agent = Agent(
    name="customer_service_agent",
    description="星辰电商平台智能客服「小星」，热情专业地处理订单、物流、售后、会员等咨询",
    instruction=CUSTOMER_SERVICE_AGENT_PROMPT,
    sub_agents=[pre_process_agent, sequential_service_agent],
)

root_agent = customer_service_agent

runner = Runner(agent=root_agent)

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
