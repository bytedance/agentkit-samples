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

"""Local User Pool login + VeADK Web UI for the Skills Sandbox MCP sample."""

from __future__ import annotations

import json
import logging
import os
import secrets
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import uvicorn
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app
from starlette.types import ASGIApp, Message, Receive, Scope, Send

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is normally present.
    load_dotenv = None

if load_dotenv:
    load_dotenv(Path(__file__).resolve().with_name(".env"))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(levelname)s:%(name)s:%(message)s",
    force=True,
)

BASE_DIR = Path(__file__).resolve().parent
AGENTS_DIR = str(BASE_DIR)
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import veadk  # noqa: E402
from assistant.agent import LOCAL_INBOUND_AUTH_TOKEN_STATE_KEY  # noqa: E402
from veadk.auth.middleware.oauth2_auth import (  # noqa: E402
    OAuth2Config,
    _fetch_oidc_discovery,
    setup_oauth2,
)

WEBUI_DIR = Path(veadk.__file__).resolve().parent / "webui"

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
_EPHEMERAL_COOKIE_SECRET = secrets.token_urlsafe(32)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _bool_env(name: str, default: bool) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "y", "on"}


def _assert_local_bind(host: str) -> None:
    if host in {"127.0.0.1", "localhost", "::1"}:
        return
    if _bool_env("LOCAL_UI_ALLOW_REMOTE", False):
        return
    raise RuntimeError(
        "Local login UI refuses to bind to a non-loopback host by default. "
        "Use HOST=127.0.0.1, or set LOCAL_UI_ALLOW_REMOTE=true explicitly."
    )


def _default_redirect_uri() -> str:
    return f"http://127.0.0.1:{PORT}/oauth2/callback"


def _api_path_prefixes() -> list[str]:
    return [
        "/api/",
        "/apps/",
        "/debug/",
        "/list-apps",
        "/oauth2/userinfo",
        "/run",
        "/run_sse",
        "/sessions/",
        "/web/",
    ]


def _finish_oauth2_config(config: OAuth2Config, redirect_uri: str) -> OAuth2Config:
    config.cookie_secure = redirect_uri.lower().startswith("https://")
    config.api_path_prefixes = _api_path_prefixes()

    origin = urlsplit(redirect_uri)
    config.logout_redirect_url = f"{origin.scheme}://{origin.netloc}/"
    config.end_session_url = None
    return config


def _normalize_issuer_base(issuer_uri: str) -> str:
    issuer_uri = issuer_uri.rstrip("/")
    suffix = "/.well-known/openid-configuration"
    if issuer_uri.endswith(suffix):
        return issuer_uri[: -len(suffix)]
    return issuer_uri


def _issuer_from_userpool_id(userpool_id: str) -> str:
    region = _env("VE_IDENTITY_REGION") or _env("VOLCENGINE_REGION") or "cn-beijing"
    return f"https://userpool-{userpool_id}.userpool.auth.id.{region}.volces.com"


def _cookie_signing_secret(client_secret: str | None) -> str:
    return (
        _env("OAUTH2_COOKIE_SIGNING_SECRET")
        or client_secret
        or _EPHEMERAL_COOKIE_SECRET
    )


def _build_oauth2_config() -> OAuth2Config:
    redirect_uri = _env("OAUTH2_REDIRECT_URI", _default_redirect_uri())
    issuer_uri = (
        _env("OAUTH2_ISSUER_URI")
        or _env("OAUTH2_ISSUER")
        or _env("USERPOOL_DISCOVERY_URL")
    )
    userpool_id = _env("USERPOOL_ID")
    if not issuer_uri and userpool_id:
        issuer_uri = _issuer_from_userpool_id(userpool_id)

    client_id = _env("OAUTH2_CLIENT_ID") or _env("USERPOOL_CLIENT_ID")
    client_secret = _env("OAUTH2_CLIENT_SECRET")
    if issuer_uri and client_id:
        discovery = _fetch_oidc_discovery(_normalize_issuer_base(issuer_uri))
        return _finish_oauth2_config(
            OAuth2Config(
                authorize_url=discovery.authorization_endpoint,
                token_url=discovery.token_endpoint,
                userinfo_url=discovery.userinfo_endpoint,
                issuer=discovery.issuer,
                jwks_uri=discovery.jwks_uri,
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=_env("OAUTH2_SCOPES", "openid profile email")
                or "openid profile email",
                cookie_signing_secret=_cookie_signing_secret(client_secret),
            ),
            redirect_uri,
        )

    user_pool_name = _env("VE_IDENTITY_USER_POOL_NAME")
    user_pool_uid = _env("VE_IDENTITY_USER_POOL_UID")
    client_name = _env("VE_IDENTITY_USER_POOL_CLIENT_NAME")
    client_uid = _env("VE_IDENTITY_USER_POOL_CLIENT_UID")
    if (user_pool_name or user_pool_uid) and (client_name or client_uid):
        return _finish_oauth2_config(
            OAuth2Config.from_veidentity(
                user_pool_name=user_pool_name,
                user_pool_uid=user_pool_uid,
                client_name=client_name,
                client_uid=client_uid,
                redirect_uri=redirect_uri,
                auto_create=_bool_env("VE_IDENTITY_USER_POOL_AUTO_CREATE", False),
                auto_register_callback=_bool_env(
                    "VE_IDENTITY_USER_POOL_AUTO_REGISTER_CALLBACK", True
                ),
            ),
            redirect_uri,
        )

    raise RuntimeError(
        "Missing User Pool login config. Set OAUTH2_ISSUER_URI + "
        "OAUTH2_CLIENT_ID, USERPOOL_ID + USERPOOL_CLIENT_ID, or explicit "
        "VE_IDENTITY_USER_POOL_* variables."
    )


