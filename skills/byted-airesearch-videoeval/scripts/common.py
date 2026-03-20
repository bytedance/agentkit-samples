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

"""Shared helpers for the byted-airesearch-videoeval skill."""

from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Any, Optional

import requests

BASE_URL_ENV = "BYTED_AIRESEARCH_VIDEOEVAL_BASE_URL"
BASE_URL = os.getenv(BASE_URL_ENV, "https://console.volcengine.com").rstrip("/")
UPLOAD_PATH = "/datatester/compass/api/v3/survey/attachment"
CREATE_TASK_PATH = "/datatester/compass/api/v3/survey/task"
API_KEY_ENV = "BYTED_AIRESEARCH_VIDEOEVAL_API_KEY"
DEFAULT_TIMEOUT = 60.0
PRODUCT_VERSION_HEADER = "x-product-version"
PRODUCT_VERSION_VALUE = "20"


def build_request_id() -> str:
    return str(uuid.uuid4())


def success(message: str, data: Any, request_id: Optional[str] = None) -> dict[str, Any]:
    return {
        "status": "success",
        "message": message,
        "request_id": request_id or build_request_id(),
        "data": data,
        "error": None,
    }


def failure(
    message: str,
    code: str,
    details: Any = None,
    request_id: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "status": "error",
        "message": message,
        "request_id": request_id or build_request_id(),
        "data": None,
        "error": {"code": code, "details": details},
    }


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def resolve_api_key(api_key: Optional[str]) -> str:
    resolved = (api_key or os.getenv(API_KEY_ENV, "")).strip()
    if resolved:
        return resolved

    raise PermissionError(
        "An API key is required. Provide --api-key or set "
        f"{API_KEY_ENV}. If you do not have one yet, create or view an API key at "
        "https://console.volcengine.com/datatester/ai-research/audience/list?tab=apikey first."
    )


def build_headers(api_key: Optional[str] = None) -> dict[str, str]:
    headers: dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": "byted-airesearch-videoeval/0.1",
        PRODUCT_VERSION_HEADER: PRODUCT_VERSION_VALUE,
    }

    resolved_api_key = resolve_api_key(api_key)
    headers["Authorization"] = f"bearer {resolved_api_key}"

    return headers


def build_url(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{BASE_URL}{path}"


def create_session(api_key: Optional[str] = None) -> requests.Session:
    session = requests.Session()
    session.headers.update(build_headers(api_key))
    return session


def parse_json_response(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise ValueError(
            f"Response is not valid JSON. status={response.status_code}, body={response.text[:1000]}"
        ) from exc


def unwrap_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        for key in ("data", "result", "payload"):
            value = payload.get(key)
            if value is not None:
                return value
    return payload


def exit_with_payload(payload: dict[str, Any], status_code: int = 0) -> None:
    print_json(payload)
    raise SystemExit(status_code)


def not_implemented_payload(operation: str) -> dict[str, Any]:
    return failure(
        message=f"{operation} API is not wired yet.",
        code="NOT_IMPLEMENTED",
        details={
            "operation": operation,
            "base_url": BASE_URL,
            "note": "Update this script after the concrete API definition is provided.",
        },
    )


def normalize_attachment(payload: Any) -> tuple[Optional[str], Any]:
    candidate = unwrap_payload(payload)
    if isinstance(candidate, dict) and "id" in candidate:
        return str(candidate["id"]), candidate

    if isinstance(payload, dict):
        for key in ("attachment", "item"):
            value = payload.get(key)
            if isinstance(value, dict) and "id" in value:
                return str(value["id"]), value

    return None, candidate


def normalize_task(payload: Any) -> tuple[Optional[str], Optional[str], Any]:
    candidate = unwrap_payload(payload)
    if isinstance(candidate, dict):
        task_id = candidate.get("id")
        status = candidate.get("status")
        if task_id is not None:
            return str(task_id), None if status is None else str(status), candidate

    if isinstance(payload, dict):
        for key in ("task", "item"):
            value = payload.get(key)
            if isinstance(value, dict) and value.get("id") is not None:
                status = value.get("status")
                return str(value["id"]), None if status is None else str(status), value

    return None, None, candidate


def request_error_details(response: requests.Response, body: Any) -> dict[str, Any]:
    return {
        "status_code": response.status_code,
        "response": body,
    }


def ensure_requests_available() -> None:
    if requests is None:
        raise RuntimeError("requests is required")


def handle_top_level_exception(exc: Exception) -> None:
    payload = failure(
        message=str(exc),
        code=exc.__class__.__name__.upper(),
    )
    print_json(payload)
    raise SystemExit(1)


def validate_file_exists(path: str) -> str:
    if not path:
        raise ValueError("A file path is required.")
    if not os.path.exists(path):
        raise FileNotFoundError(f"File does not exist: {path}")
    if not os.path.isfile(path):
        raise ValueError(f"Path is not a file: {path}")
    return path


def load_binary_file(path: str) -> bytes:
    with open(path, "rb") as file_obj:
        return file_obj.read()


def stderr(message: str) -> None:
    print(message, file=sys.stderr)
