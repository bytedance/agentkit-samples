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

"""List material evaluation tasks."""

from __future__ import annotations

import argparse

from common import (
    CREATE_TASK_PATH,
    DEFAULT_TIMEOUT,
    build_request_id,
    build_url,
    create_session,
    failure,
    handle_top_level_exception,
    parse_json_response,
    print_json,
    request_error_details,
    success,
)

FIXED_PAGE = 1
FIXED_PAGE_SIZE = 100
FIXED_AGENT_ID = 125


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List material evaluation tasks."
    )
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


def build_query_params() -> dict[str, int]:
    return {
        "page": FIXED_PAGE,
        "page_size": FIXED_PAGE_SIZE,
        "agent_id": FIXED_AGENT_ID,
    }


def normalize_list_payload(raw_body: object) -> tuple[list[dict], dict | None]:
    if not isinstance(raw_body, dict):
        raise ValueError("Task list response is not a JSON object.")

    payload = raw_body.get("data", raw_body)
    if not isinstance(payload, dict):
        raise ValueError("Task list payload is not a JSON object.")

    items = payload.get("list", [])
    page = payload.get("page")

    if not isinstance(items, list):
        raise ValueError("Task list field 'list' is not an array.")
    if page is not None and not isinstance(page, dict):
        raise ValueError("Task list field 'page' is not an object.")

    normalized_items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized_items.append(
            {
                "task_id": item.get("id"),
                "name": item.get("name"),
                "status": item.get("status"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
            }
        )

    return normalized_items, page


def list_tasks(api_key: str | None = None, timeout: float = DEFAULT_TIMEOUT) -> dict:
    request_id = build_request_id()
    session = create_session(api_key)
    response = session.get(
        build_url(CREATE_TASK_PATH),
        params=build_query_params(),
        timeout=timeout,
    )
    raw_body = parse_json_response(response)

    if response.status_code >= 400:
        return failure(
            message="Task list request failed.",
            code="LIST_TASKS_FAILED",
            details=request_error_details(response, raw_body),
            request_id=request_id,
        )

    items, page = normalize_list_payload(raw_body)
    return success(
        message="Task list fetched successfully.",
        data={
            "items": items,
            "page": page,
        },
        request_id=request_id,
    )


def main() -> None:
    args = build_parser().parse_args()
    payload = list_tasks(api_key=args.api_key, timeout=args.timeout)
    print_json(payload)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        handle_top_level_exception(exc)
