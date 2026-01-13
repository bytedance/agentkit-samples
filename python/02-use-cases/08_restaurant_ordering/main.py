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

import asyncio
import time

import agent
from google.adk.runners import InMemoryRunner
from google.adk.sessions.session import Session
from google.genai import types


async def main():
    app_name = "my_app"
    user_id_1 = "user1"
    runner = InMemoryRunner(
        agent=agent.root_agent,
        app_name=app_name,
    )
    session_11 = await runner.session_service.create_session(
        app_name=app_name, user_id=user_id_1
    )

    async def run_prompt(session: Session, new_message: str):
        content = types.Content(
            role="user", parts=[types.Part.from_text(text=new_message)]
        )
        print("** User says:", content.model_dump(exclude_none=True))
        async for event in runner.run_async(
            user_id=user_id_1,
            session_id=session.id,
            new_message=content,
        ):
            if event.content.parts and event.content.parts[0].text:
                print(f"** {event.author}: {event.content.parts[0].text}")

    start_time = time.time()
    print("Start time:", start_time)
    print("------------------------------------")
    prompts = [
        "你好，我想吃点辣的。",
        "你们有螃蟹做的菜吗？",
        "听起来不错，就按你说的做一份吧。",
        "再来一份宫保鸡丁。",
        "我点完了，结账。",
    ]
    for prompt in prompts:
        await run_prompt(session_11, prompt)
    end_time = time.time()
    print("------------------------------------")
    print("End time:", end_time)
    print("Total time:", end_time - start_time)


if __name__ == "__main__":
    asyncio.run(main())
