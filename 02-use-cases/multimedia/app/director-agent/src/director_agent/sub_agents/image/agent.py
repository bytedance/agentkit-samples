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
from veadk.agents.sequential_agent import SequentialAgent

from director_agent.hook.check_and_raise import raise_result_error
from director_agent.hook.shorten_url import hook_shorten_url
from director_agent.tools.image_generate_gather import image_generate
from director_agent.hook.format_hook import fix_output_format
from director_agent.utils.types import (
    json_response_config,
    ImageList,
    max_output_tokens_config,
)
from veadk.config import getenv
from director_agent.prompt import PROMPT_IMAGE_AGENT, PROMPT_IMAGE_FORMAT_AGENT

image_generate_agent = Agent(
    name="image_generate_agent",
    description="根据分镜脚本，为分镜生成图片",
    instruction=PROMPT_IMAGE_AGENT,
    tools=[image_generate],
    after_tool_callback=[raise_result_error, hook_shorten_url],
    generate_content_config=max_output_tokens_config,
    model_extra_config={
        "extra_body": {"thinking": {"type": getenv("THINKING_IMAGE_AGENT", "enabled")}}
    },
)

image_format_agent = Agent(
    name="image_format_agent",
    model_name=getenv("MODEL_FORMAT_NAME"),
    description="将模型的输出格式化",
    instruction=PROMPT_IMAGE_FORMAT_AGENT,
    generate_content_config=json_response_config,
    after_model_callback=[fix_output_format],
    output_schema=ImageList,
    output_key="image_list",
    model_extra_config={
        "extra_body": {
            "thinking": {"type": getenv("THINKING_IMAGE_FORMAT_AGENT", "disabled")}
        }
    },
)

image_agent = SequentialAgent(
    name="image_sequential_agent",
    description="根据分镜脚本，为分镜生成图片",
    sub_agents=[image_generate_agent, image_format_agent],
)
