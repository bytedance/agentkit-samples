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
import sys
from pathlib import Path

# 将 comic_drama_gen 目录加入 sys.path，同时支持 uv run agent.py 和模块运行两种方式
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from agentkit.apps import AgentkitAgentServerApp, AgentkitSimpleApp  # noqa: E402
from google.adk.tools.mcp_tool.mcp_toolset import (  # noqa: E402
    McpToolset,
    StdioConnectionParams,
    StdioServerParameters,
)
from veadk import Agent as VeadkAgent  # noqa: E402
from veadk import Runner  # noqa: E402
from veadk.agent_builder import AgentBuilder  # noqa: E402
from veadk.memory.short_term_memory import ShortTermMemory  # noqa: E402
from consts import set_veadk_environment_variables  # noqa: E402

# 建议通过logging.basicConfig设置全局logger，默认Log级别为INFO
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# env
set_veadk_environment_variables()

app_name = "comic_drama_master"
app = AgentkitSimpleApp()
agent_builder = AgentBuilder()

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

yaml_path = str(Path(__file__).resolve().parent / "agent.yaml")

_agent = agent_builder.build(path=yaml_path)
agent: VeadkAgent = _agent  # type: ignore[assignment]

skill_dir = str(Path(__file__).resolve().parent / "skill")
agent.skills = [skill_dir]
agent.skills_mode = "local"
agent.load_skills()

agent.tools.append(mcpTool)

runner = Runner(agent=agent, app_name=app_name)
# support veadk web
root_agent = agent

# support api server
short_term_memory = ShortTermMemory(
    backend="sqlite",
    local_database_path=str(Path(__file__).resolve().parent / ".data" / "sessions.db"),
)
agent_server_app = AgentkitAgentServerApp(
    agent=agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
