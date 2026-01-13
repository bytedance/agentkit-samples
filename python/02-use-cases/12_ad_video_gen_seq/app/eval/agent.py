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
from app.model import ArkLlm


def get_eval_agent(eval_type: Literal["image", "video"]):
    eval_agent = Agent(
        name=f"{eval_type}_evaluate_agent",
        enable_responses=True,
        description="根据用户的需求，评估分镜图片或分镜视频的质量",
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
    eval_agent.model = ArkLlm(
        model=f"{eval_agent.model_provider}/{eval_agent.model_name}",
        api_key=eval_agent.model_api_key,
        api_base=eval_agent.model_api_base,
        **eval_agent.model_extra_config,
    )
    return eval_agent
