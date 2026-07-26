"""Customer-service Runtime client for an independently deployed A2A Agent."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx


DEFAULT_A2A_SKILL = "complaint-trend-analysis"
# Backward-compatible public constant for integrations that use the Demo's
# default contract. Runtime selection itself uses A2A_DATA_AGENT_SKILL_ID.
REQUIRED_A2A_SKILL = DEFAULT_A2A_SKILL
logger = logging.getLogger(__name__)


class A2ADelegationError(RuntimeError):
    """A remote A2A Agent was unavailable or did not honour its contract."""


@dataclass(frozen=True)
class A2ADataAgentConfig:
    rpc_url: str
    card_url: str
    api_key: str
    timeout_seconds: float
    skill_id: str
    expected_agent_name: str


def _derive_card_url(rpc_url: str) -> str:
    base, _, _ = rpc_url.rstrip("/").rpartition("/")
    return f"{base}/.well-known/agent-card.json" if base else ""


def a2a_data_agent_config() -> A2ADataAgentConfig | None:
    """Read the remote delegate configuration injected into this Runtime.

    ``A2A_DATA_AGENT_URL`` is the target Agent's public *RPC* endpoint, for
    example ``https://.../a2a``.  The caller configures the API key in Runtime
    environment variables; it is never returned to the model or browser UI.
    """
    rpc_url = os.getenv("A2A_DATA_AGENT_URL", "").strip().rstrip("/")
    if not rpc_url:
        return None
    card_url = os.getenv("A2A_DATA_AGENT_CARD_URL", "").strip() or _derive_card_url(rpc_url)
    return A2ADataAgentConfig(
        rpc_url=rpc_url,
        card_url=card_url,
        api_key=os.getenv("A2A_DATA_AGENT_API_KEY", "").strip(),
        timeout_seconds=float(os.getenv("A2A_DATA_AGENT_TIMEOUT_SECONDS", "30")),
        skill_id=os.getenv("A2A_DATA_AGENT_SKILL_ID", DEFAULT_A2A_SKILL).strip(),
        expected_agent_name=os.getenv("A2A_DATA_AGENT_NAME", "").strip(),
    )


def a2a_data_agent_configured() -> bool:
    return a2a_data_agent_config() is not None


def _headers(config: A2ADataAgentConfig) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    return headers


def _text_values(value: Any) -> list[str]:
    """Extract only textual artifact/message fields from a standard response."""
    if isinstance(value, dict):
        text = value.get("text")
        values = [text] if isinstance(text, str) and text.strip() else []
        for key in ("artifacts", "parts", "message", "status"):
            if key in value:
                values.extend(_text_values(value[key]))
        return values
    if isinstance(value, list):
        values: list[str] = []
        for item in value:
            values.extend(_text_values(item))
        return values
    return []


async def _discover(client: httpx.AsyncClient, config: A2ADataAgentConfig) -> dict[str, Any]:
    try:
        logger.info("A2A Card discovery started: url=%s", config.card_url)
        response = await client.get(config.card_url, headers=_headers(config))
        response.raise_for_status()
        card = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise A2ADelegationError(f"A2A Agent Card discovery failed: {exc}") from exc
    skill_ids = {item.get("id") for item in card.get("skills", []) if isinstance(item, dict)}
    if config.skill_id not in skill_ids:
        raise A2ADelegationError(
            f"A2A Agent Card does not advertise selected skill: {config.skill_id}"
        )
    if config.expected_agent_name and card.get("name") != config.expected_agent_name:
        raise A2ADelegationError(
            "A2A Agent Card name does not match the Agent selected from A2A Center"
        )
    logger.info(
        "A2A Card discovery succeeded: agent=%s skill=%s",
        card.get("name", "unknown"),
        config.skill_id,
    )
    return card


async def delegate_complaint_trend_analysis(request: str) -> str:
    """Discover the configured A2A Agent then delegate a trend-analysis task.

    This is intentionally a narrow tool.  It gives the main Agent an explicit,
    auditable delegation path instead of allowing arbitrary URL calls or
    pretending that a local deterministic function is a remote A2A agent.
    """
    config = a2a_data_agent_config()
    if config is None:
        return (
            "A2A data agent is not configured. Set A2A_DATA_AGENT_URL after "
            "publishing and registering the data-agent Runtime."
        )

    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "kind": "message",
                "messageId": str(uuid4()),
                "role": "user",
                "parts": [{"kind": "text", "text": request}],
            },
            "configuration": {"blocking": True},
            "metadata": {"delegated_by": "hybrid_cloud_customer_service"},
        },
    }
    try:
        # The Agent tool runs inside an async ADK invocation.  Using the sync
        # httpx client here blocks the event loop and can cause the FaaS request
        # to be cancelled before a tool result is emitted.
        async with httpx.AsyncClient(
            timeout=config.timeout_seconds, follow_redirects=True
        ) as client:
            card = await _discover(client, config)
            logger.info("A2A message/send started: url=%s", config.rpc_url)
            response = await client.post(
                config.rpc_url,
                headers={**_headers(config), "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
    except (A2ADelegationError, httpx.HTTPError, ValueError) as exc:
        # A tool must always return a result to ADK.  Re-raising here produces
        # "Missing tool results" and hides the failing stage from the model.
        logger.warning("A2A delegation failed: %s", exc)
        return f"A2A 委派失败：{exc}"

    if body.get("error"):
        logger.warning("A2A delegation rejected by remote Agent: %s", body["error"])
        return f"A2A 委派失败：对端拒绝请求：{body['error']}"
    result = body.get("result", {})
    texts = _text_values(result)
    if not texts:
        logger.warning("A2A data agent returned no text artifact")
        return "A2A 委派失败：对端未返回文本 Artifact。"
    agent_name = card.get("name", "A2A data agent")
    logger.info("A2A message/send succeeded: agent=%s", agent_name)
    return f"委派给 {agent_name} 的结果：\n" + "\n".join(dict.fromkeys(texts))
