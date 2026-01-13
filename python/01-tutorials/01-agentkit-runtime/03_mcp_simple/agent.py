import os

from agentkit.apps import AgentkitAgentServerApp
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StreamableHTTPConnectionParams,
)
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from veadk import Agent, Runner
from veadk.memory.short_term_memory import ShortTermMemory

url = os.getenv("TOOL_TOS_URL")

# Only initialize MCPToolset if URL is provided
if url:
    tos_mcp_runner = MCPToolset(
        connection_params=StreamableHTTPConnectionParams(url=url, timeout=120),
    )
    tools = [tos_mcp_runner]
else:
    tools = []

short_term_memory = ShortTermMemory(backend="local")

root_agent = Agent(
    name="tos_mcp_agent",
    instruction="你是一个对象存储管理专家，精通使用MCP协议进行对象存储的各种操作。"
    + (
        ""
        if tools
        else "\n\n注意：当前未配置 TOOL_TOS_URL 环境变量，MCP 工具不可用。请设置环境变量后重启。"
    ),
    tools=tools,
)

runner = Runner(agent=root_agent)

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
