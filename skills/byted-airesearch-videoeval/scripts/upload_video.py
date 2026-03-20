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

"""Internal helper to upload a local video attachment for material evaluation."""

from __future__ import annotations

import argparse
import mimetypes
import os

from common import (
    CREATE_TASK_PATH,
    DEFAULT_TIMEOUT,
    UPLOAD_PATH,
    build_request_id,
    build_url,
    create_session,
    failure,
    handle_top_level_exception,
    normalize_attachment,
    parse_json_response,
    print_json,
    request_error_details,
    success,
    validate_file_exists,
)

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
ALLOWED_EXTENSION = ".mp4"
ALLOWED_MIME_TYPE = "video/mp4"
INTERNAL_USE_TOKEN = "create-task-flow"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Internal helper: upload a local video to the material evaluation attachment API."
    )
    parser.add_argument("--file", required=True, help="Local file path to upload.")
    parser.add_argument(
        "--internal-use-only",
        help="Internal marker required for create-task orchestration.",
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


def validate_internal_usage(internal_use_only: str | None) -> None:
    if internal_use_only != INTERNAL_USE_TOKEN:
        raise PermissionError(
            "Direct upload is not allowed. "
            "The upload API can only be used inside the material evaluation task creation flow."
        )


def validate_upload_constraints(file_path: str) -> None:
    extension = os.path.splitext(file_path)[1].lower()
    if extension != ALLOWED_EXTENSION:
        raise ValueError(
            "Only MP4 videos are supported. "
            f"Expected a '{ALLOWED_EXTENSION}' file, got '{extension or 'no extension'}'."
        )

    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type != ALLOWED_MIME_TYPE:
        raise ValueError(
            "Invalid MIME type for upload. "
            f"Expected '{ALLOWED_MIME_TYPE}', got '{mime_type or 'unknown'}'."
        )

    file_size = os.path.getsize(file_path)
    if file_size > MAX_FILE_SIZE_BYTES:
        size_mb = file_size / (1024 * 1024)
        raise ValueError(
            "Video file is too large. "
            f"Each video must be 50MB or smaller, got {size_mb:.2f}MB."
        )


def upload_video(
    file_path: str,
    api_key: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    internal_use_only: str | None = None,
) -> dict:
    validate_internal_usage(internal_use_only)
    validate_file_exists(file_path)
    validate_upload_constraints(file_path)
    request_id = build_request_id()
    session = create_session(api_key)
    url = build_url(UPLOAD_PATH)

    with open(file_path, "rb") as file_obj:
        files = {
            "file": (os.path.basename(file_path), file_obj, ALLOWED_MIME_TYPE)
        }
        response = session.post(url, files=files, timeout=timeout)

    body = parse_json_response(response)
    if response.status_code >= 400:
        return failure(
            message="Attachment upload failed.",
            code="UPLOAD_REQUEST_FAILED",
            details=request_error_details(response, body),
            request_id=request_id,
        )

    attachment_id, attachment = normalize_attachment(body)
    if not attachment_id:
        return failure(
            message="Attachment upload succeeded but no attachment ID could be extracted.",
            code="ATTACHMENT_ID_MISSING",
            details={"response": body},
            request_id=request_id,
        )

    return success(
        message="Attachment uploaded successfully.",
        data={
            "attachment_id": attachment_id,
            "attachment": attachment,
            "raw_response": body,
            "follow_up_hint": (
                "Use this attachment_id in create_evaluation_task.py as --attachment-id."
            ),
            "validation": {
                "max_videos_per_request": 50,
                "current_request_video_count": 1,
                "max_size_mb_per_video": 50,
                "mime_type": ALLOWED_MIME_TYPE,
            },
            "known_create_endpoint": build_url(CREATE_TASK_PATH),
        },
        request_id=request_id,
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    payload = upload_video(
        file_path=args.file,
        api_key=args.api_key,
        timeout=args.timeout,
        internal_use_only=args.internal_use_only,
    )
    print_json(payload)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        handle_top_level_exception(exc)
