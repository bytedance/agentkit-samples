"""Local BFF that keeps the Runtime API key out of browser JavaScript."""

from __future__ import annotations

import os
import json
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Hybrid Cloud Customer Service Blueprint")
PROJECT_ROOT = Path(__file__).resolve().parent
GUIDE_WEB_DIR = PROJECT_ROOT / "guide_web"
CHAT_WEB_DIR = PROJECT_ROOT / "web"
# Process-local override: it is cleared when the UI server restarts and is
# never returned to browser JavaScript.
_runtime_override: dict[str, str] | None = None


class LocalChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    tenant_id: str = "demo-bank"
    user_id: str = "user-001"
    session_id: str = "local-ui-001"


class RuntimeConfigRequest(BaseModel):
    endpoint: str = Field(default="", max_length=2048)
    api_key: str = Field(default="", max_length=4096)
    mode: str = Field(default="remote", pattern="^(remote|demo)$")


def _runtime_settings() -> tuple[str, str, str]:
    if _runtime_override is not None:
        return _runtime_override["endpoint"], _runtime_override["api_key"], "ui-session"
    return (
        os.getenv("RUNTIME_ENDPOINT", "").rstrip("/"),
        os.getenv("RUNTIME_API_KEY", ""),
        "environment",
    )


def _visible_text_from_event(payload: dict[str, object]) -> list[str]:
    """Extract user-displayable text and deliberately omit model reasoning."""
    content = payload.get("content")
    if not isinstance(content, dict):
        return []
    parts = content.get("parts")
    if not isinstance(parts, list):
        return []
    return [
        text
        for part in parts
        if isinstance(part, dict)
        and part.get("thought") is not True
        and isinstance((text := part.get("text")), str)
    ]


def _thought_text_from_event(payload: dict[str, object]) -> list[str]:
    """Extract reasoning separately so the UI can show it behind disclosure."""
    content = payload.get("content")
    if not isinstance(content, dict) or not isinstance(content.get("parts"), list):
        return []
    return [
        text
        for part in content["parts"]
        if isinstance(part, dict)
        and part.get("thought") is True
        and isinstance((text := part.get("text")), str)
    ]


def _new_stream_text(previous: str, incoming: str) -> str:
    """Return only unseen text for SDKs that emit both partial and final snapshots."""
    if not incoming or incoming == previous or previous.endswith(incoming):
        return ""
    if incoming.startswith(previous):
        return incoming[len(previous) :]
    return incoming


def _sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _runtime_headers(request: LocalChatRequest, api_key: str) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "user_id": request.user_id,
        "session_id": request.session_id,
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _is_json_response(response: requests.Response) -> bool:
    headers = getattr(response, "headers", {})
    content_type = headers.get("content-type", "") if hasattr(headers, "get") else ""
    return "application/json" in content_type.lower()


def _normalize_json_result(
    payload: object, request: LocalChatRequest, trace_id: str
) -> dict[str, object]:
    if not isinstance(payload, dict) or not isinstance(payload.get("answer"), str):
        raise ValueError("Runtime JSON response does not contain a string answer.")
    result = dict(payload)
    result.setdefault("session_id", request.session_id)
    result.setdefault("trace_id", trace_id)
    result.setdefault("mode", "live")
    result.setdefault("citations", [])
    result.setdefault("events", [])
    return result


def _with_transport(
    result: dict[str, object], transport: str, endpoint: str = ""
) -> dict[str, object]:
    """Expose connection evidence without exposing credentials."""
    enriched = dict(result)
    enriched["transport"] = transport
    if endpoint:
        enriched["runtime_endpoint"] = endpoint
    return enriched


@app.get("/")
def index():
    """Default customer view: the step-by-step deployment guide."""
    return FileResponse(GUIDE_WEB_DIR / "index.html")


@app.get("/guide/{asset_name}")
def guide_asset(asset_name: str):
    if asset_name not in {"app.js", "styles.css"}:
        raise HTTPException(404)
    return FileResponse(GUIDE_WEB_DIR / asset_name)


