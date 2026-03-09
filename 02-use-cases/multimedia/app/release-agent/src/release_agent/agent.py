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
from .sub_agents.film_agent.agent import film_agent
from veadk.config import getenv
from release_agent.prompt import PROMPT_RELEASE_AGENT

agent = Agent(
    name="release_agent",
    description="将分镜视频合成最终的视频",
    # instruction=getenv("PROMPT_RELEASE_AGENT"),
    instruction=PROMPT_RELEASE_AGENT,
    sub_agents=[
        film_agent,
    ],
    model_extra_config={
        "extra_body": {
            "thinking": {"type": getenv("THINKING_RELEASE_AGENT", "enabled")}
        }
    },
)

root_agent = agent
