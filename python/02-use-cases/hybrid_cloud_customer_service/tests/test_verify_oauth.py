from __future__ import annotations

import json

from scripts.verify_oauth import visible_sse_text


def _event(text: str) -> str:
    return "data: " + json.dumps({"content": {"parts": [{"thought": False, "text": text}]}})


def test_visible_sse_text_deduplicates_repeated_final_event() -> None:
    body = "\n".join((_event("OAUTH_GATEWAY_OK"), _event("OAUTH_GATEWAY_OK")))

    assert visible_sse_text(body) == "OAUTH_GATEWAY_OK"


def test_visible_sse_text_accepts_cumulative_stream_events() -> None:
    body = "\n".join((_event("OAUTH_"), _event("OAUTH_GATEWAY_OK")))

    assert visible_sse_text(body) == "OAUTH_GATEWAY_OK"
