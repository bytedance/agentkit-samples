#!/usr/bin/env python3
"""Raw stateless MCP client（只用标准库，不依赖 MCP SDK）。

用最朴素的 HTTP + JSON 演示 2026-07-28 stateless 协议在「线上」长什么样：
- 没有 initialize/initialized 握手，没有 Mcp-Session-Id；
- 每个 POST 都自带 MCP-Protocol-Version / Mcp-Method / Mcp-Name 头；
- body 的 `_meta` 携带 protocolVersion / clientInfo / clientCapabilities。

用法：
    python client.py [http://127.0.0.1:9000/mcp]
"""

import json
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:9000/mcp"
PROTOCOL_VERSION = "2026-07-28"
CLIENT_INFO = {"name": "stateless-client", "version": "0.1.0"}

_next_id = 0


def _meta() -> dict:
    return {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientInfo": CLIENT_INFO,
        "io.modelcontextprotocol/clientCapabilities": {},
    }


def rpc(endpoint: str, method: str, params: dict, name: str | None = None) -> dict:
    """发送一个 stateless MCP 请求，打印请求头和请求体，返回解析后的 JSON。"""
    global _next_id
    _next_id += 1
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "Mcp-Method": method,
    }
    if name:
        headers["Mcp-Name"] = name
    body = json.dumps(
        {"jsonrpc": "2.0", "id": _next_id, "method": method, "params": params}
    ).encode("utf-8")

    print(f"\n>>> POST {endpoint}  # {method}")
    for key, value in headers.items():
        print(f"    {key}: {value}")
    print(f"    body: {body.decode()}")

    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        data = {"http_status": e.code, "body": e.read().decode("utf-8")}
    print(f"<<< {data}")
    return data


def tool_result_text(data: dict) -> dict:
    """把 tools/call 返回的 content[0].text（JSON 字符串）解析成 dict。"""
    result = data.get("result") or {}
    content = result.get("content") or [{}]
    try:
        return json.loads(content[0].get("text", "{}"))
    except json.JSONDecodeError:
        return {"text": content[0].get("text", "")}


def main() -> None:
    endpoint = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    print(f"Stateless MCP client -> {endpoint}")

    # 1) 可选的能力发现（server/discover）
    rpc(endpoint, "server/discover", {"_meta": _meta()})

    # 2) 工具列表（tools/list）
    rpc(endpoint, "tools/list", {"_meta": _meta()})

    # 3) 工具调用：纯函数（tools/call）
    rpc(
        endpoint,
        "tools/call",
        {"name": "add", "arguments": {"a": 40, "b": 2}, "_meta": _meta()},
        name="add",
    )

    # 4) 状态编码在句柄里：模型把返回的 handle 再传回来
    handle = "0"
    for _ in range(3):
        data = rpc(
            endpoint,
            "tools/call",
            {"name": "bump_counter", "arguments": {"handle": handle}, "_meta": _meta()},
            name="bump_counter",
        )
        handle = tool_result_text(data).get("handle", handle)

    # 5) 显式状态引用：key 由调用方显式传递
    rpc(
        endpoint,
        "tools/call",
        {
            "name": "notes_save",
            "arguments": {"key": "welcome", "text": "你好，MCP"},
            "_meta": _meta(),
        },
        name="notes_save",
    )
    rpc(
        endpoint,
        "tools/call",
        {"name": "notes_read", "arguments": {"key": "welcome"}, "_meta": _meta()},
        name="notes_read",
    )

    # 6) 自描述请求：返回当前请求自带的协议版本
    rpc(
        endpoint,
        "tools/call",
        {"name": "request_info", "arguments": {}, "_meta": _meta()},
        name="request_info",
    )


if __name__ == "__main__":
    main()
