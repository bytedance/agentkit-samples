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
from typing import Literal

from veadk import Agent

from app.eval.hook import hook_url_id_mapping
from app.eval.prompt import PROMPT_EVALUATE_AGENT
from app.eval.tools.geval import evaluate_media


def get_eval_agent(eval_type: Literal["image", "video"]):
    # `enable_responses=True` makes VeADK build an ArkLlm (Ark Responses API)
    # model for this agent.
    eval_agent = Agent(
        name=f"{eval_type}_evaluate_agent",
        enable_responses=True,
        description="Evaluate the quality of shot images or shot videos",
        instruction=PROMPT_EVALUATE_AGENT,
        after_tool_callback=[hook_url_id_mapping],
        tools=[evaluate_media],
        model_extra_config={
            "extra_body": {
                "thinking": {"type": os.getenv("THINKING_EVALUATE_AGENT", "disabled")},
                "caching": {
                    "type": "disabled",
                },
            }
        },
    )
    return eval_agent
