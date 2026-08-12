"""Stateless MCP sample server（MCP 2026-07-28 规范）。

演示 stateless protocol core：
- 没有 initialize/initialized 握手，没有 Mcp-Session-Id；
- 每个请求都是自描述的：`_meta` 携带 protocolVersion / clientInfo / clientCapabilities，
  所以请求可以落在任意一个实例上（例如直接放到 round-robin 负载均衡器后面）；
- `server/discover` 可选，客户端可以借此提前拿到 server 能力；
- 状态用「显式句柄」承载（SEP-2575）：不藏在隐藏的 session 里，
  而是由模型作为工具参数来回传递。

参考：
- 规范：https://modelcontextprotocol.io/specification/2026-07-28
- SEP-2575（Make MCP Stateless）：https://modelcontextprotocol.io/seps/2575-stateless-mcp
- 发布博客：https://blog.modelcontextprotocol.io/posts/2026-07-28/

运行：
    uvicorn server:app --host 127.0.0.1 --port 9000
"""

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.context import Context

server = MCPServer(
    name="stateless-demo",
    version="1.0.0",
    title="Stateless MCP Demo",
    description="一个演示 MCP 2026-07-28 stateless 协议核心的最小示例服务。",
    instructions=(
        "这个服务演示 stateless MCP：没有握手、没有会话。"
        "bump_counter 把状态编码在 handle 参数里（SEP-2575 的显式句柄模式）；"
        "notes_save/notes_read 用显式 key 引用状态，而不是隐藏的会话。"
    ),
)


# ---------------------------
# 第一层：完全无状态的纯函数
# ---------------------------


@server.tool()
def add(a: int, b: int) -> int:
    """两个整数相加。纯函数：不需要会话，不保存任何状态。"""
    return a + b


@server.tool()
async def request_info(ctx: Context) -> dict:
    """返回当前请求自带的自描述元数据（来自 `_meta`）。

    证明每个请求都是独立的：服务端不需要维护会话就能知道是谁、用的哪个协议版本。
    """
    return {
        "protocol_version": ctx.protocol_version,
        "client_capabilities": (
            ctx.client_capabilities.model_dump() if ctx.client_capabilities else {}
        ),
        "note": "这些信息随每个请求的 _meta 一起到达，服务端不保存任何会话状态。",
    }


# ---------------------------
# 第二层：状态编码在显式句柄里（SEP-2575）
# 状态不藏在 session 里，而是作为工具参数来回传递。
# ---------------------------


@server.tool()
def bump_counter(handle: str = "0") -> dict:
    """无状态计数器：把当前计数值编码在 handle 里，返回下一次的 handle。

    handle 是类似 "3" 的字符串。调用 bump_counter("3") 返回 handle "4"。
    模型把返回的 handle 再传回来即可继续累加——全程服务器不保存任何状态。
    """
    try:
        n = int(handle or "0")
    except ValueError:
        raise ValueError("handle 必须是整数字符串，例如 '3'") from None
    return {"handle": str(n + 1), "value": n + 1}


# ---------------------------
# 第三层：显式状态引用（当完全无状态不现实时）
# 状态仍然保存，但由调用方在每次请求中显式传入 key 来引用，
# 而不是依赖传输层隐藏的会话。
# ---------------------------

_NOTES: dict[str, str] = {}


@server.tool()
def notes_save(key: str, text: str) -> dict:
    """把文本保存到显式的 key 下。后续读取时必须显式传入同一个 key。"""
    _NOTES[key] = text
    return {"key": key, "saved": True, "length": len(text)}


@server.tool()
def notes_read(key: str) -> dict:
    """读取之前用 notes_save 保存的文本。"""
    return {"key": key, "text": _NOTES.get(key)}


# ---------------------------
# ASGI app（stateless + JSON 响应）
# ---------------------------

app = server.streamable_http_app(
    streamable_http_path="/mcp",
    json_response=True,  # 每个请求用单个 JSON 对象响应（不用 SSE）
    stateless_http=True,  # 2026-07-28：无会话，每个 POST 独立处理
)
