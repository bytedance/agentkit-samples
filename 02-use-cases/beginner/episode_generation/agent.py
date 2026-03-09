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

import uuid

from agentkit.apps import AgentkitAgentServerApp
from veadk import Agent
from veadk.memory import ShortTermMemory
from veadk.runner import Runner
from veadk.tools.builtin_tools.image_generate import image_generate
from veadk.tools.builtin_tools.video_generate import video_generate
from veadk.tools.builtin_tools.web_search import web_search

# video_generator = Agent(
#     name="video_generator",
#     description="视频生成 Agent",
#     instruction="你是一个原子化的 Agent，具备视频生成能力，每次执行完毕后，考虑回到主 Agent。",
#     tools=[video_generate],
# )

# image_generator = Agent(
#     name="image_generator",
#     description="图像生成 Agent",
#     instruction="你是一个原子化的 Agent，具备图像生成能力，每次执行完毕后，考虑回到主 Agent。",
#     tools=[image_generate],
# )

root_agent = Agent(
    name="image_video_tools_agent",
    description="调用 tools 生成图片或者视频",
    instruction="""
    你是一个生图生视频助手，具备图像生成和视频生成能力。有三个可用的工具：
    - web_search：用于搜索相关信息。
    - image_generate：用于生成图像。
    - video_generate：用于生成视频。

    ### 工作流程：

    1. 当用户提供输入时，根据用户输入，准备相关背景信息：
       - 若用户输入为故事或情节，直接调用 web_search 工具；
       - 若用户输入为其他类型（如问题、请求），则先调用 web_search 工具 (最多调用2次)，找到合适的信息。
    2. 根据准备好的背景信息，调用 image_generate 工具生成分镜图片。生成后，以 Markdown 图片列表形式返回，例如：
        ```
        ![分镜图片1](https://example.com/image1.png)
        ```
    3. 根据用户输入，判断是否需要调用 video_generate 工具生成视频。返回视频 URL 时，使用 Markdown 视频链接列表，例如：
        ```
        <video src="https://example.com/video1.mp4" width="640" controls>分镜视频1</video>
        ```
    
    ### 注意事项：
    - 输入输出中，任何涉及图片或视频的链接url，**绝对禁止任何形式的修改、截断、拼接或替换**，必须100%保持原始内容的完整性与准确性。        
    """,
    # sub_agents=[image_generator, video_generator],
    tools=[web_search, image_generate, video_generate],
)
runner = Runner(agent=root_agent)


async def main(prompts: list[str]):
    session_id = uuid.uuid4().hex
    for prompt in prompts:
        response = await runner.run(
            messages=prompt,
            session_id=session_id,
        )
        print(response)


short_term_memory = ShortTermMemory(backend="local")

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
