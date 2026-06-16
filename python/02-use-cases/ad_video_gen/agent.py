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
import sys
from pathlib import Path

from agentkit.apps import AgentkitAgentServerApp
from google.genai import types
from veadk import Agent
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.tools.builtin_tools.image_generate import image_generate
from veadk.tools.builtin_tools.video_generate import video_generate

sys.path.append(str(Path(__file__).resolve().parent))

from prompt import PROMPT_AD_VIDEO_AGENT


root_agent = Agent(
    name="root_agent",
    model_name=os.getenv("MODEL_AGENT_NAME", "deepseek-v4-pro-260425"),
    description="Generate ecommerce product marketing images and short videos.",
    instruction=PROMPT_AD_VIDEO_AGENT,
    tools=[
        image_generate,
        video_generate,
    ],
    generate_content_config=types.GenerateContentConfig(max_output_tokens=18000),
)


short_term_memory = ShortTermMemory(backend="local")

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)


if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
