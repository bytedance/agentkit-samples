"""插件 HTTP 入口。启动命令：python plugin_server.py。"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated

import httpx
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

from agent_runtime import fetch_agent_card, open_agent_response, runtime_client
from plugin_models import PluginReply, PluginRequest
from plugin_response import SSE_CONTENT_TYPE, json_reply, streaming_reply


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with runtime_client() as client:
        app.state.upstream = client
        yield


app = FastAPI(title="AgentKit Plugin Server", lifespan=lifespan)
SSE = {200: {"content": {SSE_CONTENT_TYPE: {}}}}


@app.get("/.well-known/agentcard.json")
async def agent_card(request: Request) -> dict:
    return await fetch_agent_card(request.app.state.upstream)


@dataclass
class AgentCall:
    response: httpx.Response
    streaming: bool


async def call_agent(body: PluginRequest, request: Request) -> AsyncIterator[AgentCall]:
    path = request.scope["route"].path
    streaming = body.streaming if body.streaming is not None else path == "/run_sse"
    if path == "/run" and streaming:
        raise HTTPException(422, "流式请求请使用 /、/invoke 或 /run_sse")

    endpoint = path.lstrip("/")
    if path == "/":
        endpoint = "run_sse" if streaming else "invoke"

    # 依赖的生命周期覆盖整个响应，流式客户端断开时也会释放上游连接。
    async with open_agent_response(
        request.app.state.upstream, endpoint, body
    ) as response:
        yield AgentCall(response, streaming)


@app.post("/", response_model=PluginReply, responses=SSE)
@app.post("/invoke", response_model=PluginReply, responses=SSE)
@app.post("/run", response_model=PluginReply)
@app.post("/run_sse", response_model=PluginReply, responses=SSE)
async def chat(
    call: Annotated[AgentCall, Depends(call_agent)],
) -> PluginReply | StreamingResponse:
    if call.streaming:
        return streaming_reply(call.response)
    return await json_reply(call.response)


if __name__ == "__main__":
    uvicorn.run(
        app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000"))
    )
