#!/usr/bin/env python3
"""Verify a published Skills Center workflow through the deployed Runtime.

The proof uses a unique, non-sensitive confirmation code.  A pass requires the
visible Runtime answer to include the published Skill name, its expected
``needs_confirmation`` decision, and that code.  Runtime credentials are read
only from the calling process and never printed.
"""

from __future__ import annotations

import argparse
import sys
import uuid

try:  # Imported by tests or run with ``python -m`` from the Demo root.
    from scripts.verify_knowledge_memory import _require, check, invoke, show_response
except ModuleNotFoundError:  # Run directly as ``python scripts/verify_skills.py``.
    from verify_knowledge_memory import _require, check, invoke, show_response


def response_has_skill_confirmation(response: str, confirmation_code: str) -> bool:
    """Accept an SSE-duplicated visible answer containing all required evidence."""
    normalized = response.lower()
    return all(
        value in normalized
        for value in (
            "customer-service-compliance",
            "needs_confirmation",
            confirmation_code.lower(),
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--show-response",
        action="store_true",
        help="print the bounded visible response; Runtime API keys are never printed",
    )
    args = parser.parse_args()

    endpoint = _require("RUNTIME_ENDPOINT")
    api_key = _require("RUNTIME_API_KEY")
    run_id = uuid.uuid4().hex[:8]
    confirmation_code = f"SKILL_CANARY_{run_id}"
    response = invoke(
        endpoint,
        api_key,
        prompt=(
            "必须调用 execute_skills，并使用已发布的 "
            "customer-service-compliance Skill 检查理财产品退款申请。"
            "这是一次验收：将确认码 "
            f"{confirmation_code} 原样传给 Skill。"
            "最终只返回三项：Skill 名称 customer-service-compliance；"
            "决策 needs_confirmation；确认码。不得在调用工具后提前结束回答。"
        ),
        user_id=f"skills-verify-{run_id}",
        session_id=f"skills-verify-{run_id}",
    )
    passed = check(
        "published Skills execution",
        response_has_skill_confirmation(response, confirmation_code),
        "customer-service-compliance, needs_confirmation, and confirmation code are returned",
    )
    if args.show_response or not passed:
        show_response("Skills response", response)
    print(f"[INFO] Skills confirmation code: {confirmation_code}")
    print(f"[INFO] Verification user/session: skills-verify-{run_id}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
