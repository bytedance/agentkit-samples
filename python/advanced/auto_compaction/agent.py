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
from google.adk.apps import App
from google.adk.apps.app import EventsCompactionConfig
from veadk import Agent
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.tools.builtin_tools.web_search import web_search

short_term_memory = ShortTermMemory(backend="local")

DEFAULT_MODEL_AGENT_NAME = "deepseek-v4-pro-260425"

agent = Agent(
    name="auto_compaction_agent",
    description="An agent that demonstrates automatic context compaction for long conversations.",
    model_name=os.getenv("MODEL_AGENT_NAME", DEFAULT_MODEL_AGENT_NAME),
    instruction=(
        "You are a helpful assistant for long, multi-turn conversations. "
        "Answer the user's questions clearly and keep track of what was discussed earlier. "
        "If the user asks about recent facts, you can use the web_search tool. "
        "Note: respond in the same language the user uses."
    ),
    tools=[web_search],
)

root_agent = agent

# App 级别配置自动上下文压缩（Events Compaction）。
# 在长对话中，历史事件会不断累积并占满上下文窗口，导致 token 成本升高甚至超限。
# 框架会周期性地把较早的对话事件自动总结压缩为摘要，在保留关键信息的同时降低上下文长度。
app = App(
    name="auto_compaction",
    root_agent=root_agent,
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=3,  # 每新增 3 次调用触发一次压缩
        overlap_size=1,  # 压缩时保留上一个窗口的最后 1 次调用，避免上下文断层
    ),
)

# 注意：这里必须把带 events_compaction_config 的 `app` 传给 `app=` 参数，
# 而不是传裸 `agent`。否则 App 上的压缩配置会被忽略，自动压缩不会生效。
agent_server_app = AgentkitAgentServerApp(
    app=app,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
