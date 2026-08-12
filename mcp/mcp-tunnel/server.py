"""MCP tunnel sample · 私有 MCP server（跑在内网 / 本机）。

这是一个简单的 stateless MCP server（2026-07-28 规范），只绑定 127.0.0.1：
- 它自己不出现在公网，也不需要任何入站防火墙规则/公网端点；
- tunnel agent 在它旁边运行，主动「向外」连到公网 relay，
  把公网来的请求转发到这里的 /mcp。

用 stateless server 的原因：relay/tunnel 不需要会话亲和性，
任意请求落在任意 agent 上都成立，转发逻辑因此非常简单。

运行：
    uvicorn server:app --host 127.0.0.1 --port 9000
"""

from mcp.server.mcpserver import MCPServer

server = MCPServer(
    name="private-internal",
    version="1.0.0",
    title="Private Internal Tools",
    description="一个只在内网可见的 MCP server，通过 tunnel 暴露给远程客户端。",
    instructions=(
        "这些工具模拟公司内网能力：external 客户端只有通过 tunnel 才能访问它们。"
    ),
)


@server.tool()
def echo(text: str) -> str:
    """原样返回文本，用于验证 tunnel 端到端连通。"""
    return text


@server.tool()
def roll_dice(faces: int = 6) -> int:
    """掷一个 faces 面的骰子，返回 1..faces 的随机整数（模拟内网服务）。"""
    import random

    return random.randint(1, faces)


@server.tool()
def private_flag() -> str:
    """返回一个模拟的「内网秘密」，只有内网/经 tunnel 才能拿到。"""
    return "only-visible-inside-private-network"


# ---------------------------
# ASGI app（stateless + JSON 响应）
# ---------------------------

app = server.streamable_http_app(
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
)
