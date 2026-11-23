# 通过 A2A Client 从 AgentKit 调用 Hi Agent

[English](README_en.md) · [返回双向调用示例](../README.md)

## 调用链路

**外部调用方 → AgentKit Runtime 上的服务→ 直接使用A2A Client → Hi Agent 智能体**

外部向 Runtime 发送 HTTP 或 JSON-RPC 请求，服务通过 A2A 直接调用 Hi Agent，并把远端结果返回给调用方。回复由 Hi Agent 生成，本服务无需配置模型。

代码分为两个文件：[a2a_server.py](a2a_server.py) 提供接口，[a2a_tool.py](a2a_tool.py) 读取 Agent Card、携带渠道 Key 调用远端。两个入口共用同一个客户端。

| 外部请求 | 服务的处理方式 |
| --- | --- |
| `POST /HiAgent_a2a_http` | 将 `prompt` 转成 A2A 消息，返回远端的 `Task` 或 `Message`。 |
| `POST /HiAgent_a2a_client` | 接收标准 A2A JSON-RPC，结果放在响应的 `result` 中。 |

## 1. 在 Hi Agent 获取卡片和 Key

1. 选择要调用的 Hi Agent 智能体，记下它的自我介绍，供后续核对。
2. 将智能体发布到 **A2A 服务**渠道。从同一渠道导出完整 **Agent Card**，复制渠道 **API Key**。
3. 将卡片保存为本目录的 `remote_agentcard.json`。检查卡片中的服务地址，本机和部署后的 Runtime 都需要能访问它。

## 2. 在本地启动服务

从仓库根目录运行以下命令。示例使用 Python 3.12。

```bash
cd python/01-tutorials/01-agentkit-runtime/call_hiagent/a2a_client
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

在 `.env` 中填写 Hi Agent 的渠道 Key。

| 变量 | 填写内容 |
| --- | --- |
| `HI_AGENT_API_KEY` | 第 1 步的 Hi Agent A2A 渠道 Key。服务将它放入发往 Hi Agent 的 `Apikey` 请求头。 |
| `HOST`、`PORT` | 本地默认使用 `127.0.0.1` 和 `8000`，可按需修改。 |

运行 `python a2a_server.py`。默认地址是 `http://127.0.0.1:8000`。以下请求在另一终端执行，会调用真实的 Hi Agent 智能体。

## 3. 检查 HTTP 和 JSON-RPC 回复

先设置调用地址。本地服务不校验入站 Key，`APIKEY` 留空即可。

```bash
export BASE_URL='http://127.0.0.1:8000'
export APIKEY=''
```

**普通 HTTP。** 发送一句“请介绍一下你自己。”。

```bash
curl -sS --fail-with-body --max-time 65 "$BASE_URL/HiAgent_a2a_http" \
  -H "Authorization: Bearer $APIKEY" \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"请介绍一下你自己。"}'
```

成功时返回远端的 `Task` 或 `Message`。对于任务结果，检查 `status.state` 和 `artifacts[].parts`：`completed` 表示任务完成，文本应与第 1 步的自我介绍一致。若直接返回消息，文本在 `parts` 中。

**标准 A2A JSON-RPC。** 用 `message/send` 发送相同的问题。

```bash
curl -sS --fail-with-body --max-time 65 "$BASE_URL/HiAgent_a2a_client" \
  -H "Authorization: Bearer $APIKEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc":"2.0",
    "id":"request-1",
    "method":"message/send",
    "params":{
      "message":{
        "role":"user",
        "messageId":"message-1",
        "parts":[{"kind":"text","text":"请介绍一下你自己。"}]
      },
      "configuration":{"blocking":true}
    }
  }'
```

响应的 `id` 应为 `request-1`。任务状态和回复位于 `result.status.state`、`result.artifacts[].parts`；直接返回消息时读取 `result.parts`。具体措辞由远端智能体决定。即使 HTTP 状态是 200，也要检查是否有 JSON-RPC `error`。

每条新消息使用新的 `messageId`。要测试追问，将问题改为“我刚才请你做了什么？”，并传入上一条回复的 `contextId`：HTTP 使用字段 `context_id`，JSON-RPC 放在 `message.contextId`。目标智能体需要保留该会话。

## 4. 部署服务并从外部调用

1. 在本目录用已配置的 AgentKit CLI 执行 `ak config -i`。应用名称可填 `hiagent_a2a_server`，选择 Python，入口填 `a2a_server.py`，依赖文件填 `requirements.txt`，部署方式选 `cloud`，Runtime 鉴权选 `key_auth`。
2. 将应用类型设为 `WebServer App`。如果 CLI 没有该选项，在生成的 `agentkit.yaml` 中将 `common` 下的 `agent_type` 设为 `WebServer App`。
3. 在 Runtime 环境变量中填写第 2 步的 Hi Agent 渠道 Key。通过 `HOST` 和 `PORT` 将监听地址配置为 `0.0.0.0:8000`。确认 `remote_agentcard.json` 在本目录，运行 `ak launch`。Dockerfile 会复制两个 Python 文件和卡片，本地 `.env` 不进入镜像。
4. 打开新部署的 **调用方 Runtime** 的「快速调用」，复制完整 Endpoint 和 API Key。替换下面的 Endpoint，并在空引号中填写 Runtime Key，再执行第 3 步的两条 curl，核对任务状态和 Hi Agent 回复。

```bash
export BASE_URL='https://<网关域名>/runtime/<Runtime ID>'
export APIKEY=''
```

Endpoint 保留 `/runtime/<id>` 前缀，末尾不要加 `/`。这里的 `APIKEY` 用于访问 AgentKit 网关；服务端的 `HI_AGENT_API_KEY` 用于访问 Hi Agent。

**可选：供标准 A2A Client 自动发现。** 将 Runtime 环境变量 `PUBLIC_BASE_URL` 设为完整 Endpoint 并使配置生效。客户端从 `/HiAgent_a2a_client/.well-known/agent-card.json` 读取卡片；读取卡片和发送消息都使用前面 curl 中的 `Authorization` 请求头。

## 故障排查

HTTP 请求失败时，查看状态码和 JSON 中的 `detail`；JSON-RPC 请求失败时，查看 `error`。远端返回 `input-required` 表示需要补充信息，应继续该会话。

| 现象 | 如何定位 |
| --- | --- |
| 服务启动失败 | 检查 `remote_agentcard.json` 是否完整，以及 `HI_AGENT_API_KEY` 是否已填写。 |
| 云端返回 401 / 403 | 检查 `BASE_URL` 和 `APIKEY` 是否来自同一个调用方 Runtime。 |
| HTTP 返回 422 | 检查 `prompt` 是否为非空白字符串。 |
| HTTP 返回 502 或 JSON-RPC 返回 `error` | 检查 Hi Agent 卡片与渠道 Key 是否配对，以及远端服务是否可用。 |
| HTTP 返回 504 | 远端调用超过 60 秒。从服务所在网络检查卡片中的 Hi Agent 地址。 |
| Agent Card 中仍是本地地址 | 检查 Runtime 的 `PUBLIC_BASE_URL`，保留完整网关路径。 |

## 代码许可

[Apache 2.0](../../../../../LICENSE)
