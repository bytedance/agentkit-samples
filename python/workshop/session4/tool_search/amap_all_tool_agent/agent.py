from google.adk.planners import BuiltInPlanner
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StreamableHTTPConnectionParams,
)
from google.genai import types
from veadk import Agent
from veadk.config import getenv
from veadk.memory.short_term_memory import ShortTermMemory

short_term_memory = ShortTermMemory(backend="local")

amap_mcp_tool_api_key = getenv("AMAP_MCP_TOOL_API_KEY")
amap_mcp_tool_url = getenv("AMAP_MCP_TOOL_URL")
amap_mcp_tool = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=amap_mcp_tool_url,
        headers={"Authorization": f"Bearer {amap_mcp_tool_api_key}"},
    ),
)

github_tool_url = getenv("GITHUB_TOOL_URL")
github_tool_api_key = getenv("GITHUB_TOOL_API_KEY")
github_mcp_tool = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=github_tool_url,
        headers={"Authorization": f"Bearer {github_tool_api_key}"},
    ),
)

agent_model_name = getenv("MODEL_AGENT_NAME")

agent: Agent = Agent(
    name="amap_tool_agent",
    model_name=agent_model_name,
    instruction="You are an map agent.",
    # planner=PlanReActPlanner(),
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
        ),
    ),
    tools=[amap_mcp_tool, github_mcp_tool],
    short_term_memory=short_term_memory,
)

root_agent = agent
