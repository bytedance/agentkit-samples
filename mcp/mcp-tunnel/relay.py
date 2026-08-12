"""MCP tunnel sample · 公网 relay（唯一暴露在公网的部分）。

Claude 的「MCP tunnels（research preview）」思路（见
https://claude.com/blog/bringing-mcp-2026-07-28-to-claude）：
- 内网里的 MCP server 不需要任何入站防火墙规则/公网端点；
- 内网 agent 主动「向外」建连（这里用 WebSocket）到公网 relay；
- 远程 MCP 客户端只连 relay 的公网 URL，relay 把请求转发给对应 agent，
  agent 再转发给内网 server。

因为 MCP 2026-07-28 是 stateless 的，relay 不需要理解 JSON-RPC 内容、
也不需要会话亲和性：按 tunnel_id 找到 agent 的 WebSocket 连接，
把 HTTP 请求转发过去，再把响应原样转回来即可。

运行：
    uvicorn relay:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response

app = FastAPI(title="mcp-tunnel-relay")

# 需要转发给内网 server 的请求头（Host/Content-Length 等由 agent 自己生成）。
_FORWARD_HEADERS = {
    "content-type",
    "accept",
    "authorization",
    "mcp-protocol-version",
    "mcp-method",
    "mcp-name",
    "x-request-id",
}

_FORWARD_TIMEOUT = 30.0


class TunnelHub:
    """维护 tunnel_id -> agent WebSocket 的映射，并按 id 关联请求/响应。"""

    def __init__(self) -> None:
        self._agents: dict[str, WebSocket] = {}
        self._pending: dict[str, asyncio.Future] = {}

    def active(self) -> list[str]:
        return list(self._agents)

    async def serve_agent(self, tunnel_id: str, ws: WebSocket) -> None:
        """处理一个 agent 的 WebSocket 连接（在收到响应时兑现 pending future）。"""
        await ws.accept()
        self._agents[tunnel_id] = ws
        try:
            while True:
                msg = await ws.receive_json()
                future = self._pending.get(msg.get("id"))
                if future is not None and not future.done():
                    future.set_result(msg.get("response"))
        except WebSocketDisconnect:
            pass
        finally:
            self._agents.pop(tunnel_id, None)

    async def forward(
        self, tunnel_id: str, request: dict[str, Any]
    ) -> tuple[int, str | None] | None:
        """把一个 MCP 请求转发给指定 tunnel 的 agent，等待并返回其响应。

        返回 (status, body)；agent 未连接返回 None。
        """
        ws = self._agents.get(tunnel_id)
        if ws is None:
            return None
        req_id = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[req_id] = future
        try:
            await ws.send_json({"id": req_id, "request": request})
            response = await asyncio.wait_for(future, timeout=_FORWARD_TIMEOUT)
            return response.get("status", 502), response.get("body")
        except asyncio.TimeoutError:
            return 504, json.dumps(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": "tunnel agent timed out"},
                }
            )
        finally:
            self._pending.pop(req_id, None)


hub = TunnelHub()


@app.post("/register")
async def register(
    request: Request, body: dict[str, Any] | None = None
) -> JSONResponse:
    """agent 注册：返回公网 MCP URL 与 agent WebSocket URL。"""
    payload = body or {}
    tunnel_id = str(payload.get("tunnel_id") or uuid.uuid4().hex)
    base = str(request.base_url).rstrip("/")
    return JSONResponse(
        {
            "tunnel_id": tunnel_id,
            "public_url": f"{base}/tunnel/{tunnel_id}/mcp",
            "agent_ws_url": f"{base.replace('http', 'ws')}/tunnel/{tunnel_id}/agent",
        }
    )


@app.websocket("/tunnel/{tunnel_id}/agent")
async def agent_ws(websocket: WebSocket, tunnel_id: str) -> None:
    """内网 agent 主动建立的 WebSocket 连接（出站方向）。"""
    await hub.serve_agent(tunnel_id, websocket)


@app.post("/tunnel/{tunnel_id}/mcp")
async def tunnel_mcp(tunnel_id: str, request: Request) -> Response:
    """公网 MCP 端点：远程客户端（Claude 等）把 stateless MCP 请求 POST 到这里。"""
    body = (await request.body()).decode("utf-8", "replace")
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() in _FORWARD_HEADERS
    }
    response = await hub.forward(
        tunnel_id, {"method": request.method, "headers": headers, "body": body}
    )
    if response is None:
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": "tunnel agent is not connected"},
            },
            status_code=503,
        )
    status, body = response
    return Response(
        content=body or "", status_code=status, media_type="application/json"
    )


@app.get("/")
async def root() -> JSONResponse:
    return JSONResponse({"service": "mcp-tunnel-relay", "active_tunnels": hub.active()})
