"""MCP tunnel sample · tunnel agent（跑在内网，紧挨私有 MCP server）。

agent 是「主动向外」的一方：
1. 向公网 relay 的 /register 注册，拿到一个公网 URL；
2. 用 WebSocket 主动连到 relay（出站连接，不需要任何入站端口）；
3. 收到 relay 转来的 MCP 请求后，转发给本机私有 server；
4. 把私有 server 的响应原样送回 relay。

这就是 Claude「MCP tunnels（research preview）」的形态：内网不需要
暴露任何公网端点 / 入站防火墙规则 / IP 白名单。
参考：https://claude.com/blog/bringing-mcp-2026-07-28-to-claude

用法：
    python agent.py \
        --relay http://127.0.0.1:8000 \
        --tunnel-id demo \
        --local http://127.0.0.1:9000/mcp
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

import httpx
import websockets

logger = logging.getLogger("mcp-tunnel-agent")


async def forward_to_local(
    request: dict,
    local_mcp_url: str,
    client: httpx.AsyncClient,
    timeout: float = 30.0,
) -> dict:
    """把 relay 转来的 MCP 请求转发给本机私有 server，返回可送回 relay 的响应。"""
    headers = request.get("headers", {})
    response = await client.post(
        local_mcp_url, headers=headers, content=request.get("body", ""), timeout=timeout
    )
    return {
        "status": response.status_code,
        "content_type": response.headers.get("content-type", "application/json"),
        "body": response.text,
    }


async def run(
    relay_base: str,
    tunnel_id: str,
    local_mcp_url: str,
    *,
    reconnect: bool = True,
) -> None:
    """连接 relay 并循环转发请求。reconnect=False 时（如测试）断线即退出。"""
    ws_url = f"{relay_base.replace('http', 'ws')}/tunnel/{tunnel_id}/agent"
    while True:
        try:
            async with websockets.connect(ws_url) as ws:
                logger.info("tunnel '%s' connected -> %s", tunnel_id, ws_url)
                async with httpx.AsyncClient(timeout=30.0) as client:
                    async for raw in ws:
                        message = json.loads(raw)
                        response = await forward_to_local(
                            message["request"], local_mcp_url, client
                        )
                        await ws.send(
                            json.dumps({"id": message["id"], "response": response})
                        )
        except Exception as exc:  # noqa: BLE001 —— 重连循环需要兜底
            logger.warning(
                "connection lost (%s); %s",
                exc,
                "reconnecting..." if reconnect else "exiting",
            )
        if not reconnect:
            break
        await asyncio.sleep(2)


async def main() -> None:
    parser = argparse.ArgumentParser(description="MCP tunnel agent（内网侧）")
    parser.add_argument(
        "--relay", default="http://127.0.0.1:8000", help="公网 relay 地址"
    )
    parser.add_argument("--tunnel-id", default="demo", help="tunnel id")
    parser.add_argument(
        "--local",
        default="http://127.0.0.1:9000/mcp",
        help="本机私有 MCP server 的 /mcp 地址",
    )
    parser.add_argument("--once", action="store_true", help="断线后不重连（用于测试）")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    async with httpx.AsyncClient() as client:
        registered = await client.post(
            f"{args.relay}/register", json={"tunnel_id": args.tunnel_id}
        )
        registered.raise_for_status()
        info = registered.json()
        logger.info(
            "registered: tunnel_id=%s public_url=%s",
            info["tunnel_id"],
            info["public_url"],
        )

    await run(args.relay, args.tunnel_id, args.local, reconnect=not args.once)


if __name__ == "__main__":
    asyncio.run(main())
