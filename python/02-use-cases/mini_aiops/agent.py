import os
import sys

from agentkit.apps import AgentkitAgentServerApp
from google.adk.planners import BuiltInPlanner
from google.adk.tools.mcp_tool.mcp_toolset import (
    McpToolset,
    StdioServerParameters,
    StdioConnectionParams,
)
from google.genai import types
from veadk import Agent
from veadk.auth.veauth.utils import get_credential_from_vefaas_iam
from veadk.config import getenv  # noqa
from veadk.memory.short_term_memory import ShortTermMemory


env_dict = {
    "VOLCENGINE_ACCESS_KEY": os.getenv("VOLCENGINE_ACCESS_KEY"),
    "VOLCENGINE_SECRET_KEY": os.getenv("VOLCENGINE_SECRET_KEY"),
}
if not (env_dict["VOLCENGINE_ACCESS_KEY"] and env_dict["VOLCENGINE_SECRET_KEY"]):
    credential = get_credential_from_vefaas_iam()
    env_dict["VOLCENGINE_ACCESS_KEY"] = credential.access_key_id
    env_dict["VOLCENGINE_SECRET_KEY"] = credential.secret_access_key
    env_dict["VOLCENGINE_SESSION_TOKEN"] = credential.session_token

short_term_memory = ShortTermMemory(backend="local")

### control center mcp server
server_parameters = StdioServerParameters(
    command=sys.executable,
    args=["-m", "mcp_server_ccapi"],
    env=env_dict,
)

ccapi_mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=server_parameters, timeout=180.0
    ),
    errlog=None,
)

model = os.getenv("MODEL_AGENT_NAME", "deepseek-v4-pro-260425")

agent: Agent = Agent(
    name="root_agent",
    model_name=model,
    description="云资源管控智能体",
    instruction="你是一个云资源管控专家，擅长通过 CCAPI 管理各类云资源",
    tools=[ccapi_mcp_toolset],
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=False,
            thinking_budget=0,
        )
    ),
)

root_agent = agent


agent_server_app = AgentkitAgentServerApp(
    agent=agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
