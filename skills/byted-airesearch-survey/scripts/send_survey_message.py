#!/usr/bin/env python3
# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from ai_research_message import run_payload  # noqa: E402

def _parse_host_capabilities(raw: str | None) -> dict | None:
    if not raw:
        return None
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("--host-capabilities-json must be a JSON object")
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send one conversational AI Research survey message.",
    )
    parser.add_argument(
        "--message",
        required=True,
        help="The latest user message in the current research conversation.",
    )
    parser.add_argument(
        "--session-id",
        help="Optional explicit session id. If omitted, the wrapper reuses local session state.",
    )
    parser.add_argument(
        "--force-new-session",
        action="store_true",
        help="Start a fresh research conversation instead of continuing the current session.",
    )
    parser.add_argument(
        "--api-key",
        help="Optional AI Research API Key for first-time binding or explicit override.",
    )
    parser.add_argument(
        "--base-url",
        help="Optional backend base URL or full /survey/skill/message endpoint.",
    )
    parser.add_argument(
        "--state-path",
        help="Optional local session-state cache path.",
    )
    parser.add_argument(
        "--source-channel",
        help="Optional source channel override. Defaults to skill.",
    )
    parser.add_argument(
        "--research-method",
        choices=("qualitative", "quantitative"),
        help="Optional preferred research method for the first round.",
    )
    parser.add_argument(
        "--language",
        choices=("zh", "en", "auto"),
        help="Optional output language passed to ABCompass.",
    )
    parser.add_argument(
        "--app-id",
        type=int,
        help="Optional ABCompass app id.",
    )
    parser.add_argument(
        "--request-kind",
        help="Optional structured intent such as new_request, revise, confirm_execute, query_status, query_result, query_plan, or expand_plan_detail.",
    )
    parser.add_argument(
        "--industry-hint",
        help="Optional normalized industry hint passed to the backend.",
    )
    parser.add_argument(
        "--normalized-message",
        help="Optional rewritten message that preserves intent but normalizes noisy industry wording.",
    )
    parser.add_argument(
        "--response-mode",
        choices=("sync_deferred", "sync_blocking"),
        help="Optional backend response mode. Defaults to sync_deferred.",
    )
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Query /survey/skill/status directly for the current session instead of sending a new conversational turn.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        help="Optional POST request timeout override.",
    )
    parser.add_argument(
        "--host-capabilities-json",
        help="Optional host capability JSON object.",
    )
    return parser


def payload_from_args(args: argparse.Namespace) -> dict:
    payload = {
        "message": args.message,
        "force_new_session": bool(args.force_new_session),
        "status_only": bool(args.status_only),
    }
    for key in (
        "session_id",
        "api_key",
        "base_url",
        "state_path",
        "source_channel",
        "research_method",
        "language",
        "app_id",
        "industry_hint",
        "normalized_message",
        "response_mode",
        "timeout_seconds",
        "request_kind",
    ):
        value = getattr(args, key)
        if value not in (None, ""):
            payload[key] = value
    host_capabilities = _parse_host_capabilities(args.host_capabilities_json)
    if host_capabilities:
        payload["host_capabilities"] = host_capabilities
    return payload


def main() -> int:
    args = build_parser().parse_args()
    payload = payload_from_args(args)
    response, code = run_payload(payload)
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
