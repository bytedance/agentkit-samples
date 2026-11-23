# 从 Hi Agent 的 HTTP 插件调用 AgentKit Runtime

[English](README_en.md) · [返回双向调用示例](../README.md)

## 调用链路

**Hi Agent 智能体 → Hi Agent 的 HTTP 插件 → HTTP 适配器（本目录） → AgentKit 上的目标智能体**

本目录实现 HTTP 补充路径中的适配器。适配器和目标智能体分别运行在两个 AgentKit Runtime 上。Hi Agent 的插件向适配器发送 `POST /` 请求。适配器转换请求格式，再调用 `UPSTREAM_BASE_URL` 指向的目标智能体（示例中的 `simple_agent`）。

回复由目标智能体生成，再经适配器传回 Hi Agent 的插件。普通调用一次返回 JSON，流式调用通过 SSE 逐段返回文本。

这份示例最初接入的 Hi Agent 插件会把整个 JSON 对象再编码成字符串。直接发送时，目标 Runtime 返回 HTTP 422。该版本的插件还要求流式响应头为 `Content-Type: text/event-stream`。适配器处理这两处格式差异。

## 1. 选择目标智能体

首次运行可部署示例 `simple_agent`。在目标 Runtime 控制台的「快速调用」中复制完整 Endpoint 和 API Key。[目标智能体部署指南](../simple_agent/README.md)

也可以复用已部署的智能体。目标 Runtime 需支持下表中所用模式的接口。回复可以是 ADK 事件数组，也可以是每帧携带 ADK 事件 JSON 的 SSE 流。适配器提取模型文本，跳过用户消息和思考内容。各路径都追加到目标 Endpoint 之后。

| 插件请求 | 适配器对目标 Runtime 的请求 |
| --- | --- |
| 普通 `POST /` | 调用 `POST /invoke`，请求体为 `{"prompt":"…"}`，请求头携带 `user_id` 和 `session_id`。 |
| 流式 `POST /`，设 `streaming=true` | 先用 `POST /apps/{app}/users/{user}/sessions/{session}` 创建会话（已有会话返回 409 可继续），再调用 `POST /run_sse`。 |
| 显式调用适配器的 `POST /run` | 使用同一会话接口，再调用目标 `POST /run`，读取 ADK 事件数组。此入口只提供普通回复。 |

## 2. 在本地启动适配器

从仓库根目录运行以下命令。示例使用 Python 3.12。

```bash
cd python/01-tutorials/01-agentkit-runtime/call_hiagent/http_plugin
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

在 `.env` 中填写目标配置。

| 变量 | 填写内容 |
| --- | --- |
| `UPSTREAM_BASE_URL` | 目标 Runtime 的完整 Endpoint，包括已有的 `/runtime/<id>` 前缀。适配器自行追加接口路径。 |
| `UPSTREAM_API_KEY` | 目标 Runtime 的 API Key 原值。适配器会添加 `Bearer` 前缀。 |
| `UPSTREAM_APP_NAME` | 目标的 ADK 应用名，默认为 `simple_agent`。适配器在创建会话的 URL 和发给 `/run_sse`、`/run` 的 `app_name` 字段中使用它。普通 `/invoke` 调用无需此项。 |

运行 `python plugin_server.py`。默认地址是 `http://127.0.0.1:8000`。以下请求在另一终端执行，会调用真实的目标智能体。

## 3. 检查普通回复和流式事件

先模拟插件的二次编码。保留请求体最外层的双引号和里面的反斜杠。适配器也接受普通 JSON 对象。

```bash
curl -sS -i http://127.0.0.1:8000/ \
  -H 'Content-Type: application/json' \
  --data-binary '"{\"message\":\"请介绍你自己\",\"user_id\":\"user1\",\"session_id\":\"chat1\"}"'
```

成功时应看到 HTTP 200，正文只含字符串字段 `output`，例如 `{"output":"我是 Agentkit-01。"}`。具体措辞由目标智能体决定。

如果目标只提供 `/invoke`，到这里就验证了普通回复。要测试追问，可以把第一条命令的消息改为“我刚才请你做了什么？”。保留相同的 `user_id` 和 `session_id`。目标服务需要保存该会话。

