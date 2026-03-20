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

"""Create a long-running material evaluation task."""

from __future__ import annotations

import argparse
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

FIXED_AGENT_ID = 125
FIXED_AUDIENCE_ID = 3664529
FIXED_FORM_ID = 0
VALID_LANGUAGES = ("auto", "zh", "en")
VALID_TYPICAL_USER_SELECTION_MODES = ("VIEWPOINT", "PROFILE")
MAX_ATTACHMENT_IDS = 50


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a material evaluation task."
    )
    parser.add_argument(
        "--attachment-id",
        action="append",
        required=True,
        help="Attachment ID returned by upload_video.py. Repeat to send multiple IDs.",
    )
    parser.add_argument("--prompt", help="Prompt text for task creation.")
    parser.add_argument(
        "--language",
        choices=VALID_LANGUAGES,
        help="Language preference for the evaluation task.",
    )
    parser.add_argument(
        "--enable-typical-user",
        action="store_true",
        help="Enable typical user simulation.",
    )
    parser.add_argument(
        "--typical-user-count",
        type=int,
        help="Typical user count when typical user simulation is enabled.",
    )
    parser.add_argument(
        "--typical-user-selection-mode",
        choices=VALID_TYPICAL_USER_SELECTION_MODES,
        help="Selection mode for typical user generation.",
    )
    parser.add_argument(
        "--enable-report",
        action="store_true",
        help="Enable report generation.",
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


def build_request_body(args: argparse.Namespace) -> dict[str, Any]:
    attachment_ids = args.attachment_id
    if len(attachment_ids) > MAX_ATTACHMENT_IDS:
        raise ValueError(
            "Too many attachment IDs. "
            f"At most {MAX_ATTACHMENT_IDS} attachment_ids are allowed per task creation request, "
            f"got {len(attachment_ids)}."
        )

    body: dict[str, Any] = {
        "agent_id": FIXED_AGENT_ID,
        "audience_id": FIXED_AUDIENCE_ID,
        "form_id": FIXED_FORM_ID,
        "attachment_ids": attachment_ids,
    }

    if args.prompt:
        body["prompt"] = args.prompt
    if args.language:
        body["language"] = args.language
    if args.enable_typical_user:
        body["is_typical_user_enabled"] = True
    if args.typical_user_count is not None:
        if args.typical_user_count <= 0:
            raise ValueError("--typical-user-count must be greater than 0.")
        body["typical_user_count"] = args.typical_user_count
    if args.typical_user_selection_mode:
        body["typical_user_selection_mode"] = args.typical_user_selection_mode
    if args.enable_report:
        body["is_report_enabled"] = True

    return body


def create_task(body: dict[str, Any], api_key: str | None = None, timeout: float = DEFAULT_TIMEOUT) -> dict:
    request_id = build_request_id()
    session = create_session(api_key)
    response = session.post(build_url(CREATE_TASK_PATH), json=body, timeout=timeout)
    raw_body = parse_json_response(response)

    if response.status_code >= 400:
        return failure(
            message="Task creation failed.",
            code="CREATE_TASK_FAILED",
            details=request_error_details(response, raw_body),
            request_id=request_id,
        )

    task_id, task_status, task = normalize_task(raw_body)
    if not task_id:
        return failure(
            message="Task creation succeeded but no task ID could be extracted.",
            code="TASK_ID_MISSING",
            details={"response": raw_body},
            request_id=request_id,
        )

    return success(
        message="Evaluation task created successfully.",
        data={
            "task_id": task_id,
            "task_status": task_status,
            "follow_up_hint": (
                "This is a long-running task. Query task list or task detail later to check progress or fetch the result."
            ),
        },
        request_id=request_id,
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    body = build_request_body(args)
    payload = create_task(body=body, api_key=args.api_key, timeout=args.timeout)
    print_json(payload)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        handle_top_level_exception(exc)
