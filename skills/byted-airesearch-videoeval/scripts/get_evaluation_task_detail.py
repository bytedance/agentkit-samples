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

"""Get material evaluation task detail."""

from __future__ import annotations

import argparse
import json
from typing import Any

from common import (
    CREATE_TASK_PATH,
    DEFAULT_TIMEOUT,
    build_request_id,
    build_url,
    create_session,
    failure,
    handle_top_level_exception,
    normalize_task,
    parse_json_response,
    print_json,
    request_error_details,
    success,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Get material evaluation task detail."
    )
    parser.add_argument("--task-id", required=True, help="Task identifier.")
    parser.add_argument(
        "--api-key",
        help="API key used to build the Authorization header.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"HTTP timeout in seconds. Default: {DEFAULT_TIMEOUT}.",
    )
    return parser


def build_summary(task: dict) -> dict:
    return {
        "task_id": task.get("id"),
        "status": task.get("status"),
        "name": task.get("name"),
        "prompt": task.get("prompt"),
        "result": task.get("result"),
        "updated_at": task.get("updated_at"),
    }


def parse_detail(detail: Any) -> list[dict[str, Any]]:
    if detail in (None, ""):
        return []

    if isinstance(detail, list):
        parsed = detail
    elif isinstance(detail, str):
        parsed = json.loads(detail)
    else:
        raise ValueError("Task detail must be a JSON string or a list.")

    if not isinstance(parsed, list):
        raise ValueError("Parsed task detail is not a list.")

    return [item for item in parsed if isinstance(item, dict)]


def filter_summary_report_items(detail_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in detail_items
        if item.get("key") == "video_structured_result" and item.get("sub_tab") is not None
    ]


def get_task_detail(task_id: str, api_key: str | None = None, timeout: float = DEFAULT_TIMEOUT) -> dict:
    request_id = build_request_id()
    session = create_session(api_key)
    response = session.get(build_url(f"{CREATE_TASK_PATH}/{task_id}"), timeout=timeout)
    raw_body = parse_json_response(response)

    if response.status_code >= 400:
        return failure(
            message="Task detail request failed.",
            code="GET_TASK_DETAIL_FAILED",
            details=request_error_details(response, raw_body),
            request_id=request_id,
        )

    normalized_task_id, task_status, task = normalize_task(raw_body)
    if not normalized_task_id:
        return failure(
            message="Task detail request succeeded but no task ID could be extracted.",
            code="TASK_ID_MISSING",
            details={"response": raw_body},
            request_id=request_id,
        )

    if not isinstance(task, dict):
        return failure(
            message="Task detail response is not a task object.",
            code="INVALID_TASK_PAYLOAD",
            details={"response": raw_body},
            request_id=request_id,
        )

    detail_items = parse_detail(task.get("detail"))
    filtered_detail = filter_summary_report_items(detail_items)

    return success(
        message="Task detail fetched successfully.",
        data={
            "task_id": normalized_task_id,
            "task_status": task_status,
            "detail": filtered_detail,
            "filtered_detail_count": len(filtered_detail),
            "summary": build_summary(task),
        },
        request_id=request_id,
    )


def main() -> None:
    args = build_parser().parse_args()
    payload = get_task_detail(
        task_id=args.task_id,
        api_key=args.api_key,
        timeout=args.timeout,
    )
    print_json(payload)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        handle_top_level_exception(exc)
