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

from app.image.hook import hook_url_id_mapping
from app.image.schema import max_output_tokens_config
from app.image.tools.image_generate_gather import image_generate
from app.image.prompt import PROMPT_IMAGE_AGENT
from app.model import ArkLlm


def get_image_agent():
    image_agent = Agent(
        name="image_agent",
        enable_responses=True,
        description="根据分镜脚本，为分镜生成图片",
        instruction=PROMPT_IMAGE_AGENT,
        tools=[image_generate],
        after_tool_callback=[hook_url_id_mapping],  # url -> id
        generate_content_config=max_output_tokens_config,
        model_extra_config={
            "extra_body": {
                "thinking": {"type": getenv("THINKING_IMAGE_AGENT", "disabled")},
                "caching": {
                    "type": "disabled",
                },
            }
        },
    )
    image_agent.model = ArkLlm(
        model=f"{image_agent.model_provider}/{image_agent.model_name}",
        api_key=image_agent.model_api_key,
        api_base=image_agent.model_api_base,
        **image_agent.model_extra_config,
    )
    return image_agent
