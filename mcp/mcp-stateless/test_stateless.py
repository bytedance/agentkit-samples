#!/usr/bin/env python3
"""Stateless MCP sample server 冒烟测试（真实 uvicorn 进程，随机端口）。

运行：
    python test_stateless.py

覆盖：
- server/discover 返回 supportedVersions=[2026-07-28] 与 capabilities；
- tools/list 返回全部工具；
- tools/call 纯函数、句柄式状态、显式状态引用、自描述请求；
- 无 Mcp-Session-Id：两次独立请求不依赖任何会话；
- 头/体协议版本不一致 -> 400（规范 MUST）。
"""

import json
import socket
import threading
import time

import httpx
import uvicorn

import server as server_module

PROTOCOL_VERSION = "2026-07-28"
BASE_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": PROTOCOL_VERSION,
}


def _meta() -> dict:
    return {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "1.0"},
        "io.modelcontextprotocol/clientCapabilities": {},
    }


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(app) -> tuple[int, uvicorn.Server]:
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return port, server
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("server failed to start")


def _post(
    client: httpx.Client, url: str, method: str, params: dict, name: str | None = None
):
    headers = dict(BASE_HEADERS)
    headers["Mcp-Method"] = method
    if name:
        headers["Mcp-Name"] = name
    return client.post(
        url,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        headers=headers,
    )


def _call_result(response) -> dict:
    """tools/call 的 dict 结果在 content[0].text（JSON 字符串）里。"""
    result = response.json()["result"]
    return json.loads(result["content"][0]["text"])


def main() -> None:
    port, uvicorn_server = _start_server(server_module.app)
    url = f"http://127.0.0.1:{port}/mcp"
    failures = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        status = "PASS" if condition else "FAIL"
        print(f"[{status}] {label}" + (f"  ({detail})" if detail else ""))
        if not condition:
            failures.append(label)

    with httpx.Client(timeout=10.0) as client:
        # 1) server/discover
        r = _post(client, url, "server/discover", {"_meta": _meta()})
        discover = r.json()["result"]
        check(
            "server/discover 返回 supportedVersions=[2026-07-28]",
            discover["supportedVersions"] == [PROTOCOL_VERSION],
            str(discover.get("supportedVersions")),
        )
        check(
            "server/discover 返回 capabilities.tools",
            "tools" in discover["capabilities"],
        )
        check("server/discover 返回 serverInfo", "_meta" in discover)

        # 2) tools/list
        r = _post(client, url, "tools/list", {"_meta": _meta()})
        tools = {t["name"] for t in r.json()["result"]["tools"]}
        expected = {"add", "bump_counter", "request_info", "notes_save", "notes_read"}
        check("tools/list 包含全部 5 个工具", expected.issubset(tools), str(tools))

        # 3) tools/call：纯函数
        r = _post(
            client,
            url,
            "tools/call",
            {"name": "add", "arguments": {"a": 40, "b": 2}, "_meta": _meta()},
            name="add",
        )
        check("tools/call add(40,2)=42", _call_result(r) == 42)

        # 4) 句柄式状态：连续 bump 不依赖会话
        handle = "0"
        for _ in range(3):
            r = _post(
                client,
                url,
                "tools/call",
                {
                    "name": "bump_counter",
                    "arguments": {"handle": handle},
                    "_meta": _meta(),
                },
                name="bump_counter",
            )
            handle = _call_result(r)["handle"]
        check(
            "bump_counter 经过 3 次调用累计到 3（状态在句柄里）", handle == "3", handle
        )

        # 5) 显式状态引用
        _post(
            client,
            url,
            "tools/call",
            {
                "name": "notes_save",
                "arguments": {"key": "k", "text": "hi"},
                "_meta": _meta(),
            },
            name="notes_save",
        )
        r = _post(
            client,
            url,
            "tools/call",
            {"name": "notes_read", "arguments": {"key": "k"}, "_meta": _meta()},
            name="notes_read",
        )
        check("notes_read 能读到显式 key 保存的内容", _call_result(r)["text"] == "hi")

        # 6) 自描述请求
        r = _post(
            client,
            url,
            "tools/call",
            {"name": "request_info", "arguments": {}, "_meta": _meta()},
            name="request_info",
        )
        check(
            "request_info 返回 protocol_version",
            _call_result(r)["protocol_version"] == PROTOCOL_VERSION,
        )

        # 7) 无会话：响应头里没有 Mcp-Session-Id
        no_session = "mcp-session-id" not in {k.lower() for k in r.headers}
        check("响应头没有 Mcp-Session-Id（stateless）", no_session)

        # 8) 头/体协议版本不一致 -> 400（规范 MUST）
        mismatched_meta = dict(_meta())
        mismatched_meta["io.modelcontextprotocol/protocolVersion"] = "2025-11-25"
        bad = client.post(
            url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {"_meta": mismatched_meta},
            },
            headers={**BASE_HEADERS, "Mcp-Method": "tools/list"},
        )
        check(
            "MCP-Protocol-Version 头与 body 不一致 -> 400",
            bad.status_code == 400,
            f"status={bad.status_code}",
        )

    uvicorn_server.should_exit = True

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s): {failures}")
        raise SystemExit(1)
    print("All stateless checks passed.")


if __name__ == "__main__":
    main()
