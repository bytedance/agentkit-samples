"""MCP App 示例：航班助手。

一个“本地可测试”的 MCP App：
- 工具只返回结构化数据（data contract），前端把数据渲染成交互式 UI；
- 同一个 FastMCP 服务同时托管 App 前端（/）、App 清单（/app.json）和 MCP 端点（/mcp）。
"""

import json
from pathlib import Path
from random import Random

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastmcp import FastMCP
from fastmcp.server.http import create_streamable_http_app

mcp = FastMCP(name="mcp-flight-app")

_ROOT = Path(__file__).parent
_INDEX_HTML = _ROOT / "index.html"
_APP_MANIFEST = _ROOT / "app.json"

_AIRLINES = ["国航", "东航", "南航", "川航", "海航", "吉祥"]
_CITIES = ["北京", "上海", "深圳", "成都", "杭州", "广州", "西安", "三亚"]
_STATUS = ["scheduled", "boarding", "departed", "delayed", "cancelled", "landed"]
_STATUS_ZH = {
    "scheduled": "计划中",
    "boarding": "登机中",
    "departed": "已起飞",
    "delayed": "延误",
    "cancelled": "取消",
    "landed": "已到达",
}


def _rng(seed_text: str) -> Random:
    """基于 flight_id 生成确定的随机数，保证同一航班多次查询结果一致。"""
    return Random(seed_text)


# ---------------------------
# MCP Apps（工具 = App 的数据源）
# ---------------------------


@mcp.tool()
def search_flights(from_city: str, to_city: str, date: str = "今天"):
    """查询两个城市之间某一天的航班列表，返回可选的航班卡片数据。"""
    rng = Random(f"{from_city}-{to_city}-{date}")
    flights = []
    for i in range(rng.randint(4, 6)):
        flight_id = f"CA{rng.randint(1000, 9999)}"
        dep_hour = rng.randint(6, 21)
        dep_min = rng.choice([0, 5, 10, 15, 30, 45, 55])
        duration = rng.randint(90, 220)
        status = rng.choice(["scheduled", "boarding", "delayed", "cancelled"])
        flights.append(
            {
                "flight_id": flight_id,
                "airline": rng.choice(_AIRLINES),
                "from": from_city,
                "to": to_city,
                "date": date,
                "depart": f"{dep_hour:02d}:{dep_min:02d}",
                "arrive": f"{(dep_hour + duration // 60) % 24:02d}:{(dep_min + duration % 60) % 60:02d}",
                "duration": duration,
                "price": rng.randint(480, 1990),
                "status": status,
                "on_time": status not in ("delayed", "cancelled"),
            }
        )
    return flights


@mcp.tool()
def get_flight(flight_id: str):
    """按航班号查询航班详情（起降时刻、机型、价格、当前状态）。"""
    rng = _rng(flight_id)
    status = rng.choice(_STATUS)
    dep_hour = rng.randint(6, 21)
    dep_min = rng.choice([0, 5, 10, 15, 30, 45, 55])
    duration = rng.randint(90, 220)
    return {
        "flight_id": flight_id,
        "airline": rng.choice(_AIRLINES),
        "from": rng.choice(_CITIES),
        "to": rng.choice(_CITIES),
        "date": "今天",
        "depart": f"{dep_hour:02d}:{dep_min:02d}",
        "arrive": f"{(dep_hour + duration // 60) % 24:02d}:{(dep_min + duration % 60) % 60:02d}",
        "duration": duration,
        "model": rng.choice(["B737-800", "A320neo", "B787-9", "A350-900", "C919"]),
        "gate": f"{rng.randint(1, 40):02d}",
        "terminal": rng.choice(["T1", "T2", "T3"]),
        "price": rng.randint(480, 1990),
        "status": status,
        "status_zh": _STATUS_ZH[status],
        "delay_min": rng.randint(10, 180) if status == "delayed" else 0,
    }


@mcp.tool()
def track_flight(flight_id: str):
    """返回航班当前的行程时间线，用于前端渲染实时追踪视图。"""
    rng = _rng(f"{flight_id}-track")
    status = rng.choice(["checkin", "boarding", "flying", "landing", "arrived"])
    milestones = {
        "checkin": ["值机开放", "行李托运中"],
        "boarding": ["值机截止", "开始登机"],
        "flying": ["航班起飞", "巡航中"],
        "landing": ["开始下降", "即将落地"],
        "arrived": ["已落地", "行李提取"],
    }
    base = ["出票成功", "值机开放"]
    events = []
    for idx, label in enumerate(base + milestones[status], start=1):
        events.append(
            {
                "step": idx,
                "label": label,
                "time": f"{rng.randint(0, 9):02d}:{rng.choice([0, 10, 20, 30, 40, 50]):02d}",
                "done": idx <= len(base) + (0 if status == "checkin" else 1),
            }
        )
    return {
        "flight_id": flight_id,
        "status": status,
        "status_zh": {
            "checkin": "值机中",
            "boarding": "登机中",
            "flying": "飞行中",
            "landing": "降落中",
            "arrived": "已到达",
        }[status],
        "progress": len(events) - 1,
        "timeline": events,
    }


# ---------------------------
# HTTP Server（同源托管 App 前端 + MCP 端点）
# ---------------------------

# Streamable HTTP：stateless + JSON，前端每次 tools/call 都是独立请求，无需握手/session。
streamable_app = create_streamable_http_app(
    mcp, "/mcp", json_response=True, stateless_http=True
)
app = FastAPI(lifespan=streamable_app.lifespan)


@app.get("/", response_class=HTMLResponse)
def root():
    return _INDEX_HTML.read_text(encoding="utf-8")


@app.get("/app.json", response_class=JSONResponse)
def manifest():
    return JSONResponse(json.loads(_APP_MANIFEST.read_text(encoding="utf-8")))


app.mount("/", streamable_app)
