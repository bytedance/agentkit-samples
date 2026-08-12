#!/usr/bin/env python3
"""MCP tunnel sample 端到端测试（真实进程 + 真实 WebSocket）。

运行：
    python test_tunnel.py

覆盖链路：
    远程 MCP 客户端 -> relay(公网) -> agent(WebSocket 出站) -> 私有 server
并验证：
- /register 返回公网 URL；
- 通过公网 URL 的 server/discover / tools/list / tools/call 端到端打通；
- 私有 server 的「内网秘密」通过 tunnel 可见；
- agent 未连接时 relay 返回 503（而不是误转发）。
"""

import asyncio
import socket
import threading
import time

import httpx
import uvicorn

import agent as agent_module
import relay as relay_module
import server as private_server

PROTOCOL_VERSION = "2026-07-28"


def _meta() -> dict:
    return {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientInfo": {"name": "tunnel-test", "version": "1.0"},
        "io.modelcontextprotocol/clientCapabilities": {},
    }


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_uvicorn(app, port: int) -> uvicorn.Server:
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return server
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("server failed to start")


async def _post(
    client: httpx.AsyncClient,
    url: str,
    method: str,
    params: dict,
    name: str | None = None,
):
    headers = {
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "Mcp-Method": method,
    }
    if name:
        headers["Mcp-Name"] = name
    return await client.post(
        url,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        headers=headers,
    )


def _text_result(response) -> str:
    return response.json()["result"]["content"][0]["text"]


async def main() -> None:
    failures: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        status = "PASS" if condition else "FAIL"
        print(f"[{status}] {label}" + (f"  ({detail})" if detail else ""))
        if not condition:
            failures.append(label)

    private_port = _free_port()
    relay_port = _free_port()
    private_uv = _start_uvicorn(private_server.app, private_port)
    relay_uv = _start_uvicorn(relay_module.app, relay_port)

    relay_base = f"http://127.0.0.1:{relay_port}"
    local_mcp = f"http://127.0.0.1:{private_port}/mcp"
    tunnel_id = "demo"

    agent_task: asyncio.Task | None = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 0) agent 未连接时，公网端点应返回 503
            reg = (
                await client.post(
                    f"{relay_base}/register", json={"tunnel_id": tunnel_id}
                )
            ).json()
            public_url = reg["public_url"]
            check("register 返回公网 URL", "/tunnel/demo/mcp" in public_url, public_url)

            # 1) 启动 agent（内网侧，出站 WebSocket）
            agent_task = asyncio.create_task(
                agent_module.run(relay_base, tunnel_id, local_mcp, reconnect=False)
            )

            # 2) 等待 agent 连上 relay
            connected = False
            for _ in range(50):
                active = (
                    (await client.get(relay_base + "/"))
                    .json()
                    .get("active_tunnels", [])
                )
                if tunnel_id in active:
                    connected = True
                    break
                await asyncio.sleep(0.1)
            check("agent 已通过 WebSocket 连上 relay", connected)

            # 3) 通过公网 URL 走一遍 stateless MCP 流程
            r = await _post(client, public_url, "server/discover", {"_meta": _meta()})
            check(
                "server/discover 通过 tunnel 成功",
                r.status_code == 200,
                f"status={r.status_code}",
            )
            check(
                "discover 返回私有 server 的能力",
                "tools" in r.json()["result"]["capabilities"],
            )

            r = await _post(client, public_url, "tools/list", {"_meta": _meta()})
            tools = {t["name"] for t in r.json()["result"]["tools"]}
            check(
                "tools/list 返回内网工具",
                {"echo", "roll_dice", "private_flag"}.issubset(tools),
                str(tools),
            )

            r = await _post(
                client,
                public_url,
                "tools/call",
                {"name": "echo", "arguments": {"text": "hi-tunnel"}, "_meta": _meta()},
                name="echo",
            )
            check(
                "tools/call echo 端到端打通",
                _text_result(r) == "hi-tunnel",
                _text_result(r),
            )

            r = await _post(
                client,
                public_url,
                "tools/call",
                {"name": "private_flag", "arguments": {}, "_meta": _meta()},
                name="private_flag",
            )
            check(
                "内网秘密经 tunnel 可见",
                "only-visible-inside-private-network" in _text_result(r),
            )

            # 4) 无 Mcp-Session-Id（stateless + tunnel 都不引入会话）
            check(
                "响应头没有 Mcp-Session-Id",
                "mcp-session-id" not in {k.lower() for k in r.headers},
            )

            # 5) 断开 agent 后应返回 503
            agent_task.cancel()
            try:
                await agent_task
            except asyncio.CancelledError:
                pass
            agent_task = None
            for _ in range(50):
                active = (
                    (await client.get(relay_base + "/"))
                    .json()
                    .get("active_tunnels", [])
                )
                if tunnel_id not in active:
                    break
                await asyncio.sleep(0.1)
            r = await _post(client, public_url, "tools/list", {"_meta": _meta()})
            check(
                "agent 断开后公网端点返回 503",
                r.status_code == 503,
                f"status={r.status_code}",
            )
    finally:
        if agent_task is not None:
            agent_task.cancel()
        private_uv.should_exit = True
        relay_uv.should_exit = True

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s): {failures}")
        raise SystemExit(1)
    print("All tunnel checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
