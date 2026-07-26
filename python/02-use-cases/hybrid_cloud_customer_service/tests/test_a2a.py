"""Protocol and configuration tests for the independently deployed A2A Agent."""

from __future__ import annotations

import asyncio

import httpx
import pytest

pytest.importorskip("a2a", reason="A2A runtime tests require a2a-sdk")

from fastapi.testclient import TestClient

from a2a_client import (
    REQUIRED_A2A_SKILL,
    _derive_card_url,
    _text_values,
    a2a_data_agent_config,
    delegate_complaint_trend_analysis,
)
from a2a_data_agent import app
from scripts.verify_a2a import response_contains_a2a_confirmation


def test_agent_card_advertises_standard_rpc_and_skill() -> None:
    client = TestClient(app)

    response = client.get("/.well-known/agent-card.json")

    assert response.status_code == 200
    card = response.json()
    assert card["url"].endswith("/a2a")
    assert {skill["id"] for skill in card["skills"]} == {REQUIRED_A2A_SKILL}


def test_health_reports_model_presence_without_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_AGENT_NAME", "test-model")
    monkeypatch.setenv("MODEL_AGENT_API_BASE", "https://model.example/v1")
    monkeypatch.setenv("MODEL_AGENT_API_KEY", "must-not-leak")
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["model_configured"] is True
    assert "must-not-leak" not in response.text


def test_message_send_returns_complaint_analysis_artifact() -> None:
    client = TestClient(app)
    response = client.post(
        "/a2a",
        json={
            "jsonrpc": "2.0",
            "id": "a2a-test-001",
            "method": "message/send",
            "params": {
                "message": {
                    "kind": "message",
                    "messageId": "message-a2a-test-001",
                    "role": "user",
                    "parts": [{"kind": "text", "text": "分析过去一年的投诉趋势并预测下季度"}],
                },
                "configuration": {"blocking": True},
            },
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["artifacts"][0]["name"] == REQUIRED_A2A_SKILL
    assert "全年 583" in "\n".join(_text_values(result))
    assert "已由 A2A 数据分析 Agent 完成" in "\n".join(_text_values(result))


def test_main_runtime_a2a_configuration_uses_rpc_and_card_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("A2A_DATA_AGENT_URL", "https://data-agent.example.test/runtime/a2a")
    monkeypatch.delenv("A2A_DATA_AGENT_CARD_URL", raising=False)
    monkeypatch.setenv("A2A_DATA_AGENT_API_KEY", "test-key")

    config = a2a_data_agent_config()

    assert config is not None
    assert config.rpc_url == "https://data-agent.example.test/runtime/a2a"
    assert config.card_url == (
        "https://data-agent.example.test/runtime/.well-known/agent-card.json"
    )
    assert _derive_card_url(config.rpc_url) == config.card_url


def test_a2a_confirmation_requires_remote_result_not_only_the_canary() -> None:
    code = "A2A_CANARY_test123"

    assert not response_contains_a2a_confirmation(code, code)
    assert response_contains_a2a_confirmation(
        "A2A 委派分析结果：hybrid-cloud-complaint-data-agent 已由 A2A 数据分析 Agent 完成。"
        f"{code}",
        code,
    )


def test_delegation_failure_is_returned_as_a_tool_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("A2A_DATA_AGENT_URL", "https://data-agent.example.test/a2a")

    class FailingAsyncClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> "FailingAsyncClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get(self, url: str, **_: object) -> object:
            request = httpx.Request("GET", url)
            raise httpx.ConnectError("unreachable", request=request)

    monkeypatch.setattr("a2a_client.httpx.AsyncClient", FailingAsyncClient)

    result = asyncio.run(delegate_complaint_trend_analysis("分析投诉趋势"))

    assert result.startswith("A2A 委派失败：")
    assert "Card discovery failed" in result
