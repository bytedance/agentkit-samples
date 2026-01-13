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

from veadk import Agent
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.tools.builtin_tools.run_code import run_code
from veadk.tools.builtin_tools.web_search import web_search
from agentkit.apps import AgentkitAgentServerApp

short_term_memory = ShortTermMemory(backend="local")

agent = Agent(
    name="data_analysis_agent",
    description="A data analysis for stock marketing",
    instruction="""
    You are a data analysis agent for stock marketing.
    Talk with user friendly. You can invoke your tools to finish user's task or question.
    Load memory first. In case you already have answer from memory, you can use it directly.
    Download the stock data thru sandbox if it is not available in memory.
    * If trading data is not found, download the stock trading data using run_code. You can use the Python library akshare to download relevant stock data.
    * After downloading, execute code through run_code to avoid installation checks each time.
    * You can use the web_search tool to search for relevant company operational data.
    * If dependency libraries are missing, install them for the sandbox using Python code.
    """,
    tools=[run_code, web_search],
)

root_agent = agent

agent_server_app = AgentkitAgentServerApp(
    agent=agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
