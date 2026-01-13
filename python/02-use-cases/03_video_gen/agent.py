# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
import sys
from pathlib import Path

from agentkit.apps import AgentkitAgentServerApp, AgentkitSimpleApp
from google.adk.tools.mcp_tool.mcp_toolset import (
    McpToolset,
    StdioConnectionParams,
    StdioServerParameters,
)
from veadk import Runner
from veadk.agent_builder import AgentBuilder
from veadk.memory.short_term_memory import ShortTermMemory
from consts import set_veadk_environment_variables

# 建议通过logging.basicConfig设置全局logger，默认Log级别为INFO
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 当前目录
sys.path.append(str(Path(__file__).resolve().parent))

# 上层目录
sys.path.append(str(Path(__file__).resolve().parent.parent))

# env
set_veadk_environment_variables()

app_name = "storyvideo"
app = AgentkitSimpleApp()
agent_builder = AgentBuilder()

# 配置MCP Tool，用于视频剪辑
server_parameters = StdioServerParameters(
    command="npx",
    args=["@pickstar-2002/video-clip-mcp@latest"],
)
mcpTool = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=server_parameters, timeout=600.0
    ),
    errlog=None,
)

yaml_path = "agent.yaml"
if not os.path.isfile(yaml_path):
    yaml_path = "video_gen/agent.yaml"

agent = agent_builder.build(path=yaml_path)
agent.tools.append(mcpTool)

runner = Runner(agent=agent, app_name=app_name)
# support veadk web
root_agent = agent

# support api server
short_term_memory = ShortTermMemory(backend="local")
agent_server_app = AgentkitAgentServerApp(
    agent=agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
