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
from veadk.config import getenv

from app.storyboard.hook import hook_for_callback
from app.storyboard.schema import (
    max_output_tokens_config,
)

from app.storyboard.prompt import PROMPT_STORYBOARD_AGENT


def get_storyboard_agent():
    # `enable_responses=True` makes VeADK build an ArkLlm (Ark Responses API)
    # model for this agent.
    storyboard_agent = Agent(
        name="storyboard_agent",
        enable_responses=True,
        description="Generate the storyboard script from the video configuration script",
        instruction=PROMPT_STORYBOARD_AGENT,
        generate_content_config=max_output_tokens_config,
        before_model_callback=[hook_for_callback],
        model_extra_config={
            "extra_body": {
                "thinking": {"type": getenv("THINKING_STORYBOARD_AGENT", "disabled")},
                "caching": {
                    "type": "disabled",
                },
            }
        },
    )
    return storyboard_agent
