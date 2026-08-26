"""Local OAuth2 chat client for a launched AgentKit Runtime."""

from __future__ import annotations

import base64
import json
import logging
import os
import secrets
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is normally present.
    load_dotenv = None

if load_dotenv:
    load_dotenv(
        Path(__file__).resolve().with_name(".env"),
        override=os.getenv("CLOUD_CLIENT_DOTENV_OVERRIDE", "true").lower()
        not in {"0", "false", "no"},
    )

from veadk.auth.middleware.oauth2_auth import (  # noqa: E402
    OAuth2Config,
    OAuth2RoutePaths,
    _fetch_oidc_discovery,
    setup_oauth2,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(levelname)s:%(name)s:%(message)s",
    force=True,
)
logger = logging.getLogger(__name__)

HOST = os.getenv("CLOUD_CLIENT_HOST", "127.0.0.1")
PORT = int(os.getenv("CLOUD_CLIENT_PORT", "8083"))
APP_NAME = os.getenv("CLOUD_AGENT_APP_NAME", "userpool_sandbox_mcp_authz")
DEFAULT_PROMPT = os.getenv(
    "CLOUD_AGENT_DEFAULT_PROMPT",
    "List the MCP tools available in the Skills Sandbox.",
)
DEFAULT_CALL_PATH = os.getenv("CLOUD_AGENT_CALL_PATH", "invoke")
_EPHEMERAL_COOKIE_SECRET = secrets.token_urlsafe(32)

HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _default_redirect_uri() -> str:
    return f"http://127.0.0.1:{PORT}/oauth2/callback"


def _issuer_from_userpool_id(userpool_id: str) -> str:
    userpool_id = userpool_id.strip().strip('"').strip("'")
    if not userpool_id:
        return ""
    region = _env("VE_IDENTITY_REGION") or _env("VOLCENGINE_REGION") or "cn-beijing"
    return f"https://userpool-{userpool_id}.userpool.auth.id.{region}.volces.com"


def _normalize_issuer_base(issuer_uri: str) -> str:
    issuer_uri = issuer_uri.rstrip("/")
    suffix = "/.well-known/openid-configuration"
    if issuer_uri.endswith(suffix):
        return issuer_uri[: -len(suffix)]
    return issuer_uri


def _api_path_prefixes() -> list[str]:
    return [
        "/api/",
        "/oauth2/userinfo",
    ]


def _finish_oauth2_config(config: OAuth2Config, redirect_uri: str) -> OAuth2Config:
    config.cookie_secure = redirect_uri.lower().startswith("https://")
    config.api_path_prefixes = _api_path_prefixes()

    origin = urlsplit(redirect_uri)
    config.logout_redirect_url = f"{origin.scheme}://{origin.netloc}/"
    config.end_session_url = None
    return config


def _oauth2_route_paths(config: OAuth2Config) -> OAuth2RoutePaths:
    callback_path = urlsplit(config.redirect_uri).path or "/oauth2/callback"
    return OAuth2RoutePaths(callback=callback_path)


def _build_oauth2_config() -> OAuth2Config:
    redirect_uri = _env("CLOUD_CLIENT_REDIRECT_URI", _default_redirect_uri())
    issuer_uri = (
        _env("OAUTH2_ISSUER_URI")
        or _env("OAUTH2_ISSUER")
        or _env("USERPOOL_DISCOVERY_URL")
        or _issuer_from_userpool_id(_env("USERPOOL_ID", "") or "")
    )
    client_id = _env("OAUTH2_CLIENT_ID") or _env("USERPOOL_CLIENT_ID")
    client_secret = _env("OAUTH2_CLIENT_SECRET")
    if not issuer_uri or not client_id:
        raise RuntimeError(
            "Missing cloud client login config. Set OAUTH2_ISSUER_URI + "
            "OAUTH2_CLIENT_ID, or USERPOOL_ID + USERPOOL_CLIENT_ID."
        )

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
            cookie_signing_secret=(
                _env("OAUTH2_COOKIE_SIGNING_SECRET")
                or client_secret
                or _env("FLASK_SECRET_KEY")
                or _EPHEMERAL_COOKIE_SECRET
            ),
        ),
        redirect_uri,
    )


