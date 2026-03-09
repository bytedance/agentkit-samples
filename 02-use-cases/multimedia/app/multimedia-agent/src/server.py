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

from multimedia_agent.agent import root_agent
from veadk.memory.short_term_memory import ShortTermMemory
from agentkit import AgentkitAgentServerApp

short_term_memory = ShortTermMemory(backend="local")
agent_server_app = AgentkitAgentServerApp(
    agent=root_agent, short_term_memory=short_term_memory
)

app = agent_server_app.app
