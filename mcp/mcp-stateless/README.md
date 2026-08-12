# Stateless MCP Sample Server

一个演示 **MCP 2026-07-28 stateless 协议核心**的最小示例服务：没有 `initialize`/`initialized` 握手、没有 `Mcp-Session-Id`，每个请求都是自描述的。

> 参考：
> - 规范：https://modelcontextprotocol.io/specification/2026-07-28
> - [SEP-2575 · Make MCP Stateless](https://modelcontextprotocol.io/seps/2575-stateless-mcp)
> - 发布博客：https://blog.modelcontextprotocol.io/posts/2026-07-28/
> - Claude 博客（MCP 2026-07-28 接入）：https://claude.com/blog/bringing-mcp-2026-07-28-to-claude

## 什么是 stateless MCP

旧版 MCP 依赖一次 `initialize` 握手建立 session，session 状态在服务端保存。这导致：

- 没法直接放到 round-robin 负载均衡器后面（请求会落在不同实例，状态却只有一个实例有）；
- 实例宕机会丢掉会话，客户端要重连 + 重新握手；
- 服务端要管理/回收每个客户端的会话状态，容易出 bug 和内存泄漏。

`2026-07-28` 把协议改成 **stateless**（SEP-2575）：

- 每个请求自带协议版本、客户端身份、客户端能力（在 body 的 `_meta` 里）；
- 同步把 `MCP-Protocol-Version` / `Mcp-Method` / `Mcp-Name` 复制到 HTTP 头，方便网关直接按头路由和鉴权；
- `server/discover`（可选）让客户端提前拿到服务端能力；
- 需要状态时，用 **显式句柄**（tool 参数）承载，模型自己把状态来回传。

## 目录结构

| 文件 | 说明 |
| - | - |
| `server.py` | 基于官方 `mcp` SDK 2.0 的 stateless 服务（`stateless_http=True`） |
| `client.py` | **无 SDK、仅标准库**的裸客户端，逐行打印请求头/请求体，展示真实线上格式 |
| `test_stateless.py` | 冒烟测试（真实 uvicorn 进程 + 随机端口，无需外部依赖） |
| `requirements.txt` | Python 依赖 |

## 服务端工具（对应 stateless 的三个层次）

| 工具 | 层次 | 说明 |
| - | - | - |
| `add(a, b)` | 纯函数 | 完全无状态 |
| `bump_counter(handle)` | 状态在句柄里 | 把计数编码进 `handle` 参数来回传，服务端零存储 |
| `request_info(ctx)` | 自描述 | 返回当前请求自带的 `protocol_version`，证明每个请求独立 |
| `notes_save(key, text)` / `notes_read(key)` | 显式状态引用 | 状态仍保存，但由调用方显式传 `key` 引用（SEP-2575 第二层） |

## 运行

要求：Python 3.10+。

```bash
cd mcp/mcp-stateless
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --host 127.0.0.1 --port 9000
```

另开一个终端跑裸客户端（展示真实线上格式，含 HTTP 头）：

```bash
cd mcp/mcp-stateless
python client.py http://127.0.0.1:9000/mcp
```

也可以直接用 curl 手动验证（注意 stateless 要求的头）：

```bash
curl -sS http://127.0.0.1:9000/mcp \
  -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: tools/call' \
  -H 'Mcp-Name: add' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"add","arguments":{"a":40,"b":2},"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientInfo":{"name":"curl","version":"0.0"},"io.modelcontextprotocol/clientCapabilities":{}}}}'
```

## 测试

```bash
cd mcp/mcp-stateless
python test_stateless.py
```

覆盖：`server/discover`、`tools/list`、`tools/call`、句柄式状态、显式状态引用、自描述请求、无 `Mcp-Session-Id`，以及「协议版本头与 body 不一致 → 400」的规范 MUST 校验。

## 关键点

- 请求必须带 `Accept: application/json, text/event-stream`、`MCP-Protocol-Version`、`Mcp-Method`（`tools/call` 还要 `Mcp-Name`）；
- body 的 `_meta` 必须同时包含 `io.modelcontextprotocol/protocolVersion` 和 `io.modelcontextprotocol/clientCapabilities`（`clientInfo` 建议带上）；
- 服务端响应也没有 `Mcp-Session-Id` —— 请求与请求之间完全独立。
