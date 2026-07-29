#!/usr/bin/env python3
"""Verify a custom-JWT Runtime without printing OAuth credentials."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def get_json(url: str) -> dict[str, object]:
    with urlopen(url, timeout=30) as response:  # noqa: S310 - operator supplied URL
        return json.loads(response.read())


def token_url_with_grant(endpoint: str) -> str:
    parts = urlsplit(endpoint)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["grant_type"] = "client_credentials"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def obtain_token(token_endpoint: str, client_id: str, client_secret: str) -> str:
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    request = Request(
        token_url_with_grant(token_endpoint),
        data=b"grant_type=client_credentials",
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310 - discovery supplied URL
        payload = json.loads(response.read())
    token = str(payload.get("access_token") or "")
    if not token:
        raise RuntimeError("token response does not contain access_token")
    return token


def invoke(endpoint: str, authorization: str | None) -> tuple[int, str]:
    run_id = uuid.uuid4().hex[:8]
    headers = {
        "Content-Type": "application/json",
        "user_id": f"oauth-gateway-{run_id}",
        "session_id": f"oauth-gateway-{run_id}",
    }
    if authorization is not None:
        headers["Authorization"] = authorization
    request = Request(
        f"{endpoint.rstrip('/')}/invoke",
        data=json.dumps(
            {"prompt": "不要调用任何工具，只回复：OAUTH_GATEWAY_OK"},
            ensure_ascii=False,
        ).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=90) as response:  # noqa: S310 - operator supplied URL
            return response.status, response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def report(name: str, passed: bool, detail: str) -> bool:
    print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")
    return passed


def visible_sse_text(body: str) -> str:
    visible = ""
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        try:
            event = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        for part in event.get("content", {}).get("parts", []):
            if not part.get("thought") and part.get("text"):
                text = str(part["text"])
                if not text or visible.endswith(text):
                    continue
                if text.startswith(visible):
                    visible = text
                else:
                    visible += text
    if visible:
        return visible
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return ""
    for key in ("answer", "output", "text"):
        if payload.get(key):
            return str(payload[key])
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show-response", action="store_true")
    parser.add_argument(
        "--negative-checks",
        action="store_true",
        help="also verify that missing and malformed Bearer credentials are rejected",
    )
    args = parser.parse_args()

    endpoint = require_env("OAUTH_RUNTIME_ENDPOINT")
    discovery_url = require_env("OAUTH_DISCOVERY_URL")
    client_id = require_env("OAUTH_CLIENT_ID")
    client_secret = require_env("OAUTH_CLIENT_SECRET")

    try:
        discovery = get_json(discovery_url)
        token_endpoint = str(discovery.get("token_endpoint") or "")
        discovery_ok = bool(
            discovery.get("issuer") and discovery.get("jwks_uri") and token_endpoint
        )
        token = obtain_token(token_endpoint, client_id, client_secret)
    except (HTTPError, URLError, ValueError, RuntimeError) as exc:
        print(f"[FAIL] OAuth preparation: {type(exc).__name__}; credential values are hidden")
        return 1

    if not discovery_ok:
        print("[FAIL] OAuth token: Discovery is missing issuer, token endpoint, or JWKS")
        return 1

    checks = [
        report(
            "OAuth token",
            bool(token),
            "short-lived access token acquired from the user pool (hidden)",
        )
    ]

    valid_status, valid_body = invoke(endpoint, f"Bearer {token}")
    visible = visible_sse_text(valid_body)
    checks.append(
        report(
            "OAuth Runtime invoke",
            valid_status == 200 and bool(visible.strip()),
            f"Bearer token accepted; Runtime returns HTTP {valid_status} with a final response",
        )
    )
    if args.show_response and visible:
        normalized = " ".join(visible.split())
        print(f"[DEBUG] final response: {normalized[:600]}")

    if args.negative_checks:
        missing_status, _ = invoke(endpoint, None)
        checks.append(
            report(
                "missing credential",
                missing_status in (401, 403),
                f"gateway returns HTTP {missing_status}",
            )
        )

        invalid_status, _ = invoke(endpoint, "Bearer invalid.jwt.value")
        checks.append(
            report(
                "invalid credential",
                invalid_status in (401, 403),
                f"gateway returns HTTP {invalid_status}",
            )
        )
    else:
        print("[INFO] Negative gateway checks skipped; use --negative-checks when needed.")
    print("[INFO] OAuth access token and Client Secret were not printed or written to the project.")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
