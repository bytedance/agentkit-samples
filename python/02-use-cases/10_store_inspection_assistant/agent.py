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

from agentkit.apps import AgentkitAgentServerApp
from veadk import Runner
from veadk.agent_builder import AgentBuilder
from veadk.memory.short_term_memory import ShortTermMemory

# 建议通过logging.basicConfig设置全局logger，默认Log级别为INFO
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# current path
sys.path.append(str(Path(__file__).resolve().parent))
# parent path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# 1. Define root_agent with veadk.AgentBuilder (support veadk web)
yaml_path = "agent.yaml"
if not os.path.isfile(yaml_path):
    yaml_path = "inspection_assistant/agent.yaml"

app_name = "inspection_assistant"
agent_builder = AgentBuilder()
agent = agent_builder.build(path=yaml_path)
runner = Runner(agent=agent, app_name=app_name)

# support veadk web
root_agent = agent

# 2. Build Agent as Server App (support agentkit)
short_term_memory = ShortTermMemory(backend="local")
agent_server_app = AgentkitAgentServerApp(
    agent=root_agent, short_term_memory=short_term_memory
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
