# MCP App · 航班助手（本地可测试）

一个**本地可测试的 MCP App** 示例：MCP 工具只返回结构化数据，同源托管的前端把不同工具的输出渲染成交互式 UI（App）。

> 参考：https://modelcontextprotocol.io/extensions/apps/build

## 什么是 MCP App

MCP App 是在 MCP 之上构建交互式前端的一种方式：

- 服务端用**工具（Tool）**提供结构化数据（data contract）；
- 客户端/嵌入式 WebView 根据工具类型把数据渲染成对应的 **App UI**；
- 一个 MCP 服务可以同时托管 MCP 端点、App 前端和 App 清单。

本示例用 FastMCP + FastAPI 演示这一模式，全部在本地运行，无需任何外部服务。

## 目录结构

| 文件 | 说明 |
| - | - |
| `server.py` | FastMCP 服务 + FastAPI 托管：`/`（前端）、`/app.json`（App 清单）、`/mcp`（MCP 端点） |
| `index.html` | App 前端：搜索航班 → 点击查看详情 → 实时追踪 |
| `app.json` | App 清单：声明 App 的 id、入口、MCP 端点与工具契约 |
| `test_mcp_app.py` | 本地冒烟测试（进程内 HTTP，无需浏览器/端口） |
| `requirements.txt` | Python 依赖 |

## 数据契约（工具 → App UI）

| 工具 | 入参 | 输出 | UI |
| - | - | - | - |
| `search_flights` | `from_city, to_city, date` | 航班列表 | 航班卡片，可点击 |
| `get_flight` | `flight_id` | 航班详情 | 详情卡片（机型/登机口/价格/状态） |
| `track_flight` | `flight_id` | 行程时间线 | 时间线视图 |

前端每次调用都是一个独立的 `tools/call` 请求（stateless + JSON），无需 initialize 握手。

## 本地运行

要求：Python 3.10+。

```bash
cd mcp/mcp-app
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --port 8000
```

打开 http://127.0.0.1:8000 即可使用 App UI：

- 输入出发/到达城市 → **搜索航班**
- 点击航班卡片自动填入航班号 → **查询详情** / **实时追踪**

其他端点：

- MCP 端点：`POST http://127.0.0.1:8000/mcp`
- App 清单：`GET http://127.0.0.1:8000/app.json`

## 本地测试（无需启动服务）

```bash
cd mcp/mcp-app
python test_mcp_app.py
```

测试使用 FastAPI `TestClient` 在进程内直接请求真实应用，覆盖：前端页面、App 清单、`tools/list`、三个工具的 `tools/call` 数据契约、错误路径与 `/docs`。

## 如何接入支持 MCP Apps 的客户端

1. 在客户端 MCP 配置中加入该服务（Streamable HTTP）：`http://127.0.0.1:8000/mcp`
2. 客户端调用 `tools/list` 获取工具；
3. 调用 `search_flights`/`get_flight`/`track_flight` 拿到结构化数据；
4. 前端按 `app.json` 中声明的工具契约，把结果渲染成对应的 App UI。
