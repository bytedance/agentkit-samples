import os
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from veadk import Agent, Runner
from agentkit.apps import AgentkitAgentServerApp
from veadk.memory.short_term_memory import ShortTermMemory

url = os.getenv("TOOL_TOS_URL")

tos_mcp_runner = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=url,
        timeout=120
    ),
)

short_term_memory = ShortTermMemory(
    backend="local"
)  # 指定 local 后端，或直接 ShortTermMemory()

root_agent = Agent(
    name="tos_mcp_agent",
    instruction="你是一个对象存储管理专家，精通使用MCP协议进行对象存储的各种操作。",
    tools=[tos_mcp_runner],
)

runner = Runner(agent=root_agent)

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)