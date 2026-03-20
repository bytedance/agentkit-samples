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

"""Upload one or more videos, then create a material evaluation task."""

from __future__ import annotations

import argparse

from common import handle_top_level_exception, print_json
from create_evaluation_task import MAX_ATTACHMENT_IDS, build_request_body, create_task
from upload_video import INTERNAL_USE_TOKEN, upload_video, validate_upload_constraints
from common import DEFAULT_TIMEOUT, validate_file_exists


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Upload one or more videos, then create a material evaluation task."
    )
    parser.add_argument(
        "--file",
        action="append",
        required=True,
        help="Local MP4 file path to upload. Repeat to submit multiple videos.",
    )
    parser.add_argument("--prompt", help="Prompt text for task creation.")
    parser.add_argument(
        "--language",
        choices=("auto", "zh", "en"),
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
        choices=("VIEWPOINT", "PROFILE"),
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


def validate_batch(file_paths: list[str]) -> None:
    if len(file_paths) > MAX_ATTACHMENT_IDS:
        raise ValueError(
            "Too many videos. "
            f"At most {MAX_ATTACHMENT_IDS} videos are allowed per task submission, got {len(file_paths)}."
        )

    for file_path in file_paths:
        validate_file_exists(file_path)
        validate_upload_constraints(file_path)


def submit_task(args: argparse.Namespace) -> dict:
    validate_batch(args.file)

    attachment_ids: list[str] = []
    for file_path in args.file:
        upload_payload = upload_video(
            file_path=file_path,
            api_key=args.api_key,
            timeout=args.timeout,
            internal_use_only=INTERNAL_USE_TOKEN,
        )
        if upload_payload["status"] != "success":
            return upload_payload

        upload_data = upload_payload["data"]
        attachment_ids.append(upload_data["attachment_id"])

    body = build_request_body(
        argparse.Namespace(
            attachment_id=attachment_ids,
            prompt=args.prompt,
            language=args.language,
            enable_typical_user=args.enable_typical_user,
            typical_user_count=args.typical_user_count,
            typical_user_selection_mode=args.typical_user_selection_mode,
            enable_report=args.enable_report,
        )
    )
    task_payload = create_task(body=body, api_key=args.api_key, timeout=args.timeout)
    if task_payload["status"] != "success":
        return task_payload

    task_payload["data"]["submitted_video_count"] = len(attachment_ids)
    return task_payload


def main() -> None:
    args = build_parser().parse_args()
    payload = submit_task(args)
    print_json(payload)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        handle_top_level_exception(exc)
