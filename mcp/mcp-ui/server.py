from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastmcp import FastMCP
from fastmcp.server.http import create_streamable_http_app

import random

mcp = FastMCP(name="mcp-app-demo")

_INDEX_HTML = Path(__file__).with_name("index.html")


# ---------------------------
# MCP Apps（工具 = App）
# 工具只返回结构化数据，前端按工具类型渲染成不同的 HTML UI
# ---------------------------


@mcp.tool()
def weather(city: str):
    """查询城市实时天气。"""
    temp = random.randint(10, 35)
    return {
        "city": city,
        "temp": temp,
        "feels_like": temp + random.randint(-4, 4),
        "humidity": random.randint(30, 95),
        "wind": random.randint(0, 40),
        "status": random.choice(["sunny", "rainy", "cloudy", "snowy"]),
    }


@mcp.tool()
def search(query: str):
    """搜索相关结果。"""
    slug = query.replace(" ", "-")
    return [
        {
            "title": f"{query} 权威指南",
            "url": f"https://example.com/docs/{slug}",
            "snippet": f"深入讲解 {query} 的核心概念、最佳实践与常见陷阱，适合入门到进阶。",
            "source": "docs",
        },
        {
            "title": f"{query} 开源项目",
            "url": f"https://github.com/example/{slug}",
            "snippet": f"围绕 {query} 的高质量开源实现，star 持续增长、社区活跃。",
            "source": "github",
        },
        {
            "title": f"{query} 实战笔记",
            "url": f"https://example.com/blog/{slug}",
            "snippet": f"作者记录用 {query} 解决实际问题的完整过程与踩坑总结。",
            "source": "blog",
        },
    ]


@mcp.tool()
def user_profile(user_id: str):
    """查询用户资料。"""
    return {
        "user_id": user_id,
        "name": random.choice(
            ["Ada Lovelace", "Alan Turing", "Grace Hopper", "Linus Torvalds"]
        ),
        "plan": random.choice(["free", "pro", "enterprise"]),
        "balance": random.randint(100, 1000),
        "joined": random.choice(["2022-05-11", "2023-08-02", "2024-01-19"]),
        "verified": random.choice([True, False]),
        "stats": {
            "apps": random.randint(1, 12),
            "tokens_used": random.randint(1000, 99999),
        },
    }


# ---------------------------
# HTTP Server
# ---------------------------

app = FastAPI()
app.mount("/mcp", create_streamable_http_app(mcp, "/mcp"))


@app.get("/", response_class=HTMLResponse)
def root():
    return _INDEX_HTML.read_text(encoding="utf-8")
