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

from release_agent.hook.format_hook import fix_output_format

# from release_agent.tools.video_combine import video_combine
from release_agent.tools.video_combine import video_combine
from release_agent.utils.types import (
    max_output_tokens_config,
    VideoUrl,
    json_response_config,
)
from veadk.config import getenv
from release_agent.prompt import PROMPT_FILM_AGENT, PROMPT_FORMAT_AGENT

film_generate_agent = Agent(
    name="film_generate_agent",
    description="将所有分镜的视频合成最终的视频",
    instruction=PROMPT_FILM_AGENT,
    tools=[video_combine],
    generate_content_config=max_output_tokens_config,
    model_extra_config={
        "extra_body": {"thinking": {"type": getenv("THINKING_FILM_AGENT", "enabled")}}
    },
)

format_agent = Agent(
    name="format_agent",
    model_name=getenv("MODEL_FORMAT_NAME"),
    description="将模型的输出格式化",
    instruction=PROMPT_FORMAT_AGENT,
    generate_content_config=json_response_config,
    output_schema=VideoUrl,
    output_key="video_url",
    after_model_callback=[fix_output_format],
    model_extra_config={
        "extra_body": {
            "thinking": {"type": getenv("THINKING_FORMAT_AGENT", "disabled")}
        }
    },
)

film_agent = SequentialAgent(
    name="film_agent",
    description="将所有分镜的视频合成最终的视频",
    sub_agents=[film_generate_agent, format_agent],
)
