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

import os

from agentkit.apps import AgentkitAgentServerApp
from veadk import Agent, Runner
from veadk.memory import LongTermMemory, ShortTermMemory
from google.adk.agents.callback_context import CallbackContext


# 这里仅做记忆保存的演示，实际根据需求选择会话保存到长期记忆中
async def after_agent_execution(callback_context: CallbackContext):
    session = callback_context._invocation_context.session
    await long_term_memory.add_session_to_memory(session)


vikingmem_app_name = os.getenv("DATABASE_VIKINGMEM_COLLECTION", "vikingmem_agent_app")

short_term_memory = ShortTermMemory()
long_term_memory = LongTermMemory(backend="viking", index=vikingmem_app_name)
root_agent = Agent(
    name="vikingmem_agent",
    instruction="你是一个具备长期记忆的智能助手，擅长用中文回答问题。能够根据情况，搜索过往记忆来回答用户问题。",
    long_term_memory=long_term_memory,
    after_agent_callback=after_agent_execution,
)

runner = Runner(
    agent=root_agent,
    short_term_memory=short_term_memory,
    app_name="vikingmem_agent",
    user_id="user_id",
)

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
