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

os.environ["LOGGING_LEVEL"] = "ERROR"
import time
import asyncio
from google.adk.sessions import Session
from google.adk.agents import RunConfig
from google.adk.agents.run_config import StreamingMode
from google.adk.events import Event
from google.genai import types
from veadk import Runner
from veadk.memory import ShortTermMemory

from app.root import get_root_agent


async def export_session(session_service, app_name, user_id, session_id, file_path):
    session = await session_service.get_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    if session:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(session.model_dump_json(indent=2, exclude_none=True, by_alias=True))


async def import_session(session_service, app_name, user_id, file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        loaded_session = Session.model_validate_json(f.read())

        # 创建新session并复制状态
    new_session = await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=SESSION_ID,
        state=loaded_session.state,
    )

    # Append all events
    for event in loaded_session.events:
        await session_service.append_event(new_session, event)

    return new_session


APP_NAME = "debug_app"
USER_ID = "debug_user"
SESSION_ID = "debug_session"

root_agent = get_root_agent()

short_term_memory = ShortTermMemory(
    backend="local",
)

runner = Runner(
    agent=root_agent,
    short_term_memory=short_term_memory,
    app_name=APP_NAME,
    user_id=USER_ID,
)


async def main(prompt: types.Content, stream: bool = False):
    # await import_session(runner.session_service, APP_NAME, USER_ID, "session.json")
    await short_term_memory.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )
    start_time = time.time()
    event_author = ""
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=prompt,
        run_config=RunConfig(
            streaming_mode=StreamingMode.SSE if stream else StreamingMode.NONE,
        ),
    ):
        if isinstance(event, Event):
            if event_author != event.author:
                print(f"Author: {event.author} ---------------------------------------")
                event_author = event.author
            if stream:
                if (
                    event.partial
                    and event.content.parts
                    and event.content.parts[0].text
                ):
                    print(event.content.parts[0].text, end="", flush=True)
                elif not event.partial:
                    print()
            else:
                if event.content.parts:
                    for part in event.content.parts:
                        if not part.thought and part.text:
                            print(part.text)
                            print()
    end_time = time.time()
    print(f"Execution time: {end_time - start_time} seconds")
    # await export_session(runner.session_service, APP_NAME, USER_ID, SESSION_ID, "session.json")


if __name__ == "__main__":
    prompt = "帮我生成杨梅饮料的宣传视频（商品展示视频），图片素材为：https://ark-tutorial.tos-cn-beijing.volces.com/multimedia/%E6%9D%A8%E6%A2%85%E9%A5%AE%E6%96%99.jpg 每个分镜两个首帧图，两条视频"
    request = types.Content(
        role="user",
        parts=[
            types.Part(
                text=prompt,
            )
        ],
    )
    asyncio.run(main(request, stream=False))
