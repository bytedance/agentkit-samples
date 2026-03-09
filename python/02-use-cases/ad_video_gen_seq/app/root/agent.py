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

from typing import override, AsyncGenerator

from google.adk.agents import InvocationContext, BaseAgent
from google.adk.agents.run_config import StreamingMode
from google.adk.events import Event
from google.genai import types
from veadk.agents.sequential_agent import SequentialAgent

from app.eval import get_eval_agent
from app.image.agent import get_image_agent
from app.market import get_market_agent
from app.release.agent import get_release_agent
from app.storyboard import get_storyboard_agent
from app.video.agent import get_video_agent


class CallBackAgent(BaseAgent):
    async def _yield_event(
        self, ctx: InvocationContext, text: str
    ) -> AsyncGenerator[Event, None]:
        if ctx.run_config.streaming_mode != StreamingMode.NONE:
            stream_event = Event(
                invocation_id=ctx.invocation_id,
                author="callback_agent",
                content=types.Content(
                    parts=[
                        types.Part(
                            text=text,
                        )
                    ],
                    role="model",
                ),
                partial=True,
            )
            yield stream_event

        event = Event(
            invocation_id=ctx.invocation_id,
            author="callback_agent",
            content=types.Content(
                parts=[
                    types.Part(
                        text=text,
                    )
                ],
                role="model",
            ),
        )
        yield event

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        cb_agent_output = ctx.session.state.get("cb_agent_output", "")
        cb_agent_state = ctx.session.state.get("cb_agent_state", "")

        if isinstance(cb_agent_output, str):
            if cb_agent_output:
                async for event in self._yield_event(ctx, cb_agent_output):
                    yield event
        elif isinstance(cb_agent_output, list):
            for output_item in cb_agent_output:
                if output_item:
                    async for event in self._yield_event(ctx, output_item):
                        yield event

        if cb_agent_state:
            async for event in self._yield_event(ctx, cb_agent_state):
                yield event


class MMSequentialAgent(SequentialAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.sub_agents:
            new_sub_agents = []
            for i, sub_agent in enumerate(self.sub_agents):
                # 间隔插入一个callback_agent
                new_sub_agents.append(sub_agent)
                new_sub_agents.append(CallBackAgent(name=f"callback_agent_{i}"))

            self.sub_agents = new_sub_agents
            pass

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        async for event in super()._run_async_impl(ctx):
            if isinstance(event, Event):
                yield event
            if ctx.session.state.get("end_invocation", False):
                break


def get_root_agent() -> MMSequentialAgent:
    import os

    os.environ["MODEL_AGENT_CACHING"] = "disabled"
    root_agent = MMSequentialAgent(
        name="root_agent",
        description="根据用户的需求，生成电商视频",
        sub_agents=[
            get_market_agent(),
            get_storyboard_agent(),
            get_image_agent(),
            get_eval_agent(eval_type="image"),
            get_video_agent(),
            get_eval_agent(eval_type="video"),
            get_release_agent(),
        ],
    )
    return root_agent
