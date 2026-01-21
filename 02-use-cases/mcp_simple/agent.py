import os
from agentkit.apps import AgentkitAgentServerApp
from veadk import Agent
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.tools.builtin_tools.mcp_router import mcp_router

short_term_memory = ShortTermMemory(backend="local")

root_agent = Agent(
    name="mcp_agent",
    model_name=os.getenv("MODEL_AGENT_NAME", "doubao-seed-1-8-251228"),
    instruction="你是一个具备深度推理能力的 AI 助手。当你遇到复杂逻辑、数学、编程或需要多步推理的问题时，请务必使用MCP工具辅助完成用户的问题。",
    tools=[mcp_router],
    model_extra_config={"extra_body": {"thinking": {"type": "disabled"}}},
)

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
