"""Credential-free HTTP surface for deterministic demos and CI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from demo_core import HybridCustomerService
from platform_capabilities import capability_status, resolve_identity

app = FastAPI(title="AgentKit Hybrid Cloud Customer Service Demo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
service = HybridCustomerService("demo")
PROJECT_ROOT = Path(__file__).resolve().parent
GUIDE_WEB_DIR = PROJECT_ROOT / "guide_web"
CHAT_WEB_DIR = PROJECT_ROOT / "web"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    tenant_id: str = "demo-bank"
    user_id: str = "user-001"
    session_id: str = "session-001"


class InvokeRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    tenant_id: str = "demo-bank"
    user_id: str = "user-001"
    session_id: str = "console-test-001"


@app.get("/")
def index():
    return FileResponse(GUIDE_WEB_DIR / "index.html")


@app.get("/guide/{asset_name}")
def guide_asset(asset_name: str):
    if asset_name not in {"app.js", "styles.css"}:
        raise HTTPException(404)
    return FileResponse(GUIDE_WEB_DIR / asset_name)


@app.get("/chat")
def chat_workbench():
    return FileResponse(CHAT_WEB_DIR / "index.html")


@app.get("/web/{asset_name}")
def web_asset(asset_name: str):
    if asset_name not in {"app.js", "styles.css"}:
        raise HTTPException(404)
    return FileResponse(CHAT_WEB_DIR / asset_name)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "mode": "demo"}


@app.get("/ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/capabilities")
def capabilities() -> dict[str, dict[str, str | bool]]:
    return capability_status()


@app.get("/.well-known/agent-card.json")
def agent_card() -> dict[str, object]:
    return {
        "name": "hybrid-cloud-customer-service",
        "description": "Tenant-isolated customer service agent",
        "url": "/a2a",
        "version": "0.3.0",
        "capabilities": {"streaming": False, "pushNotifications": False},
        "skills": [
            {
                "id": "complaint-analysis",
                "name": "Complaint trend analysis",
                "tags": ["finance", "customer-service"],
            }
        ],
    }


@app.post("/a2a")
async def a2a_endpoint(request: Request) -> dict[str, object]:
    payload = await request.json()
    params = payload.get("params", {})
    text = params.get("message", {}).get("parts", [{}])[0].get("text", "分析投诉趋势")
    result = service.chat(text, session_id=str(params.get("sessionId", "a2a-session"))).to_dict()
    return {
        "jsonrpc": "2.0",
        "id": payload.get("id"),
        "result": {
            "status": {"state": "completed"},
            "artifacts": [{"parts": [{"text": result["answer"]}]}],
        },
    }


@app.post("/mcp")
async def mcp_endpoint(request: Request) -> dict[str, object]:
    payload = await request.json()
    method = payload.get("method")
    if method == "initialize":
        result = {
            "protocolVersion": "2025-03-26",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "hybrid-customer-service", "version": "0.3.0"},
        }
    elif method == "tools/list":
        result = {
            "tools": [
                {
                    "name": "calculate_transaction_summary",
                    "description": "Return transaction summary",
                    "inputSchema": {"type": "object", "properties": {}},
                },
                {
                    "name": "lookup_refund_policy",
                    "description": "Look up refund policy",
                    "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
                },
            ]
        }
    elif method == "tools/call":
        name = payload.get("params", {}).get("name")
        answer = service.chat(
            "分析这 237 笔交易的总收益"
            if name == "calculate_transaction_summary"
            else "理财产品可以退吗"
        ).answer
        result = {"content": [{"type": "text", "text": answer}], "isError": False}
    else:
        return {
            "jsonrpc": "2.0",
            "id": payload.get("id"),
            "error": {"code": -32601, "message": "Method not found"},
        }
    return {"jsonrpc": "2.0", "id": payload.get("id"), "result": result}


@app.post("/api/chat")
def chat(
    request: ChatRequest, authorization: str | None = Header(default=None)
) -> dict[str, object]:
    try:
        identity = resolve_identity(request.tenant_id, request.user_id, authorization)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return service.chat(
        request.message,
        tenant_id=identity.tenant_id,
        user_id=identity.user_id,
        session_id=request.session_id,
        identity_source=identity.source,
    ).to_dict()


@app.post("/invoke")
def invoke(request: InvokeRequest) -> dict[str, object]:
    """Compatibility endpoint used by the AgentKit console online test."""
    return service.chat(
        request.prompt,
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        session_id=request.session_id,
    ).to_dict()


@app.post("/api/a2ui")
def a2ui(
    request: ChatRequest, authorization: str | None = Header(default=None)
) -> dict[str, object]:
    """Return trusted declarative cards inspired by the A2UI component model."""
    try:
        identity = resolve_identity(request.tenant_id, request.user_id, authorization)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    result = service.chat(
        request.message,
        tenant_id=identity.tenant_id,
        user_id=identity.user_id,
        session_id=request.session_id,
        identity_source=identity.source,
    ).to_dict()
    components: list[dict[str, object]] = [{"type": "text", "props": {"text": result["answer"]}}]
    if result["citations"]:
        components.append({"type": "citation-list", "props": {"items": result["citations"]}})
    components.append(
        {
            "type": "capability-timeline",
            "props": {"events": result["events"], "trace_id": result["trace_id"]},
        }
    )
    return {"version": "0.9", "surface": "agent-response", "components": components}
