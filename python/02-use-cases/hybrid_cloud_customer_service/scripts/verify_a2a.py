#!/usr/bin/env python3
"""Prove a real A2A delegation with one cross-Runtime confirmation code."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from scripts.verify_knowledge_memory import _require, check, invoke, show_response
except ModuleNotFoundError:
    from verify_knowledge_memory import _require, check, invoke, show_response


REMOTE_COMPLETION = "已由 A2A 数据分析 Agent 完成"


def expected_skill() -> str:
    return os.getenv("A2A_EXPECTED_SKILL_ID", "complaint-trend-analysis").strip()


def expected_agent_name() -> str:
    return os.getenv(
        "A2A_EXPECTED_AGENT_NAME", "hybrid-cloud-complaint-data-agent"
    ).strip()


def request_json(url: str, api_key: str, *, method: str = "GET", body: dict | None = None) -> dict:
    """Request the data Runtime without exposing its credential."""
    request = Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
        method=method,
    )
    try:
        with urlopen(request, timeout=90) as response:  # noqa: S310 - operator-supplied Runtime URL
            return json.loads(response.read().decode())
    except HTTPError as exc:
        raise RuntimeError(f"data Runtime returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"cannot reach data Runtime: {exc.reason}") from exc


def card_has_required_skill(card: dict) -> bool:
    return expected_skill() in {
        item.get("id") for item in card.get("skills", []) if isinstance(item, dict)
    }


def response_contains_a2a_confirmation(response: str, confirmation_code: str) -> bool:
    normalized = response.lower()
    return all(
        value.lower() in normalized
        for value in (
            confirmation_code,
            expected_agent_name(),
            REMOTE_COMPLETION,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show-response", action="store_true")
    args = parser.parse_args()

    main_endpoint = _require("RUNTIME_ENDPOINT")
    main_key = _require("RUNTIME_API_KEY")
    data_endpoint = _require("A2A_AGENT_ENDPOINT").rstrip("/")
    if data_endpoint.endswith("/a2a"):
        data_endpoint = data_endpoint[: -len("/a2a")]
    data_key = _require("A2A_AGENT_API_KEY")
    run_id = uuid.uuid4().hex[:8]
    confirmation_code = f"A2A_CANARY_{run_id}"
    user_id = f"a2a-verify-{run_id}"
    session_id = f"a2a-main-{run_id}"

    card = request_json(f"{data_endpoint}/.well-known/agent-card.json", data_key)
    card_ok = check(
        "data AgentCard",
        card.get("name") == expected_agent_name() and card_has_required_skill(card),
        "the A2A Center-selected Agent advertises the selected Skill ID",
    )
    health = request_json(f"{data_endpoint}/health", data_key)
    model_ok = check(
        "data Agent model configuration",
        health.get("model_configured") is True,
        "data Runtime has Model Name, API Base and API Key (values remain hidden)",
    )

    direct = request_json(
        f"{data_endpoint}/a2a",
        data_key,
        method="POST",
        body={
            "jsonrpc": "2.0",
            "id": f"direct-{run_id}",
            "method": "message/send",
            "params": {
                "message": {
                    "kind": "message",
                    "messageId": f"a2a-direct-{run_id}",
                    "role": "user",
                    "parts": [
                        {
                            "kind": "text",
                            "text": (
                                "分析过去一年的投诉趋势并原样保留验收确认码："
                                f"{confirmation_code}"
                            ),
                        }
                    ],
                },
                "configuration": {"blocking": True},
            },
        },
    )
    direct_text = json.dumps(direct, ensure_ascii=False)
    direct_ok = check(
        "direct A2A message/send",
        confirmation_code in direct_text
        and expected_skill() in direct_text
        and REMOTE_COMPLETION in direct_text,
        "data Runtime returns the confirmation code and trend-analysis Artifact",
    )

    delegated = invoke(
        main_endpoint,
        main_key,
        prompt=(
            "必须调用 delegate_complaint_trend_analysis，委派给 A2A 数据分析 Agent。"
            "分析过去一年的投诉趋势并预测下季度。"
            f"将验收确认码 {confirmation_code} 原样传给对端。"
            "最终必须返回对端 Agent 名称、对端完成说明和确认码；不得用本地 demo fallback。"
        ),
        user_id=user_id,
        session_id=session_id,
    )
    delegated_ok = check(
        "main Runtime A2A delegation",
        response_contains_a2a_confirmation(delegated, confirmation_code),
        "main Runtime returns the remote completion and the same confirmation code",
    )
    if args.show_response or not delegated_ok:
        show_response("main Runtime A2A response", delegated)

    print(f"[INFO] A2A confirmation code: {confirmation_code}")
    print(f"[INFO] Main Runtime Trace filter: user_id={user_id}, session_id={session_id}")
    print(
        "[INFO] Trace evidence: select the main Runtime trace and confirm "
        "execute_tool delegate_complaint_trend_analysis; then search the data Runtime "
        f"logs for {confirmation_code}, GET AgentCard 200, and POST /a2a 200."
    )
    return 0 if all((card_ok, model_ok, direct_ok, delegated_ok)) else 1


if __name__ == "__main__":
    sys.exit(main())