def _bearer_token_from_scope(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name.lower() != b"authorization":
            continue
        header_value = value.decode("latin-1").strip()
        scheme, _, token = header_value.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            return token.strip()
    return None


def _validated_access_token(scope: Scope) -> str | None:
    state = scope.get("state")
    if isinstance(state, dict) and state.get("oauth2_access_token_validated", False):
        token = state.get("oauth2_access_token")
        if isinstance(token, str) and token.strip():
            return token.strip()
    return _bearer_token_from_scope(scope)


def _with_authorization_header(scope: Scope, access_token: str) -> Scope:
    updated_scope = dict(scope)
    headers = [
        (name, value)
        for name, value in scope.get("headers", [])
        if name.lower() != b"authorization"
    ]
    headers.append((b"authorization", f"Bearer {access_token}".encode("latin-1")))
    updated_scope["headers"] = headers
    return updated_scope


def _with_user_token_state(payload: Any, access_token: str) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    updated = dict(payload)
    state_delta = updated.get("state_delta")
    if not isinstance(state_delta, dict):
        state_delta = updated.get("stateDelta")
    if not isinstance(state_delta, dict):
        state_delta = {}
    else:
        state_delta = dict(state_delta)

    state_delta[LOCAL_INBOUND_AUTH_TOKEN_STATE_KEY] = access_token
    updated["state_delta"] = state_delta
    updated["stateDelta"] = state_delta
    return updated


async def _read_body(receive: Receive) -> bytes:
    body_parts: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        if message["type"] != "http.request":
            continue
        body_parts.append(message.get("body", b""))
        if not message.get("more_body", False):
            break
    return b"".join(body_parts)


def _with_content_length(scope: Scope, body: bytes) -> Scope:
    updated_scope = dict(scope)
    headers = [
        (name, value)
        for name, value in scope.get("headers", [])
        if name.lower() != b"content-length"
    ]
    headers.append((b"content-length", str(len(body)).encode("ascii")))
    updated_scope["headers"] = headers
    return updated_scope


class UserTokenStateASGIMiddleware:
    """Bridge local OAuth2 login into ADK run state for this local experiment."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path") not in {"/run", "/run_sse"}
        ):
            await self.app(scope, receive, send)
            return

        access_token = _validated_access_token(scope)
        if not access_token:
            await self.app(scope, receive, send)
            return

        original_body = await _read_body(receive)
        body = original_body
        try:
            payload = json.loads(original_body or b"{}")
        except json.JSONDecodeError:
            pass
        else:
            updated_payload = _with_user_token_state(payload, access_token)
            if updated_payload is not None:
                body = json.dumps(
                    updated_payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")

        body_sent = False

        async def replay_receive() -> Message:
            nonlocal body_sent
            if body_sent:
                return await receive()
            body_sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        scope_with_auth = _with_authorization_header(scope, access_token)
        await self.app(
            _with_content_length(scope_with_auth, body),
            replay_receive,
            send,
        )


def build_app():
    _assert_local_bind(HOST)
    app = get_fast_api_app(
        agents_dir=AGENTS_DIR,
        web=False,
        auto_create_session=True,
    )

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    label = _env("OAUTH2_PROVIDER_LABEL", "VeIdentity") or "VeIdentity"

    @app.get("/web/auth-config")
    async def web_auth_config() -> dict[str, list[dict[str, str]]]:
        return {
            "providers": [
                {"id": "veidentity", "label": label, "loginUrl": "/oauth2/login"}
            ]
        }

    # Register this before setup_oauth2 so OAuth2 middleware runs first and this
    # bridge sees the validated access token on request.state / Authorization.
    app.add_middleware(UserTokenStateASGIMiddleware)

    setup_oauth2(
        app,
        _build_oauth2_config(),
        exempt_paths={"/", "/index.html", "/favicon.ico", "/ping", "/web/auth-config"},
        exempt_prefixes={"/assets", "/skillhub"},
    )

    if (WEBUI_DIR / "index.html").is_file():
        app.mount("/", StaticFiles(directory=str(WEBUI_DIR), html=True), name="webui")
    return app


app = build_app()


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
