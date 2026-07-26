#!/usr/bin/env python3
"""Verify published AgentKit Knowledge and MEM0 Memory through public /invoke.

The script has no third-party dependencies and never prints the Runtime API
key. It makes three independent checks:
1. a published Knowledge canary is retrievable;
2. a preference survives a new session for the same user;
3. that preference is not visible to another user.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required; export it in your terminal first.")
    return value


def invoke(endpoint: str, api_key: str, *, prompt: str, user_id: str, session_id: str) -> str:
    """Call Runtime /invoke and combine visible SSE text without logging secrets."""
    request = Request(
        f"{endpoint.rstrip('/')}/invoke",
        data=json.dumps({"prompt": prompt}, ensure_ascii=False).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "user_id": user_id,
            "session_id": session_id,
        },
        method="POST",
    )
    visible_parts: list[str] = []
    try:
        with urlopen(request, timeout=90) as response:  # noqa: S310 - endpoint is user supplied
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue
                try:
                    event = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                if event.get("error"):
                    raise RuntimeError(event["error"])
                for part in event.get("content", {}).get("parts", []):
                    if not part.get("thought") and part.get("text"):
                        visible_parts.append(part["text"])
    except HTTPError as exc:
        raise RuntimeError(f"Runtime returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot reach Runtime: {exc.reason}") from exc
    return "".join(visible_parts)


def check(name: str, condition: bool, detail: str) -> bool:
    state = "PASS" if condition else "FAIL"
    print(f"[{state}] {name}: {detail}")
    return condition


def show_response(label: str, response: str) -> None:
    """Print a bounded, secret-free model response to diagnose a failed check."""
    normalized = " ".join(response.split())
    suffix = "..." if len(normalized) > 900 else ""
    print(f"[DEBUG] {label}: {normalized[:900]}{suffix}")


def response_is_exact_marker(response: str, marker: str) -> bool:
    """Accept only the requested marker, allowing duplicate SSE text frames.

    A model can mention the requested marker while explaining that it did *not*
    find it.  A substring check would mark that response as a false pass.  The
    recall prompt requires the marker alone, so remove harmless Markdown/space
    decoration and require the complete visible answer to be one or more copies
    of that marker.
    """
    compact = re.sub(r"[\s`*]+", "", response)
    return bool(re.fullmatch(f"(?:{re.escape(marker)})+", compact))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--wait-seconds",
        type=float,
        default=60.0,
        help="Maximum time to poll for asynchronous cross-session Memory recall",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=5.0,
        help="Interval between cross-session Memory recall attempts",
    )
    parser.add_argument(
        "--show-responses",
        action="store_true",
        help="print bounded visible model responses; Runtime API keys are never printed",
    )
    args = parser.parse_args()

    endpoint = _require("RUNTIME_ENDPOINT")
    api_key = _require("RUNTIME_API_KEY")
    run_id = uuid.uuid4().hex[:8]
    marker = f"MEM_CANARY_{run_id}"
    knowledge_user = f"knowledge-verify-{run_id}"
    user_a = f"memory-verify-{run_id}"
    user_b = f"memory-isolation-{run_id}"

    knowledge = invoke(
        endpoint,
        api_key,
        prompt="请调用知识库检索，只回答知识库验收标记及来源文件。",
        # Keep Knowledge validation out of the Memory user's history.  MEM0
        # records ordinary conversations too; reusing user_a here can make a
        # Knowledge request win the subsequent semantic memory search.
        user_id=knowledge_user,
        session_id=f"knowledge-{run_id}",
    )
    knowledge_ok = check(
        "published knowledge",
        "KB_CANARY_20260717_01" in knowledge and "knowledge_canary.md" in knowledge,
        "canary marker and source file are returned",
    )
    if args.show_responses or not knowledge_ok:
        show_response("knowledge response", knowledge)

    invoke(
        endpoint,
        api_key,
        prompt=f"请记住：我的退款到账偏好是 {marker}。只回复已记录。",
        user_id=user_a,
        session_id=f"memory-write-{run_id}",
    )
    deadline = time.monotonic() + max(args.wait_seconds, 0)
    same_user = ""
    recall_attempt = 0
    while True:
        recall_attempt += 1
        same_user = invoke(
            endpoint,
            api_key,
            prompt=(
                "必须先调用 load_memory 查询我的长期记忆。"
                f"如果工具结果包含 {marker}，只原样回答该值；"
                "只有工具明确返回空结果时才回答无。不得猜测或忽略工具结果。"
            ),
            user_id=user_a,
            session_id=f"memory-read-{run_id}",
        )
        if response_is_exact_marker(same_user, marker) or time.monotonic() >= deadline:
            break
        remaining = max(0, deadline - time.monotonic())
        delay = min(max(args.poll_seconds, 0.1), remaining)
        print(
            "[INFO] Memory canary is not visible yet; "
            f"retrying in {delay:g}s (attempt {recall_attempt})."
        )
        time.sleep(delay)
    same_user_ok = check(
        "cross-session memory",
        response_is_exact_marker(same_user, marker),
        f"same user reads the value written in a different session (attempts: {recall_attempt})",
    )
    if args.show_responses or not same_user_ok:
        show_response("same-user memory response", same_user)

    other_user = invoke(
        endpoint,
        api_key,
        prompt="请读取我的长期记忆：我的退款到账偏好是什么？只回答偏好值。",
        user_id=user_b,
        session_id=f"memory-isolation-{run_id}",
    )
    isolation_ok = check(
        "user isolation",
        marker not in other_user,
        "another user does not receive the first user's preference",
    )
    if args.show_responses or not isolation_ok:
        show_response("other-user memory response", other_user)

    print(f"[INFO] Verification users: {user_a}, {user_b}")
    return 0 if all((knowledge_ok, same_user_ok, isolation_ok)) else 1


if __name__ == "__main__":
    sys.exit(main())
