"""A separately deployable, standards-based A2A complaint-analysis Agent.

Deploy this module with ``AGENT_APP_MODE=a2a_data_analyst``.  Its public
``/.well-known/agent-card.json`` is the record registered in AgentKit's A2A
center; ``/a2a`` accepts the A2A JSON-RPC ``message/send`` method.

The card identity and advertised Skill are deployment configuration, not an
A2A-center global constant. The demo implementation uses a stable, desensitized
dataset so protocol verification remains repeatable; the Runtime still receives
its own model configuration for later model-backed analysis extensions.
"""

from __future__ import annotations

import os
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Part,
    TextPart,
)
from fastapi import FastAPI

from tools.analysis import complaint_trend


AGENT_NAME = os.getenv("A2A_AGENT_NAME", "hybrid-cloud-complaint-data-agent")
SKILL_ID = os.getenv("A2A_AGENT_SKILL_ID", "complaint-trend-analysis")


def _model_configured() -> bool:
    """Report presence only; never expose model credentials."""
    return all(
        os.getenv(key)
        for key in (
            "MODEL_AGENT_NAME",
            "MODEL_AGENT_API_BASE",
            "MODEL_AGENT_API_KEY",
        )
    )


def _public_rpc_url() -> str:
    """Return the URL published in the Agent Card, never a credential URL."""
    configured = os.getenv("A2A_PUBLIC_URL", "").strip().rstrip("/")
    if configured:
        return configured if configured.endswith("/a2a") else f"{configured}/a2a"
    return "http://localhost:8000/a2a"


def _analysis_text(request: str) -> str:
    result = complaint_trend()
    quarterly = result["quarterly"]
    total = sum(quarterly.values())
    return (
        "已由 A2A 数据分析 Agent 完成投诉趋势分析。\n\n"
        f"请求：{request}\n"
        f"季度投诉量：Q1 {quarterly['Q1']}、Q2 {quarterly['Q2']}、"
        f"Q3 {quarterly['Q3']}、Q4 {quarterly['Q4']}（全年 {total}）。\n"
        f"主要主题：{'、'.join(result['top_topics'])}；"
        f"预测下季度投诉指数：{result['next_quarter_forecast']}。\n"
        "说明：结果来自本 Demo 的脱敏样例数据，仅用于验证 A2A 委派链路。"
    )


class ComplaintTrendAgentExecutor(AgentExecutor):
    """Minimal A2A executor that returns an artifact and final message."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id = context.task_id or str(uuid4())
        context_id = context.context_id or str(uuid4())
        updater = TaskUpdater(event_queue, task_id=task_id, context_id=context_id)
        await updater.start_work()

        answer = _analysis_text(context.get_user_input())
        await updater.add_artifact(
            parts=[Part(root=TextPart(text=answer))],
            name=SKILL_ID,
            metadata={"agent": AGENT_NAME},
        )
        await updater.complete(updater.new_agent_message(parts=[Part(root=TextPart(text=answer))]))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(
            event_queue,
            task_id=context.task_id or str(uuid4()),
            context_id=context.context_id or str(uuid4()),
        )
        await updater.cancel()


def build_app() -> FastAPI:
    card = AgentCard(
        name=AGENT_NAME,
        description="A2A data agent that analyses desensitized customer-service complaint trends.",
        url=_public_rpc_url(),
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            AgentSkill(
                id=SKILL_ID,
                name="投诉趋势分析",
                description="分析脱敏投诉趋势并给出下季度指数预测。",
                tags=["customer-service", "complaints", "analytics"],
                examples=["分析过去一年的投诉趋势并预测下季度"],
            )
        ],
    )
    app = FastAPI(title="Hybrid Cloud A2A Complaint Data Agent")
    app.get("/health")(
        lambda: {
            "status": "ok",
            "agent": card.name,
            "model_configured": _model_configured(),
        }
    )
    app.get("/v1/ping")(lambda: {"status": "ok"})

    handler = DefaultRequestHandler(
        agent_executor=ComplaintTrendAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    A2AStarletteApplication(agent_card=card, http_handler=handler).add_routes_to_app(
        app,
        agent_card_url="/.well-known/agent-card.json",
        rpc_url="/a2a",
    )
    return app


app = build_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
