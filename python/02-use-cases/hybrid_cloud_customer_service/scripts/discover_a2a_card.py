#!/usr/bin/env python3
"""Discover non-secret AgentCard identity and capability IDs."""

from __future__ import annotations

import argparse
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def card_url(service_url: str) -> str:
    """Derive the well-known AgentCard URL from a service or RPC URL."""
    base = service_url.rstrip("/")
    if base.endswith("/a2a"):
        base = base[: -len("/a2a")]
    return f"{base}/.well-known/agent-card.json"


def extract_card_summary(card: dict) -> dict[str, object]:
    """Return the fields needed by the main Runtime's A2A peer config."""
    name = str(card.get("name") or "").strip()
    capability_ids = [
        str(item.get("id") or "").strip()
        for item in card.get("skills", [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    ]
    if not name:
        raise ValueError("AgentCard does not contain a non-empty name.")
    if not capability_ids:
        raise ValueError("AgentCard does not contain any skills[].id capability.")
    return {"name": name, "capability_ids": capability_ids}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service-url", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    args = parser.parse_args()

    api_key = os.getenv("A2A_DATA_AGENT_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("A2A_DATA_AGENT_API_KEY is required for AgentCard discovery.")

    request = Request(
        card_url(args.service_url),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=args.timeout_seconds) as response:  # noqa: S310
            card = json.loads(response.read().decode())
    except HTTPError as exc:
        raise SystemExit(f"AgentCard discovery returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise SystemExit(f"Cannot reach AgentCard endpoint: {exc.reason}.") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit("AgentCard response is not valid JSON.") from exc

    try:
        summary = extract_card_summary(card)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
