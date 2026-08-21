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

from __future__ import annotations

import os
from pathlib import Path

from veadk import Agent
from veadk.tools.builtin_tools.remote_skills import (
    build_remote_skill_tools,
    load_remote_skill_definitions,
)


MANIFEST_PATH = Path(
    os.getenv("REMOTE_SKILLS_MANIFEST", Path(__file__).with_name("remote_skills.json"))
)

remote_skill_definitions = load_remote_skill_definitions(MANIFEST_PATH)
remote_skill_tools = build_remote_skill_tools(remote_skill_definitions)

root_agent = Agent(
    name="remote_skills_proxy_agent",
    description="An agent that calls protected RemoteSkills through Skills Sandbox A2A.",
    model_name=os.getenv("MODEL_AGENT_NAME", "deepseek-v4-pro-260425"),
    instruction=(
        "Use the available RemoteSkills when they match the user's task. "
        "You can see only each RemoteSkill description and input schema; "
        "the actual implementation runs in the remote Skills Sandbox."
    ),
    tools=remote_skill_tools,
)


if __name__ == "__main__":
    from agentkit.apps import AgentkitAgentServerApp
    from veadk.memory.short_term_memory import ShortTermMemory

    agent_server_app = AgentkitAgentServerApp(
        agent=root_agent,
        short_term_memory=ShortTermMemory(backend="local"),
    )
    agent_server_app.run(host="0.0.0.0", port=8000)
