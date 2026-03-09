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

# amap_mcp_api_key
amap_mcp_tool_set_api_key = getenv("AMAP_MCP_TOOL_SET_API_KEY")
amap_mcp_tool_set_url = getenv("AMAP_MCP_TOOL_SET_URL")
amap_mcp_tool_set = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=amap_mcp_tool_set_url,
        headers={"Authorization": f"Bearer {amap_mcp_tool_set_api_key}"},
    ),
)

agent_model_name = getenv("MODEL_AGENT_NAME")

agent: Agent = Agent(
    name="amap_tool_set_agent",
    model_name=agent_model_name,
    instruction="You are an map agent.",
    # planner=PlanReActPlanner(),
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
        ),
    ),
    tools=[amap_mcp_tool_set],
    short_term_memory=short_term_memory,
)

root_agent = agent
