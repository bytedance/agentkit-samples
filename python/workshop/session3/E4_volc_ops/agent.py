from typing import Any
from google.adk.planners import BuiltInPlanner
from google.adk.tools.mcp_tool.mcp_toolset import (
    StreamableHTTPConnectionParams,
)
from google.genai import types
from veadk import Agent
from veadk.config import getenv
from veadk.integrations.ve_identity import (
    VeIdentityMcpToolset,
    IdentityClient,
    oauth2_auth,
    AuthRequestProcessor,
)
from veadk.config import settings
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.tool_context import ToolContext
from veadk.integrations.ve_identity.auth_mixins import OAuth2AuthMixin

identity_client = IdentityClient(region=settings.veidentity.region)

# 创建 ECS MCP Tool
mcp_ecs = VeIdentityMcpToolset(
    auth_config=oauth2_auth(
        provider_name="ecs-oauth-provider",
        auth_flow="USER_FEDERATION",
        identity_client=identity_client,
    ),
    connection_params=StreamableHTTPConnectionParams(
        url=getenv("ECS_MCP_URL", "https://ecs.mcp.volcbiz.com/ecs/mcp"),
        timeout=30.0,
    ),
)


async def clean_state(args: dict[str, Any], *, tool_context: ToolContext) -> None:
    """Clean user's Oauth identity state.

    Args:
        args: fixed arguments for cleaning identity state: {"op": "clean"}
    """
    oauth_client = OAuth2AuthMixin(
        provider_name="ecs-oauth-provider",
        auth_flow="USER_FEDERATION",
        force_authentication=True,
    )
    await oauth_client._get_oauth2_token_or_auth_url(tool_context=tool_context)
    return None


clean_state_tool = FunctionTool(clean_state)

# 创建独立的 ECS Agent
ecs_agent: Agent = Agent(
    name="ecs_agent",
    description="ECS 运维智能体",
    instruction="你是一个 ECS 云服务器运维专家, 你可以使用 ECS 工具来管理云服务器，如果用户想清理自己的身份凭据，你可以调用 clean_state_tool 工具。",
    tools=[mcp_ecs, clean_state_tool],
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=1024,
        )
    ),
    run_processor=AuthRequestProcessor(),
)

root_agent = ecs_agent