@app.get("/chat")
def chat_workbench():
    """Interactive verification UI used after the Runtime is deployed."""
    return FileResponse(CHAT_WEB_DIR / "index.html")


@app.get("/web/{asset_name}")
def web_asset(asset_name: str):
    if asset_name not in {"app.js", "styles.css"}:
        raise HTTPException(404)
    return FileResponse(CHAT_WEB_DIR / asset_name)


@app.get("/ui/config")
def config() -> dict[str, object]:
    endpoint, api_key, source = _runtime_settings()
    return {
        "remote": bool(endpoint),
        "endpoint": endpoint or "local demo",
        # Deliberately reveal configuration state only; never expose the key.
        "api_key_configured": bool(api_key),
        "source": source,
    }


@app.post("/ui/runtime-config")
def runtime_config(request: RuntimeConfigRequest) -> dict[str, object]:
    """Configure one local UI process; credentials are never persisted or returned."""
    global _runtime_override
    if request.mode == "demo":
        _runtime_override = {"endpoint": "", "api_key": ""}
        return config()
    endpoint = request.endpoint.strip().rstrip("/")
    # Console examples commonly show the complete invoke URL. The BFF owns the
    # route suffix, so accept either form without producing /invoke/invoke.
    if endpoint.endswith("/invoke"):
        endpoint = endpoint[: -len("/invoke")].rstrip("/")
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(422, detail="Runtime endpoint must be a complete http(s) URL.")
    if not request.api_key.strip():
        raise HTTPException(422, detail="Runtime API Key is required for a remote Runtime.")
    _runtime_override = {"endpoint": endpoint, "api_key": request.api_key.strip()}
    return config()


@app.delete("/ui/runtime-config")
def clear_runtime_config() -> dict[str, object]:
    global _runtime_override
    _runtime_override = None
    return config()


@app.post("/ui/chat")
def chat(request: LocalChatRequest) -> dict[str, object]:
    endpoint, api_key, _ = _runtime_settings()
    if not endpoint:
        from demo_core import HybridCustomerService

        return _with_transport(
            HybridCustomerService("demo").chat(
                request.message,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                session_id=request.session_id,
            ).to_dict(),
            "local",
        )
    if not api_key:
        raise HTTPException(
            503,
            detail="Remote Runtime is configured but RUNTIME_API_KEY is missing. "
            "Set it in this UI process environment or in .env, then restart ./scripts/run_local_ui.sh.",
        )
    # The public Runtime gateway exposes /invoke, not the internal /apps routes.
    # AgentKit's compatibility endpoint creates the session on first request.
    try:
        response = requests.post(
            f"{endpoint}/invoke",
            headers=_runtime_headers(request, api_key),
            json={"prompt": request.message},
            timeout=90,
            stream=True,
        )
        response.raise_for_status()
        if _is_json_response(response):
            return _with_transport(
                _normalize_json_result(
                    response.json(), request, f"runtime-{uuid.uuid4().hex[:12]}"
                ),
                "remote",
                endpoint,
            )
        texts: list[str] = []
        thoughts: list[str] = []
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line or not raw_line.startswith("data: "):
                continue
            payload = json.loads(raw_line.removeprefix("data: "))
            if payload.get("error"):
                raise RuntimeError(payload["error"])
            texts.extend(_visible_text_from_event(payload))
            thoughts.extend(_thought_text_from_event(payload))
        answer = "".join(texts).strip() or "Runtime 未返回可展示的文本。"
        # The demo tool returns a structured response; preserve its local Trace schema
        # whenever the live agent returns that JSON as tool output.
        try:
            structured = json.loads(answer)
            if isinstance(structured, dict) and "answer" in structured:
                return _with_transport(structured, "remote", endpoint)
        except json.JSONDecodeError:
            pass
        return _with_transport(
            {
                "answer": answer,
                "session_id": request.session_id,
                "trace_id": f"runtime-{uuid.uuid4().hex[:12]}",
                "mode": "live",
                "citations": [],
                "thoughts": thoughts,
                "events": [
                    {
                        "name": "runtime.run_sse",
                        "status": "succeeded",
                        "mode": "live",
                        "detail": {},
                    }
                ],
            },
            "remote",
            endpoint,
        )
    except requests.RequestException as exc:
        raise HTTPException(502, detail=f"Runtime call failed: {exc}") from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(502, detail=f"Runtime stream failed: {exc}") from exc


