#!/usr/bin/env python3
"""Raw MCP client（标准库），通过 tunnel 的公网 URL 调私有 server 的工具。

用法（先按 README 起好 server + relay + agent）：
    python client.py http://127.0.0.1:8000/tunnel/demo/mcp
"""

import json
import sys
import urllib.request

PROTOCOL_VERSION = "2026-07-28"
_next_id = 0


def _meta() -> dict:
    return {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientInfo": {
            "name": "tunnel-client",
            "version": "0.1.0",
        },
        "io.modelcontextprotocol/clientCapabilities": {},
    }


def rpc(endpoint: str, method: str, params: dict, name: str | None = None) -> dict:
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

    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        data = {"http_status": e.code, "body": e.read().decode("utf-8")}
    print(f"<<< {data}")
    return data


def main() -> None:
    endpoint = (
        sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/tunnel/demo/mcp"
    )
    print(f"Tunnel MCP client -> {endpoint}")

    rpc(endpoint, "server/discover", {"_meta": _meta()})
    rpc(endpoint, "tools/list", {"_meta": _meta()})
    rpc(
        endpoint,
        "tools/call",
        {
            "name": "echo",
            "arguments": {"text": "hello through tunnel"},
            "_meta": _meta(),
        },
        name="echo",
    )
    rpc(
        endpoint,
        "tools/call",
        {"name": "private_flag", "arguments": {}, "_meta": _meta()},
        name="private_flag",
    )
    rpc(
        endpoint,
        "tools/call",
        {"name": "roll_dice", "arguments": {"faces": 6}, "_meta": _meta()},
        name="roll_dice",
    )


if __name__ == "__main__":
    main()
