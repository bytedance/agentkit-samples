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
from google.adk.plugins.context_filter_plugin import ContextFilterPlugin
from veadk import Agent
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.tools.builtin_tools.web_search import web_search

short_term_memory = ShortTermMemory(backend="local")

DEFAULT_MODEL_AGENT_NAME = "deepseek-v4-pro-260425"

agent = Agent(
    name="context_filter_agent",
    description="An agent that keeps only the most recent turns in the LLM context.",
    model_name=os.getenv("MODEL_AGENT_NAME", DEFAULT_MODEL_AGENT_NAME),
    instruction=(
        "You are a helpful assistant for long, multi-turn conversations. "
        "Answer the user's questions clearly based on the context you are given. "
        "If the user asks about recent facts, you can use the web_search tool. "
        "Note: respond in the same language the user uses."
    ),
    tools=[web_search],
)

root_agent = agent

# App 级别配置上下文过滤（Context Filter）。
# 在长对话中，历史事件会不断累积并占满上下文窗口，导致 token 成本升高甚至超限。
# ContextFilterPlugin 会在每次调用模型前，只保留最近 N 次调用的对话内容，
# 直接丢弃更早的历史。实现简单、开销极低，代价是超出保留窗口的信息会丢失。
app = App(
    name="context_filter",
    root_agent=root_agent,
    plugins=[
        ContextFilterPlugin(
            num_invocations_to_keep=3,  # 只保留最近 3 次调用的上下文
        )
    ],
)

# 注意：这里必须把带 plugins 的 `app` 传给 `app=` 参数，
# 而不是传裸 `agent`。否则 App 上的插件不会被加载，上下文过滤不会生效。
agent_server_app = AgentkitAgentServerApp(
    app=app,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
