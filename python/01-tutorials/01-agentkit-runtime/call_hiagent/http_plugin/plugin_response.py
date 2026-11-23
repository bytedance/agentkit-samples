"""将 AgentKit 回复转换为插件客户端使用的 JSON 或 SSE。"""

import json
from collections.abc import AsyncIterator
from typing import Literal

import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from agent_runtime import agent_events
from plugin_models import PluginReply


SSE_CONTENT_TYPE = "text/event-stream"


async def reply_text(
    response: httpx.Response, *, streaming: bool = False
) -> AsyncIterator[tuple[Literal["chunk", "final"], str]]:
    """依次给出可见文本片段，最后给出完整回复。"""
    partial_text = ""
    final_text = ""
    error_fields = ("error", "errorCode", "errorMessage", "error_code", "error_message")
    async for event in agent_events(response):
        if any(event.get(field) for field in error_fields):
            raise HTTPException(502, "上游 Agent 执行失败")

        content = event.get("content") or {}
        if event.get("author") == "user" or content.get("role") == "user":
            continue
        text = "".join(
            part["text"]
            for part in content.get("parts") or []
            if part.get("text") and not part.get("thought")
        )
        if not text:
            continue
        if event.get("partial"):
            partial_text += text
            yield "chunk", text
            continue

        # 上游可能在增量之后重发完整文本，只补发未输出的后缀。
        if text.startswith(partial_text):
            suffix = text[len(partial_text) :]
            if suffix:
                yield "chunk", suffix
        elif streaming:
            raise HTTPException(502, "上游修改了已经发送的文本，流式回复未完成")
        final_text = text
        partial_text = ""

    message = partial_text or final_text
    if not message:
        raise HTTPException(502, "上游 Agent 未返回文本回复")
    yield "final", message


async def json_reply(response: httpx.Response) -> PluginReply:
    async for kind, text in reply_text(response):
        if kind == "final":
            return PluginReply(output=text)
    raise HTTPException(502, "上游 Agent 未返回文本回复")


def json_frame(event: str, data: dict[str, str]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def sse_frames(response: httpx.Response) -> AsyncIterator[str]:
    try:
        async for kind, text in reply_text(response, streaming=True):
            if kind == "chunk":
                yield json_frame("message", {"content": text})
        yield "event: close\ndata: closed\n\n"
    except (
        HTTPException,
        httpx.RequestError,
        ValueError,
        TypeError,
        AttributeError,
    ) as exc:
        detail = (
            exc.detail if isinstance(exc, HTTPException) else "上游响应中断或格式无效"
        )
        yield json_frame("error", {"error_msg": detail})


def streaming_reply(response: httpx.Response) -> StreamingResponse:
    # 显式设置 Content-Type，防止框架为 text/* 自动附加 charset。
    return StreamingResponse(
        sse_frames(response),
        headers={
            "Content-Type": SSE_CONTENT_TYPE,
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
