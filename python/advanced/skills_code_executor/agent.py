# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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
from pathlib import Path as _Path

from google.adk.code_executors import UnsafeLocalCodeExecutor
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset
from veadk import Agent


SKILL_DIR = _Path(__file__).parent / "skills" / "algorithmic-art"

skills_agent = SkillToolset(
    skills=[
        load_skill_from_dir(SKILL_DIR),
    ],
    code_executor=UnsafeLocalCodeExecutor(),
)

root_agent = Agent(
    name="skills_code_executor_agent",
    description="An agent that loads a local skill and executes its bundled scripts.",
    model_name=os.getenv("MODEL_AGENT_NAME", "deepseek-v4-pro-260425"),
    instruction=(
        "Use the available skills to complete the user's request. "
        "Load the relevant skill instructions before following them. "
        "Only run scripts bundled with the trusted local skill."
    ),
    tools=[skills_agent],
)


if __name__ == "__main__":
    from agentkit.apps import AgentkitAgentServerApp
    from veadk.memory.short_term_memory import ShortTermMemory

    agent_server_app = AgentkitAgentServerApp(
        agent=root_agent,
        short_term_memory=ShortTermMemory(backend="local"),
    )
    agent_server_app.run(host="0.0.0.0", port=8000)