**可选：验证流式回复。** 目标支持 ADK 会话接口和 `/run_sse` 时，才执行下面的命令。它沿用上一条请求的两个 ID。省略 `user_id` 时使用 `plugin_user`，省略 `session_id` 时每次生成新 ID。

```bash
curl -sS -i -N http://127.0.0.1:8000/ \
  -H 'Content-Type: application/json' \
  --data-binary '{"message":"我刚才请你做了什么？","user_id":"user1","session_id":"chat1","streaming":true}'
```

`-i` 显示响应头，`-N` 让事件即时显示。检查 `Content-Type` 的值恰为 `text/event-stream`，没有 `charset`。每个 `message` 的 `content` 是一段可见文本。成功时最后一个事件是 `close`，例如：

```text
event: message
data: {"content":"你刚才请我介绍自己。"}

event: close
data: closed
```

流开始后若上游出错，最后一个事件是 `error`。读取 `error_msg`，将本次回复标为失败。即使 HTTP 状态是 200 或已经收到部分文本，也要检查终止事件。若上游最终文本改写了已发送的内容，流会以 `error` 结束。可用普通请求重新调用，取得该次调用的完整文本。

```text
event: error
data: {"error_msg":"上游 Agent 执行失败"}
```

只检查本地处理逻辑时，在本目录运行 `python -m unittest discover -s tests -v`。测试使用模拟上游。

## 4. 部署适配器并接入 Hi Agent

1. 在本目录用已配置的 AgentKit CLI 执行 `ak config -i`。给适配器起独立的部署名称。选择 Python，入口填 `plugin_server.py`，依赖文件填 `requirements.txt`，部署方式选 `cloud`，Runtime 鉴权选 `key_auth`。
2. 在适配器的云端环境变量中填写目标的 `UPSTREAM_BASE_URL` 和 `UPSTREAM_API_KEY`。若目标 ADK 应用名有变，也设置 `UPSTREAM_APP_NAME`。镜像不会包含本地 `.env`。运行 `ak launch`。
3. 打开**适配器 Runtime** 的「快速调用」，复制它的 Endpoint 和 API Key。在 Hi Agent 新建 HTTP 插件，方法选 `POST`，URL 填适配器的完整 Endpoint 加 `/`。设置 `Content-Type: application/json` 和 `Authorization: Bearer <适配器 Runtime 的 API Key>`。插件使用适配器的凭证，适配器访问目标时使用第 2 步的凭证。
4. 添加必填字符串 `message`。普通调用将响应字段 `output` 设为字符串。多轮调用再添加字符串 `user_id` 和 `session_id`。如果还要使用流式调用，添加可选布尔值 `streaming`，用 `streaming=true` 验证 `message` 和 `close` 事件。
5. 发布插件，把工具添加到 Hi Agent 智能体。在对话中发送「请调用这个工具，让远程智能体介绍自己，并转述它的回复」。在工具调用记录中查看结果。示例目标会提到 `Agentkit-01`。使用自有目标时，按其实际回答核对。

## 故障排查

普通请求失败或流建立前失败时，先看 HTTP 状态和 JSON 中的 `detail`。流建立后看末尾事件。

| 现象 | 如何定位 |
| --- | --- |
| 401 / 403 | 检查插件 Header 中的适配器 Key。若 `detail` 表示「上游 Runtime 返回 HTTP …」，检查适配器环境中的目标 Key 与目标 Endpoint 是否配对。 |
| 普通调用成功，流式调用返回 404 | 检查目标 ADK 应用名、会话创建接口和 `/run_sse`。普通根路径调用只经过 `/invoke`。 |
| 422 | 检查 `message` 是否为非空白字符串，ID 是否适合放入请求头和 URL 路径。流式请求使用根路径和 `streaming=true`。 |
| 503 / 502 / 504 | 若提示缺少 Key，配置适配器的 `UPSTREAM_API_KEY`。连接失败或超时时，从适配器所在网络检查目标 Endpoint。若提示回复格式无效或没有文本，检查目标返回的 ADK 事件。 |
| 插件看不到文本或回复中断 | 用上述 `curl -i -N` 检查适配器的响应头、`message.content` 和最后一个事件。若终止事件为 `error`，查看 `error_msg`。只收到部分文本且缺少终止事件时，检查连接是否中断。 |

## 代码许可

[Apache 2.0](../../../../../LICENSE)
