import os
from pathlib import Path

import httpx
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.runners import InMemoryRunner
from google.genai.types import UserContent

AGENT_CARD = str(Path(__file__).with_name("remote_agentcard.json"))


async def call_remote_agent(message: str) -> str:
    if not message.strip():
        raise ValueError("消息不能为空。")

    key = os.environ["AGENTKIT_RUNTIME_API_KEY"]
    headers = {"Authorization": f"Bearer {key}"}
    client = httpx.AsyncClient(headers=headers, timeout=60)
    agent = RemoteA2aAgent(
        name="remote_agent", agent_card=AGENT_CARD, httpx_client=client
    )

    async with client, InMemoryRunner(agent=agent) as runner:
        return await _send_message(runner, message)


async def _send_message(runner: InMemoryRunner, message: str) -> str:
    session = await runner.session_service.create_session(
        app_name=runner.app_name, user_id="mcp_user"
    )
    events = runner.run_async(
        user_id=session.user_id,
        session_id=session.id,
        new_message=UserContent(parts=message),
    )

    reply = ""
    async for event in events:
        if event.error_message:
            raise RuntimeError(event.error_message)
        if not event.is_final_response() or not event.content:
            continue

        parts = event.content.parts or []
        reply = "".join(p.text for p in parts if p.text and not p.thought)

    if not reply:
        raise RuntimeError("远程 Agent 未返回文本回复。")
    return reply