@app.post("/ui/chat/stream")
def chat_stream(request: LocalChatRequest) -> StreamingResponse:
    """Forward the Runtime SSE stream so the browser can render incrementally."""
    endpoint, api_key, _ = _runtime_settings()

    def generate() -> Iterator[str]:
        trace_id = f"runtime-{uuid.uuid4().hex[:12]}"
        if not endpoint:
            result = chat(request)
            yield _sse("answer", {"text": result["answer"]})
            yield _sse("done", result)
            return
        if not api_key:
            yield _sse(
                "error",
                {
                    "detail": "Remote Runtime is configured but RUNTIME_API_KEY is missing. "
                    "Set it in .env or the UI process environment, then restart ./scripts/run_local_ui.sh."
                },
            )
            return
        response = None
        answer_so_far = ""
        thought_so_far = ""
        try:
            response = requests.post(
                f"{endpoint}/invoke",
                headers=_runtime_headers(request, api_key),
                json={"prompt": request.message},
                timeout=90,
                stream=True,
            )
            response.raise_for_status()
            if _is_json_response(response):
                result = _with_transport(
                    _normalize_json_result(response.json(), request, trace_id),
                    "remote",
                    endpoint,
                )
                yield _sse("answer", {"text": result["answer"]})
                yield _sse("done", result)
                return
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line or not raw_line.startswith("data: "):
                    continue
                payload = json.loads(raw_line.removeprefix("data: "))
                error = payload.get("error") or payload.get("errorMessage")
                if isinstance(error, str):
                    yield _sse("error", {"detail": error})
                    return
                visible = "".join(_visible_text_from_event(payload))
                thought = "".join(_thought_text_from_event(payload))
                visible_delta = _new_stream_text(answer_so_far, visible)
                thought_delta = _new_stream_text(thought_so_far, thought)
                if visible_delta:
                    answer_so_far += visible_delta
                    yield _sse("answer", {"text": visible_delta})
                if thought_delta:
                    thought_so_far += thought_delta
                    yield _sse("thought", {"text": thought_delta})
            yield _sse(
                "done",
                _with_transport(
                    {
                    "answer": answer_so_far or "Runtime 未返回可展示的文本。",
                    "thoughts": [thought_so_far] if thought_so_far else [],
                    "session_id": request.session_id,
                    "trace_id": trace_id,
                    "mode": "live",
                    "citations": [],
                    "events": [
                        {
                            "name": "runtime.run_sse",
                            "status": "succeeded",
                            "mode": "live",
                            "detail": {},
                        }
                    ],
                    },
                    "remote",
                    endpoint,
                ),
            )
        except (requests.RequestException, ValueError) as exc:
            yield _sse("error", {"detail": f"Runtime stream failed: {exc}"})
        finally:
            if response is not None and hasattr(response, "close"):
                response.close()

    return StreamingResponse(
        generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


@app.post("/ui/a2ui")
def a2ui(request: LocalChatRequest) -> dict[str, object]:
    """Expose the same trusted A2UI envelope for a remote AgentKit Runtime."""
    result = chat(request)
    components: list[dict[str, object]] = [{"type": "text", "props": {"text": result["answer"]}}]
    if result["citations"]:
        components.append({"type": "citation-list", "props": {"items": result["citations"]}})
    if result.get("thoughts"):
        components.append({"type": "reasoning", "props": {"items": result["thoughts"]}})
    components.append(
        {
            "type": "capability-timeline",
            "props": {"events": result["events"], "trace_id": result["trace_id"]},
        }
    )
    return {
        "version": "0.9",
        "surface": "agent-response",
        "mode": result.get("mode"),
        "transport": result.get("transport"),
        "runtime_endpoint": result.get("runtime_endpoint"),
        "components": components,
    }
