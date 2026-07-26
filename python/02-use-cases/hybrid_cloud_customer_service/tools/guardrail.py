"""Transparent demo guardrail that blocks prompt-injection patterns."""

from __future__ import annotations


BLOCKED_PATTERNS = (
    "ignore all previous",
    "system prompt",
    "完整凭据",
    "full credentials",
    "transfer $",
    "转账",
)


def detect_attack(message: str) -> list[str]:
    normalized = message.casefold()
    return [pattern for pattern in BLOCKED_PATTERNS if pattern in normalized]
