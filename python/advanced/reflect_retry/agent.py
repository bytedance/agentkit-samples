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
from google.adk.plugins import ReflectAndRetryToolPlugin
from veadk import Agent
from veadk.memory.short_term_memory import ShortTermMemory

short_term_memory = ShortTermMemory(backend="local")

DEFAULT_MODEL_AGENT_NAME = "deepseek-v4-pro-260425"

# 一个"不稳定"的示例工具：前两次调用会抛错，第三次才成功。
# 用于演示 ReflectAndRetryToolPlugin 在工具失败时如何引导模型反思并自动重试。
_attempts: dict[str, int] = {}


def flaky_weather(city: str) -> dict:
    """Query the current weather of a city.

    Args:
        city: The city name to query, e.g. "Beijing".

    Returns:
        A dict containing the city and its weather description.
    """
    count = _attempts.get(city, 0) + 1
    _attempts[city] = count
    if count < 3:
        # 模拟一个瞬时故障（如网络抖动 / 限流），前两次失败。
        raise RuntimeError(
            f"Upstream weather service temporarily unavailable "
            f"(attempt {count}). Please retry."
        )
    return {"city": city, "weather": "Sunny, 26°C"}


agent = Agent(
    name="reflect_retry_agent",
    description="An agent that self-heals from transient tool failures by reflecting and retrying.",
    model_name=os.getenv("MODEL_AGENT_NAME", DEFAULT_MODEL_AGENT_NAME),
    instruction=(
        "You are a helpful assistant. "
        "When the user asks about the weather, call the `flaky_weather` tool. "
        "If a tool call fails, read the error guidance and retry the call. "
        "Note: respond in the same language the user uses."
    ),
    tools=[flaky_weather],
)

root_agent = agent

# App 级别配置工具失败自愈（Reflect and Retry）。
# 工具调用抛错时，ReflectAndRetryToolPlugin 会拦截异常，把结构化的错误信息
# 和反思引导反馈给模型，并允许模型重新发起调用，最多重试 max_retries 次。
app = App(
    name="reflect_retry",
    root_agent=root_agent,
    plugins=[
        ReflectAndRetryToolPlugin(
            max_retries=3,  # 同一工具连续失败超过 3 次才最终放弃
        )
    ],
)

# 注意：这里必须把带 plugins 的 `app` 传给 `app=` 参数，
# 而不是传裸 `agent`。否则 App 上的插件不会被加载，失败重试不会生效。
agent_server_app = AgentkitAgentServerApp(
    app=app,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
