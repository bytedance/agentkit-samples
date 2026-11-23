"""对外提供 HTTP 和 JSON-RPC 两个入口，交给 a2a_tool 调用远端 Agent。"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from a2a.client.helpers import create_text_message_object
from a2a.server.apps import A2AStarletteApplication
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    MessageSendConfiguration,
    MessageSendParams,
)
from a2a.utils.errors import ServerError
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from a2a_tool import A2ATool, UpstreamTimeoutError


load_dotenv(Path(__file__).with_name(".env"))

HTTP_PATH = "/HiAgent_a2a_http"
A2A_PATH = "/HiAgent_a2a_client"


class HttpMessage(BaseModel):
    prompt: str = Field(min_length=1)
    context_id: str | None = Field(default=None, min_length=1)
    task_id: str | None = Field(default=None, min_length=1)

    @field_validator("prompt")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt must contain text")
        return value


def create_app(*, card_path=None, public_base_url=None, http_transport=None):
    # 两个入口共用一个远端客户端。
    tool = A2ATool(card_path=card_path, http_transport=http_transport)
    public_base_url = public_base_url or os.getenv(
        "PUBLIC_BASE_URL", f"http://127.0.0.1:{os.getenv('PORT', '8000')}"
    )
    public_card = AgentCard(
        name="HiAgent A2A Proxy",
        description="Direct access to the configured remote HiAgent through A2A.",
        url=f"{public_base_url.rstrip('/')}{A2A_PATH}",
        version="1.0.0",
        preferred_transport="JSONRPC",
        capabilities=AgentCapabilities(push_notifications=False),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            AgentSkill(
                id="hiagent",
                name="HiAgent",
                tags=["a2a"],
                description="Forward messages directly to the configured remote agent.",
            )
        ],
    )

    @asynccontextmanager
    async def lifespan(app):
        # 服务启动时连接客户端，退出时关闭连接池。
        async with tool:
            remote_card = tool.remote_card
            public_card.capabilities.streaming = remote_card.capabilities.streaming
            public_card.capabilities.state_transition_history = (
                remote_card.capabilities.state_transition_history
            )
            public_card.capabilities.extensions = remote_card.capabilities.extensions
            public_card.default_input_modes = remote_card.default_input_modes
            public_card.default_output_modes = remote_card.default_output_modes
            yield

    app = FastAPI(title="HiAgent A2A Client Gateway", lifespan=lifespan)

    @app.get("/ping")
    async def ping():
        return {"status": "ok"}

    @app.post(HTTP_PATH)
    async def invoke(body: HttpMessage):
        """普通 HTTP：把 prompt 转成 A2A 消息，返回远端结果。"""
        message = create_text_message_object(content=body.prompt)
        message.context_id = body.context_id
        message.task_id = body.task_id
        try:
            result = await tool.on_message_send(
                MessageSendParams(
                    message=message,
                    configuration=MessageSendConfiguration(blocking=True),
                )
            )
        except ServerError as exc:
            status = 504 if isinstance(exc, UpstreamTimeoutError) else 502
            raise HTTPException(
                status_code=status, detail=exc.error.model_dump(exclude_none=True)
            ) from None
        return result.model_dump(mode="json", by_alias=True, exclude_none=True)

    # 标准 A2A：JSON-RPC 解析和 SSE 格式交给 SDK。
    a2a_app = A2AStarletteApplication(agent_card=public_card, http_handler=tool)
    a2a_app.add_routes_to_app(app, rpc_url=A2A_PATH)

    @app.get(f"{A2A_PATH}/.well-known/agent-card.json")
    async def agent_card():
        return public_card.model_dump(mode="json", by_alias=True, exclude_none=True)

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000"))
    )