def _runtime_base_url() -> str:
    value = _env("AGENT_RUNTIME_URL", "") or ""
    if not value:
        raise HTTPException(status_code=500, detail="AGENT_RUNTIME_URL is not set.")
    if not value.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=500,
            detail="AGENT_RUNTIME_URL must start with http:// or https://.",
        )
    for suffix in ("/run_sse", "/run", "/invoke"):
        if value.rstrip("/").endswith(suffix):
            return value.rstrip("/")[: -len(suffix)]
    return value.rstrip("/")


def _runtime_url(path: str) -> str:
    return f"{_runtime_base_url()}/{path.lstrip('/')}"


def _validated_access_token(scope: dict[str, Any]) -> str | None:
    state = scope.get("state")
    if not isinstance(state, dict):
        return None
    if not state.get("oauth2_access_token_validated", False):
        return None
    token = state.get("oauth2_access_token")
    if isinstance(token, str) and token.strip():
        return token.strip()
    return None


def _decode_jwt_claims_unverified(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    padded = payload + "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        data = json.loads(decoded)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _user_id_from_request(request: Request, access_token: str) -> str:
    user = request.scope.get("user")
    display_name = getattr(user, "display_name", None)
    if isinstance(display_name, str) and display_name:
        return display_name

    claims = _decode_jwt_claims_unverified(access_token)
    for key in ("sub", "user_id", "uid", "username", "email"):
        value = claims.get(key)
        if isinstance(value, str) and value:
            return value
    return "agentkit_user"


def _safe_runtime_host() -> str:
    try:
        parsed = urlsplit(_runtime_base_url())
    except HTTPException:
        return ""
    return parsed.netloc


def _config_diagnostics() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not _env("AGENT_RUNTIME_URL"):
        errors.append("AGENT_RUNTIME_URL is missing.")
    if not (_env("OAUTH2_ISSUER_URI") or _env("OAUTH2_ISSUER") or _env("USERPOOL_ID")):
        errors.append("OAUTH2_ISSUER_URI or USERPOOL_ID is missing.")
    if not (_env("OAUTH2_CLIENT_ID") or _env("USERPOOL_CLIENT_ID")):
        errors.append("OAUTH2_CLIENT_ID or USERPOOL_CLIENT_ID is missing.")
    if not _env("SKILL_SPACE_ID"):
        warnings.append("SKILL_SPACE_ID is empty; Skills Sandbox calls may fail.")
    try:
        call_path = _normalized_call_path(DEFAULT_CALL_PATH)
    except HTTPException:
        errors.append("CLOUD_AGENT_CALL_PATH must be one of: invoke, run, run_sse.")
    else:
        if call_path == "run_sse":
            warnings.append("CLOUD_AGENT_CALL_PATH=run_sse requires a Runtime session.")
    return errors, warnings


def _normalized_call_path(value: str | None) -> str:
    raw = (value or DEFAULT_CALL_PATH or "invoke").strip().strip("/")
    if raw not in {"invoke", "run", "run_sse"}:
        raise HTTPException(
            status_code=400,
            detail="call_path must be one of: invoke, run, run_sse.",
        )
    return raw


def _runtime_headers(
    access_token: str, user_id: str, session_id: str
) -> dict[str, str]:
    return {
        "Accept": "text/event-stream, application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "user_id": user_id,
        "session_id": session_id,
    }


def _adk_run_body(
    *,
    prompt: str,
    user_id: str,
    session_id: str,
    streaming: bool,
) -> dict[str, Any]:
    return {
        "app_name": APP_NAME,
        "user_id": user_id,
        "session_id": session_id,
        "new_message": {
            "role": "user",
            "parts": [{"text": prompt}],
        },
        "streaming": streaming,
    }


async def _ensure_adk_session(
    *,
    client: httpx.AsyncClient,
    access_token: str,
    user_id: str,
    session_id: str,
) -> None:
    url = _runtime_url(f"apps/{APP_NAME}/users/{user_id}/sessions")
    headers = _runtime_headers(access_token, user_id, session_id)
    response = await client.post(
        url,
        headers=headers,
        json={"session_id": session_id, "state": {}},
    )
    if response.status_code in {200, 201, 204, 409}:
        return
    body = response.text.lower()
    if response.status_code in {400, 500} and "already" in body and "exist" in body:
        return
    raise HTTPException(
        status_code=502,
        detail={
            "stage": "create_session",
            "runtime_status": response.status_code,
            "runtime_body": response.text[:2000],
        },
    )


def _sse_data(payload: dict[str, Any]) -> bytes:
    return (
        "data: "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + "\n\n"
    ).encode("utf-8")


async def _stream_invoke(
    *,
    client: httpx.AsyncClient,
    access_token: str,
    user_id: str,
    session_id: str,
    prompt: str,
) -> AsyncIterator[bytes]:
    headers = _runtime_headers(access_token, user_id, session_id)
    async with client.stream(
        "POST",
        _runtime_url("invoke"),
        headers=headers,
        json={"prompt": prompt},
    ) as response:
        if response.status_code >= 400:
            body = (await response.aread()).decode("utf-8", errors="replace")
            yield _sse_data(
                {
                    "error": "Runtime invoke failed",
                    "stage": "invoke",
                    "runtime_status": response.status_code,
                    "runtime_body": body[:2000],
                }
            )
            return
        async for chunk in response.aiter_bytes():
            yield chunk


async def _stream_run_sse(
    *,
    client: httpx.AsyncClient,
    access_token: str,
    user_id: str,
    session_id: str,
    prompt: str,
) -> AsyncIterator[bytes]:
    await _ensure_adk_session(
        client=client,
        access_token=access_token,
        user_id=user_id,
        session_id=session_id,
    )
    headers = _runtime_headers(access_token, user_id, session_id)
    async with client.stream(
        "POST",
        _runtime_url("run_sse"),
        headers=headers,
        json=_adk_run_body(
            prompt=prompt,
            user_id=user_id,
            session_id=session_id,
            streaming=True,
        ),
    ) as response:
        if response.status_code >= 400:
            body = (await response.aread()).decode("utf-8", errors="replace")
            yield _sse_data(
                {
                    "error": "Runtime run_sse failed",
                    "stage": "run_sse",
                    "runtime_status": response.status_code,
                    "runtime_body": body[:2000],
                }
            )
            return
        async for chunk in response.aiter_bytes():
            yield chunk


async def _stream_run(
    *,
    client: httpx.AsyncClient,
    access_token: str,
    user_id: str,
    session_id: str,
    prompt: str,
) -> AsyncIterator[bytes]:
    await _ensure_adk_session(
        client=client,
        access_token=access_token,
        user_id=user_id,
        session_id=session_id,
    )
    headers = _runtime_headers(access_token, user_id, session_id)
    response = await client.post(
        _runtime_url("run"),
        headers=headers,
        json=_adk_run_body(
            prompt=prompt,
            user_id=user_id,
            session_id=session_id,
            streaming=False,
        ),
    )
    if response.status_code >= 400:
        yield _sse_data(
            {
                "error": "Runtime run failed",
                "stage": "run",
                "runtime_status": response.status_code,
                "runtime_body": response.text[:2000],
            }
        )
        return
    try:
        payload = response.json()
    except json.JSONDecodeError:
        payload = {"text": response.text}
    yield _sse_data({"events": payload})


async def _cloud_event_stream(
    *,
    access_token: str,
    user_id: str,
    session_id: str,
    prompt: str,
    call_path: str,
) -> AsyncIterator[bytes]:
    timeout = float(os.getenv("CLOUD_CLIENT_TIMEOUT_SECONDS", "300"))
    async with httpx.AsyncClient(timeout=timeout) as client:
        yield _sse_data(
            {
                "meta": {
                    "app_name": APP_NAME,
                    "call_path": call_path,
                    "session_id": session_id,
                    "user_id": user_id,
                }
            }
        )
        try:
            if call_path == "invoke":
                async for chunk in _stream_invoke(
                    client=client,
                    access_token=access_token,
                    user_id=user_id,
                    session_id=session_id,
                    prompt=prompt,
                ):
                    yield chunk
            elif call_path == "run_sse":
                async for chunk in _stream_run_sse(
                    client=client,
                    access_token=access_token,
                    user_id=user_id,
                    session_id=session_id,
                    prompt=prompt,
                ):
                    yield chunk
            else:
                async for chunk in _stream_run(
                    client=client,
                    access_token=access_token,
                    user_id=user_id,
                    session_id=session_id,
                    prompt=prompt,
                ):
                    yield chunk
        except HTTPException as exc:
            yield _sse_data(
                {
                    "error": "Cloud client failed before Runtime execution",
                    "status": exc.status_code,
                    "detail": exc.detail,
                }
            )
        except httpx.RequestError as exc:
            logger.warning("Runtime request failed: %s", exc)
            yield _sse_data(
                {
                    "error": "Runtime request failed",
                    "detail": str(exc),
                }
            )


def _index_html() -> str:
    config_json = json.dumps(
        {
            "appName": APP_NAME,
            "defaultPrompt": DEFAULT_PROMPT,
            "defaultCallPath": _normalized_call_path(DEFAULT_CALL_PATH),
        },
        ensure_ascii=False,
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Skills Sandbox MCP Cloud Client</title>
  <style>
    :root {{
      --bg: #f5f7fb;
      --surface: #ffffff;
      --surface-2: #f0f4f9;
      --line: #d8dee9;
      --text: #18202f;
      --muted: #657084;
      --blue: #1d65d8;
      --blue-strong: #164da6;
      --green: #167a45;
      --amber: #9a6200;
      --red: #b3261e;
      --shadow: 0 18px 54px rgba(31, 42, 68, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px;
      letter-spacing: 0;
    }}
    button, input, textarea, select {{
      font: inherit;
    }}
    button {{
      border: 0;
      border-radius: 8px;
      min-height: 38px;
      padding: 0 14px;
      background: var(--blue);
      color: #fff;
      cursor: pointer;
    }}
    button:hover {{ background: var(--blue-strong); }}
    button.secondary {{
      background: var(--surface-2);
      color: var(--text);
      border: 1px solid var(--line);
    }}
    button.secondary:hover {{ background: #e6edf7; }}
    button:disabled {{
      cursor: not-allowed;
      opacity: 0.55;
    }}
    a {{ color: var(--blue); text-decoration: none; }}
    .shell {{
      min-height: 100vh;
      display: grid;
      grid-template-columns: 360px minmax(0, 1fr);
    }}
    aside {{
      border-right: 1px solid var(--line);
      background: #fbfcfe;
      padding: 24px;
    }}
    main {{
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      min-width: 0;
      height: 100vh;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 24px;
    }}
    .logo {{
      width: 34px;
      height: 34px;
      border-radius: 8px;
      background: linear-gradient(135deg, #1d65d8, #13a07d);
      display: grid;
      place-items: center;
      color: #fff;
      font-weight: 800;
    }}
    h1 {{
      margin: 0;
      font-size: 18px;
      line-height: 1.2;
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 13px;
      color: var(--muted);
      font-weight: 700;
      text-transform: uppercase;
    }}
    .panel {{
      border: 1px solid var(--line);
      background: var(--surface);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;
    }}
    .field {{
      margin: 12px 0 0;
    }}
    .label {{
      display: block;
      color: var(--muted);
      margin-bottom: 6px;
      font-size: 12px;
      font-weight: 700;
    }}
    input, textarea, select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--text);
      padding: 10px 11px;
      outline: none;
    }}
    textarea {{
      resize: vertical;
      min-height: 108px;
      line-height: 1.55;
    }}
    input:focus, textarea:focus, select:focus {{
      border-color: var(--blue);
      box-shadow: 0 0 0 3px rgba(29, 101, 216, 0.12);
    }}
    .kv {{
      display: grid;
      gap: 10px;
      margin-top: 12px;
      min-width: 0;
    }}
    .kv-row {{
      display: block;
      min-width: 0;
    }}
    .k {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      margin-bottom: 4px;
    }}
    .v {{
      display: block;
      width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      line-height: 1.4;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 6px 10px;
      background: #eef2f7;
      color: var(--muted);
      font-weight: 700;
      font-size: 12px;
    }}
    .status.ok {{ background: #e9f8ef; color: var(--green); }}
    .status.warn {{ background: #fff4df; color: var(--amber); }}
    .status.err {{ background: #fff0f0; color: var(--red); }}
    .dot {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: currentColor;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }}
    .top {{
      padding: 22px 28px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.86);
      backdrop-filter: blur(10px);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }}
    .title-block h1 {{ font-size: 22px; }}
    .title-block p {{
      margin: 6px 0 0;
      color: var(--muted);
    }}
    .messages {{
      overflow: auto;
      padding: 28px;
    }}
    .message {{
      max-width: 880px;
      border: 1px solid var(--line);
      background: var(--surface);
      border-radius: 8px;
      padding: 14px 16px;
      margin-bottom: 14px;
      box-shadow: 0 6px 18px rgba(31, 42, 68, 0.05);
    }}
    .message.user {{
      margin-left: auto;
      background: #eef5ff;
      border-color: #bfd4f5;
    }}
    .message .role {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      margin-bottom: 8px;
      text-transform: uppercase;
    }}
    .message .content {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      line-height: 1.6;
    }}
    .composer {{
      border-top: 1px solid var(--line);
      background: var(--surface);
      padding: 18px 28px 24px;
    }}
    .composer-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: end;
    }}
    .footer-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-top: 10px;
      color: var(--muted);
      font-size: 12px;
    }}
    details {{
      margin-top: 10px;
    }}
    summary {{
      cursor: pointer;
      color: var(--muted);
      font-weight: 700;
    }}
    pre {{
      margin: 10px 0 0;
      max-height: 220px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #0f172a;
      color: #dbeafe;
      padding: 12px;
      font-size: 12px;
      line-height: 1.5;
      white-space: pre-wrap;
    }}
    .notice {{
      color: var(--muted);
      line-height: 1.5;
    }}
    .errors {{
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }}
    .pill {{
      border-radius: 999px;
      padding: 6px 10px;
      background: var(--surface-2);
      color: var(--muted);
      font-weight: 700;
      font-size: 12px;
      overflow-wrap: anywhere;
    }}
    @media (max-width: 860px) {{
      .shell {{ grid-template-columns: 1fr; }}
      aside {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      main {{ height: auto; min-height: 70vh; }}
      .top, .messages, .composer {{ padding-left: 18px; padding-right: 18px; }}
      .composer-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <div class="brand">
        <div class="logo">AK</div>
        <div>
          <h1>Cloud Runtime Client</h1>
          <div class="notice">Skills Sandbox MCP experiment</div>
        </div>
      </div>

      <section class="panel">
        <h2>Identity</h2>
        <div id="authStatus" class="status warn"><span class="dot"></span><span>Checking</span></div>
        <div class="kv">
          <div class="kv-row"><div class="k">User</div><div id="userId" class="v">-</div></div>
          <div class="kv-row"><div class="k">Issuer</div><div id="issuer" class="v">-</div></div>
        </div>
        <div class="actions">
          <a href="/oauth2/login"><button type="button">Sign in</button></a>
          <a href="/oauth2/logout"><button type="button" class="secondary">Logout</button></a>
        </div>
      </section>

      <section class="panel">
        <h2>Runtime</h2>
        <div class="kv">
          <div class="kv-row"><div class="k">Host</div><div id="runtimeHost" class="v">-</div></div>
          <div class="kv-row"><div class="k">App</div><div id="appName" class="v">-</div></div>
        </div>
        <div class="field">
          <label class="label" for="callPath">Call path</label>
          <select id="callPath">
            <option value="invoke">/invoke</option>
            <option value="run_sse">/run_sse</option>
            <option value="run">/run</option>
          </select>
        </div>
        <div class="field">
          <label class="label" for="sessionId">Session ID</label>
          <input id="sessionId" autocomplete="off">
        </div>
        <div class="actions">
          <button id="newSession" type="button" class="secondary">New session</button>
        </div>
        <div id="diagnostics" class="errors"></div>
      </section>
    </aside>

    <main>
      <div class="top">
        <div class="title-block">
          <h1>Skills Sandbox MCP Cloud Call</h1>
          <p>Local login, cloud Runtime execution, user token forwarded as inbound auth.</p>
        </div>
        <span id="busy" class="status"><span class="dot"></span><span>Idle</span></span>
      </div>

      <div id="messages" class="messages">
        <div class="message">
          <div class="role">System</div>
          <div class="content">Ready for cloud Runtime calls.</div>
        </div>
      </div>

      <div class="composer">
        <div class="composer-grid">
          <textarea id="prompt" placeholder="Ask the cloud agent to use the MCP tools configured in Skills Sandbox."></textarea>
          <button id="send" type="button">Send</button>
        </div>
        <div class="footer-row">
          <span id="lastStatus">Ready</span>
          <button id="clear" type="button" class="secondary">Clear</button>
        </div>
        <details>
          <summary>Raw runtime events</summary>
          <pre id="rawLog"></pre>
        </details>
      </div>
    </main>
  </div>

  <script>
    const CONFIG = {config_json};
    const $ = (id) => document.getElementById(id);
    const messages = $("messages");
    const rawLog = $("rawLog");
    const promptBox = $("prompt");
    const sessionInput = $("sessionId");
    const callPath = $("callPath");
    const sendButton = $("send");
    const busy = $("busy");
    const lastStatus = $("lastStatus");

    function randomSessionId() {{
      const bytes = new Uint8Array(8);
      crypto.getRandomValues(bytes);
      return "cloud-client-" + Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
    }}

    function setBusy(active, text) {{
      busy.className = active ? "status warn" : "status";
      busy.querySelector("span:last-child").textContent = text;
      sendButton.disabled = active;
    }}

    function addMessage(role, content, kind) {{
      const item = document.createElement("div");
      item.className = "message" + (kind ? " " + kind : "");
      const roleEl = document.createElement("div");
      roleEl.className = "role";
      roleEl.textContent = role;
      const contentEl = document.createElement("div");
      contentEl.className = "content";
      contentEl.textContent = content || "";
      item.append(roleEl, contentEl);
      messages.appendChild(item);
      messages.scrollTop = messages.scrollHeight;
      return contentEl;
    }}

    function appendRaw(value) {{
      rawLog.textContent += value + "\\n";
      rawLog.scrollTop = rawLog.scrollHeight;
    }}

    function extractText(payload) {{
      const pieces = [];
      const visit = (value) => {{
        if (!value || typeof value !== "object") return;
        if (typeof value.text === "string") pieces.push(value.text);
        if (Array.isArray(value.parts)) value.parts.forEach(visit);
        if (value.content) visit(value.content);
        if (Array.isArray(value.events)) value.events.forEach(visit);
      }};
      visit(payload);
      return pieces.join("");
    }}

    function handleRuntimeData(data, assistantEl) {{
      if (!data.trim()) return;
      appendRaw(data);
      let payload;
      try {{
        payload = JSON.parse(data);
      }} catch {{
        assistantEl.textContent += data;
        return;
      }}
      if (payload.error) {{
        assistantEl.textContent += "\\n[Error] " + payload.error;
        if (payload.runtime_status) {{
          assistantEl.textContent += " (HTTP " + payload.runtime_status + ")";
        }}
        if (payload.runtime_body) {{
          assistantEl.textContent += "\\n" + payload.runtime_body;
        }}
        return;
      }}
      const text = extractText(payload);
      if (text) assistantEl.textContent += text;
    }}

    async function loadConfig() {{
      const configResp = await fetch("/api/config", {{headers: {{"Accept": "application/json"}}}});
      if (configResp.ok) {{
        const config = await configResp.json();
        $("runtimeHost").textContent = config.runtimeHost || "-";
        $("appName").textContent = config.appName || CONFIG.appName;
        callPath.value = config.defaultCallPath || CONFIG.defaultCallPath || "invoke";
        const diagnostics = $("diagnostics");
        diagnostics.textContent = "";
        [...(config.errors || []), ...(config.warnings || [])].forEach((item) => {{
          const pill = document.createElement("div");
          pill.className = "pill";
          pill.textContent = item;
          diagnostics.appendChild(pill);
        }});
      }}

      const meResp = await fetch("/api/me", {{headers: {{"Accept": "application/json"}}}});
      const status = $("authStatus");
      if (!meResp.ok) {{
        status.className = "status err";
        status.querySelector("span:last-child").textContent = "Signed out";
        $("userId").textContent = "-";
        return;
      }}
      const me = await meResp.json();
      status.className = "status ok";
      status.querySelector("span:last-child").textContent = "Signed in";
      $("userId").textContent = me.userId || "-";
      $("issuer").textContent = me.issuer || "-";
    }}

    async function sendMessage() {{
      const text = promptBox.value.trim();
      if (!text) return;
      const sessionId = sessionInput.value.trim() || randomSessionId();
      sessionInput.value = sessionId;
      localStorage.setItem("cloudClientSessionId", sessionId);

      addMessage("You", text, "user");
      const assistantEl = addMessage("Agent", "", "");
      rawLog.textContent = "";
      promptBox.value = "";
      setBusy(true, "Calling");
      lastStatus.textContent = "Calling cloud Runtime...";

      try {{
        const response = await fetch("/api/run-cloud", {{
          method: "POST",
          headers: {{"Content-Type": "application/json", "Accept": "text/event-stream"}},
          body: JSON.stringify({{
            prompt: text,
            session_id: sessionId,
            call_path: callPath.value,
          }}),
        }});
        if (response.status === 401) {{
          assistantEl.textContent = "Please sign in first.";
          lastStatus.textContent = "Authentication required";
          return;
        }}
        if (!response.body) {{
          assistantEl.textContent = await response.text();
          return;
        }}
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {{
          const {{done, value}} = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, {{stream: true}});
          const blocks = buffer.split(/\\n\\n/);
          buffer = blocks.pop() || "";
          for (const block of blocks) {{
            const lines = block.split(/\\n/).filter(line => line.startsWith("data:"));
            const data = lines.map(line => line.slice(5).trimStart()).join("\\n");
            handleRuntimeData(data, assistantEl);
          }}
        }}
        if (buffer.trim()) handleRuntimeData(buffer.trim(), assistantEl);
        if (!assistantEl.textContent.trim()) assistantEl.textContent = "(No text content returned. Check raw events.)";
        lastStatus.textContent = "Done";
      }} catch (error) {{
        assistantEl.textContent = "Request failed: " + error;
        lastStatus.textContent = "Failed";
      }} finally {{
        setBusy(false, "Idle");
      }}
    }}

    promptBox.value = CONFIG.defaultPrompt || "";
    sessionInput.value = localStorage.getItem("cloudClientSessionId") || randomSessionId();
    callPath.value = CONFIG.defaultCallPath || "invoke";
    $("newSession").addEventListener("click", () => {{
      sessionInput.value = randomSessionId();
      localStorage.setItem("cloudClientSessionId", sessionInput.value);
    }});
    $("clear").addEventListener("click", () => {{
      messages.innerHTML = "";
      rawLog.textContent = "";
    }});
    sendButton.addEventListener("click", sendMessage);
    promptBox.addEventListener("keydown", (event) => {{
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") sendMessage();
    }});
    loadConfig();
  </script>
</body>
</html>"""


def build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return _index_html()

    @app.get("/api/config")
    async def api_config() -> dict[str, Any]:
        errors, warnings = _config_diagnostics()
        return {
            "appName": APP_NAME,
            "defaultPrompt": DEFAULT_PROMPT,
            "defaultCallPath": _normalized_call_path(DEFAULT_CALL_PATH),
            "runtimeHost": _safe_runtime_host(),
            "runtimeUrlConfigured": bool(_env("AGENT_RUNTIME_URL")),
            "errors": errors,
            "warnings": warnings,
        }

    @app.get("/api/me")
    async def api_me(request: Request) -> dict[str, Any]:
        access_token = _validated_access_token(request.scope)
        if not access_token:
            raise HTTPException(status_code=401, detail="Not authenticated")
        claims = _decode_jwt_claims_unverified(access_token)
        return {
            "signedIn": True,
            "userId": _user_id_from_request(request, access_token),
            "issuer": claims.get("iss", ""),
            "expiresAt": claims.get("exp"),
        }

    @app.post("/api/run-cloud")
    async def api_run_cloud(request: Request) -> StreamingResponse:
        access_token = _validated_access_token(request.scope)
        if not access_token:
            raise HTTPException(
                status_code=401, detail="Sign in before calling Runtime."
            )

        try:
            payload = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body.") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="JSON object body required.")
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise HTTPException(status_code=400, detail="prompt is required.")

        user_id = payload.get("user_id")
        if not isinstance(user_id, str) or not user_id.strip():
            user_id = _user_id_from_request(request, access_token)
        session_id = payload.get("session_id")
        if not isinstance(session_id, str) or not session_id.strip():
            session_id = f"cloud-client-{secrets.token_hex(8)}"
        call_path = _normalized_call_path(payload.get("call_path"))

        return StreamingResponse(
            _cloud_event_stream(
                access_token=access_token,
                user_id=user_id.strip(),
                session_id=session_id.strip(),
                prompt=prompt.strip(),
                call_path=call_path,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    oauth2_config = _build_oauth2_config()
    setup_oauth2(
        app,
        oauth2_config,
        routes=_oauth2_route_paths(oauth2_config),
        exempt_paths={
            "/",
            "/favicon.ico",
            "/api/config",
            "/ping",
        },
    )
    return app


app = build_app()


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
