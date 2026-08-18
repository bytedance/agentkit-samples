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

"""Minimal HTTPS client for the CUA Skill Gateway.

Stdlib only (urllib). Parses the gateway's unified `{ ok, data | error }`
envelope and converts errors into SkillError with the gateway error code.
"""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from cua_util import SkillError

DEFAULT_TIMEOUT_SEC = 120
MAX_RAW_RESPONSE_BYTES = 256 * 1024 * 1024


class _NoRedirect(HTTPRedirectHandler):
    """Reject redirects so bearer credentials never cross origins."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = build_opener(_NoRedirect)


def request(method, base_url, path, token=None, body=None, query=None, timeout=DEFAULT_TIMEOUT_SEC):
    """Perform an HTTP request and return (status_code, parsed_json)."""
    url = base_url.rstrip("/") + path
    if query:
        url += "?" + urlencode(query)
    headers = {"accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["content-type"] = "application/json"
    if token:
        headers["authorization"] = "Bearer " + token
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            return resp.status, _read_json(resp)
    except HTTPError as exc:
        return exc.code, _read_json(exc)
    except URLError as exc:
        raise SkillError("NETWORK", f"Cannot reach CUA gateway at {base_url}: {exc.reason}")
    except TimeoutError:
        raise SkillError("NETWORK", f"Request to {url} timed out")


def raw_request(method, base_url, path, token=None, body=None, query=None, timeout=DEFAULT_TIMEOUT_SEC):
    """Perform an HTTP request and return raw bytes plus response headers.

    Non-2xx responses are decoded like `gateway_call`, so callers get stable
    SkillError codes while successful artifact downloads can stream raw bytes.
    """
    url = base_url.rstrip("/") + path
    if query:
        url += "?" + urlencode(query)
    headers = {"accept": "application/octet-stream, */*"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["content-type"] = "application/json"
    if token:
        headers["authorization"] = "Bearer " + token
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            response_headers = _headers_dict(resp)
            content_length = response_headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > MAX_RAW_RESPONSE_BYTES:
                        raise SkillError("PAYLOAD_TOO_LARGE", "Artifact exceeds the 256 MiB download limit.")
                except ValueError:
                    pass
            raw = resp.read(MAX_RAW_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RAW_RESPONSE_BYTES:
                raise SkillError("PAYLOAD_TOO_LARGE", "Artifact exceeds the 256 MiB download limit.")
            return resp.status, response_headers, raw
    except HTTPError as exc:
        payload = _read_json(exc)
        _raise_gateway_error(exc.code, payload)
    except URLError as exc:
        raise SkillError("NETWORK", f"Cannot reach CUA gateway at {base_url}: {exc.reason}")
    except TimeoutError:
        raise SkillError("NETWORK", f"Request to {url} timed out")


def gateway_call(method, base_url, path, token=None, body=None, query=None, timeout=DEFAULT_TIMEOUT_SEC):
    """Call the gateway and return the `data` payload, raising SkillError on error."""
    status, payload = request(method, base_url, path, token=token, body=body, query=query, timeout=timeout)
    if isinstance(payload, dict) and payload.get("ok") is True:
        data = payload.get("data", {})
        if not isinstance(data, dict):
            return {}
        data = dict(data)
        if payload.get("request_id") and not data.get("request_id"):
            data["request_id"] = payload["request_id"]
            if "outcome" in data or "diagnostics" in data:
                diagnostics = dict(data.get("diagnostics") or {})
                diagnostics.setdefault("request_id", payload["request_id"])
                data["diagnostics"] = diagnostics
        return data
    _raise_gateway_error(status, payload)


def _raise_gateway_error(status, payload):
    # Prefer a real gateway error envelope (it carries the authoritative code).
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict) and error.get("code"):
        code = str(error["code"])
        raw_message = str(error.get("message") or "")
        lowered_message = raw_message.lower()
        if code == "UpstreamError" and (
            "already active" in lowered_message
            or "active task" in lowered_message
            or "active run" in lowered_message
        ):
            code = "ACTIVE_RUN_CONFLICT"
            message = "The cloud desktop already has an active task or run."
        else:
            message = f"Gateway request failed ({code})."
        safe_fields = {
            "retryable",
            "reason",
            "request_id",
            "upstream_code",
            "upstream_status",
            "conflict_scope",
            "active_task_id",
        }
        extra = {k: v for k, v in error.items() if k in safe_fields}
        if payload.get("request_id") and not extra.get("request_id"):
            extra["request_id"] = payload["request_id"]
        raise SkillError(code, message, **extra)
    # 502/503/504 usually come from the API gateway (not our envelope) when an
    # upstream sync wait exceeds the gateway timeout. Treat them as retryable so
    # the CLI keeps polling instead of failing the task.
    if status == 504:
        raise SkillError("GATEWAY_TIMEOUT", "Gateway timed out (HTTP 504); the task is likely still running.")
    if status in (502, 503):
        raise SkillError("CUA_BACKEND_UNAVAILABLE", f"Gateway/backend unavailable (HTTP {status}).")
    raise SkillError("INTERNAL", f"Unexpected non-JSON gateway response (HTTP {status})")


def _headers_dict(response):
    return {k.lower(): v for k, v in response.headers.items()}


def _read_json(response):
    try:
        raw = response.read().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Non-JSON body (e.g. an API-gateway 504 HTML page). Don't fabricate an
        # error code here — let gateway_call classify by HTTP status.
        return {"_non_json": True}
