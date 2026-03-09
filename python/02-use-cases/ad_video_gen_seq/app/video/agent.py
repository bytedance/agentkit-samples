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

from google.genai import types
from veadk import Agent

# from veadk.tools.builtin_tools.video_generate import video_generate
from app.video.tools.video_generate_by_code import video_generate
from app.video.hook import hook_short_image_url_to_long, hook_url_id_mapping
from app.video.prompt import PROMPT_VIDEO_AGENT
from app.model import ArkLlm

max_output_tokens_config = types.GenerateContentConfig(max_output_tokens=18000)


def get_video_agent():
    video_agent = Agent(
        name="video_agent",
        enable_responses=True,
        description="根据分镜脚本，生成分镜视频",
        instruction=PROMPT_VIDEO_AGENT,
        tools=[video_generate],
        before_tool_callback=[hook_short_image_url_to_long],
        after_tool_callback=[hook_url_id_mapping],
        generate_content_config=max_output_tokens_config,
        model_extra_config={
            "extra_body": {
                "thinking": {"type": os.getenv("THINKING_VIDEO_AGENT", "disabled")},
                "caching": {
                    "type": "disabled",
                },
            },
        },
    )
    video_agent.model = ArkLlm(
        model=f"{video_agent.model_provider}/{video_agent.model_name}",
        api_key=video_agent.model_api_key,
        api_base=video_agent.model_api_base,
        **video_agent.model_extra_config,
    )
    return video_agent
