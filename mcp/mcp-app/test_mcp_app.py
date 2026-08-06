"""本地冒烟测试：无需启动浏览器/服务，直接对 FastAPI 应用做进程内 HTTP 测试。

运行方式（在 mcp-app 目录下）：
    python test_mcp_app.py
或使用已有虚拟环境：
    /path/to/.venv/bin/python test_mcp_app.py
"""

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))
import server

HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def extract_result(data):
    """与前端 extractResult() 保持一致的数据提取逻辑。"""
    if not data or data.get("result") is None:
        return None
    r = data["result"]
    if r.get("structuredContent") is not None:
        return r["structuredContent"]
    text = r.get("content") and r["content"][0] and r["content"][0].get("text")
    if text:
        try:
            return json.loads(text)
        except Exception:
            return text
    return r


def call(client, name, arguments):
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200, (resp.status_code, resp.text)
    data = resp.json()
    assert data["result"]["isError"] is False, data
    return extract_result(data)


def main():
    passed = 0
    with TestClient(server.app) as client:
        # 1. App 前端
        r = client.get("/")
        assert r.status_code == 200 and "航班助手" in r.text
        print("PASS  GET / -> App 前端 index.html")
        passed += 1

        # 2. App 清单
        r = client.get("/app.json")
        assert r.status_code == 200
        manifest = r.json()
        assert manifest["id"] == "mcp-flight-app"
        assert {t["name"] for t in manifest["tools"]} == {
            "search_flights",
            "get_flight",
            "track_flight",
        }
        print("PASS  GET /app.json -> App 清单", manifest["name"])
        passed += 1

        # 3. 工具列表
        r = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers=HEADERS,
        )
        tools = {t["name"] for t in r.json()["result"]["tools"]}
        assert tools == {"search_flights", "get_flight", "track_flight"}, tools
        print("PASS  tools/list ->", sorted(tools))
        passed += 1

        # 4. search_flights -> 航班卡片列表
        flights = call(
            client,
            "search_flights",
            {"from_city": "北京", "to_city": "上海", "date": "今天"},
        )
        assert isinstance(flights, list) and flights
        required = {
            "flight_id",
            "airline",
            "from",
            "to",
            "depart",
            "arrive",
            "duration",
            "price",
            "status",
            "on_time",
        }
        assert all(required <= set(f) for f in flights), flights[0]
        print(f"PASS  search_flights -> {len(flights)} 个航班")
        passed += 1

        # 5. get_flight -> 航班详情
        detail = call(client, "get_flight", {"flight_id": "CA1234"})
        required = {
            "flight_id",
            "from",
            "to",
            "depart",
            "arrive",
            "model",
            "gate",
            "terminal",
            "price",
            "status",
            "status_zh",
        }
        assert required <= set(detail), detail
        print("PASS  get_flight ->", detail["flight_id"], detail["status_zh"])
        passed += 1

        # 6. track_flight -> 行程时间线
        track = call(client, "track_flight", {"flight_id": "CA1234"})
        assert set(track) >= {"flight_id", "status", "status_zh", "timeline"}
        assert isinstance(track["timeline"], list) and track["timeline"]
        assert all(
            set(e) >= {"step", "label", "time", "done"} for e in track["timeline"]
        ), track["timeline"][0]
        print("PASS  track_flight ->", len(track["timeline"]), "个时间点")
        passed += 1

        # 7. 错误路径：缺少必填参数 -> isError=true
        r = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "search_flights", "arguments": {}},
            },
            headers=HEADERS,
        )
        assert r.status_code == 200 and r.json()["result"]["isError"] is True
        print("PASS  缺少必填参数 -> isError=true")
        passed += 1

        # 8. FastAPI 自带文档仍可用
        assert client.get("/docs").status_code == 200
        print("PASS  /docs 可用")
        passed += 1

    print(f"\n全部通过：{passed}/8")


if __name__ == "__main__":
    main()
