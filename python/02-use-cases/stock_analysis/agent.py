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
import datetime
import os
from tzlocal import get_localzone

from veadk import Agent
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.tools.builtin_tools.run_code import run_code
from veadk.tools.builtin_tools.web_search import web_search
from agentkit.apps import AgentkitAgentServerApp

short_term_memory = ShortTermMemory(backend="local")
MODEL_AGENT_NAME = "MODEL_AGENT_NAME"
DEFAULT_MODEL_AGENT_NAME = "deepseek-v4-pro-260425"
model_name = os.getenv(MODEL_AGENT_NAME, DEFAULT_MODEL_AGENT_NAME)
AKSHARE_VERSION = "1.18.88"
AKSHARE_INDEX_URL = "https://mirrors.ivolces.com/pypi/simple/"


def get_current_time() -> str:
    """Get the current server time."""
    local_tz = get_localzone()
    current_time_obj = datetime.datetime.now(local_tz)
    return current_time_obj.strftime("%Y-%m-%d %H:%M:%S %z")


agent = Agent(
    name="data_analysis_agent",
    description="A data analysis for stock marketing",
    instruction=f"""
    You are a data analysis agent for stock marketing.
    Talk with user friendly. You can invoke your tools to finish user's task or question.
    If the user's request contains words like "recently", "lately", "latest" or with similar meanings,
    you need to first obtain the current time using get_current_time tool, in order to understand what the user considers as time.
    Load memory first. In case you already have answer from memory, you can use it directly.
    Download the stock data thru sandbox if it is not available in memory.
    * If trading data is not found, download the stock trading data using run_code. You can use the Python library akshare to download relevant stock data.
    * After downloading, execute code through run_code to avoid installation checks each time.
    * You can use the web_search tool to search for relevant company operational data.
    * If akshare is missing, install exactly akshare=={AKSHARE_VERSION} from {AKSHARE_INDEX_URL}.
    * Install it inside run_code's Python kernel. Use sys.executable with subprocess; do not use a shell command or a bare pip executable because the shell and run_code Python environments are different.
    * Use this installation pattern:
      import importlib.util
      import subprocess
      import sys
      if importlib.util.find_spec("akshare") is None:
          subprocess.run(
              [
                  sys.executable,
                  "-m",
                  "pip",
                  "install",
                  "--user",
                  "--prefer-binary",
                  "--disable-pip-version-check",
                  "--progress-bar",
                  "off",
                  "--index-url",
                  "{AKSHARE_INDEX_URL}",
                  "akshare=={AKSHARE_VERSION}",
              ],
              check=True,
              timeout=25,
          )
    Note: If a user asks a question in a certain language, you should respond in the same language as well.""",
    tools=[get_current_time, run_code, web_search],
    model_name=model_name,
)

root_agent = agent

agent_server_app = AgentkitAgentServerApp(
    agent=agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
