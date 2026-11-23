# 让 Hi Agent 通过 MCP 调用 AgentKit 智能体

[双向调用示例](../README.md) · [English](README_en.md)

## 调用链路

**Hi Agent 智能体 → Hi Agent 的 MCP 插件 → MCP Server（本目录）→ AgentKit 上的目标智能体（A2A）**

本目录实现 POC 2 的 MCP Server。它和目标智能体部署在不同的 AgentKit Runtime 上。Hi Agent 的 MCP 插件连接这个服务，发现并调用 `remote_agent_poc_hiagent(message)`。工具每次新建会话，通过 A2A 把消息发给目标智能体，再把最终文本返回给 Hi Agent。

目标 Runtime 要求读取 Agent Card 时携带凭证。示例使用的 Hi Agent 版本直接注册 A2A 服务时，无法为这一步设置鉴权请求头。通过 MCP 插件接入后，MCP Server 从预先下载的卡片读取地址，再用目标 Runtime 的 Key 发起调用。

## 1. 准备目标 Runtime

可以部署本教程的目标智能体，也可以复用已有的 AgentKit Runtime。目标需提供可访问的 A2A 服务、Agent Card 和文本回复。先在目标 Runtime 的在线测试中请它自我介绍，记下回复中的特征。本教程自带的目标会说「我是Agentkit-01」。[部署示例目标](../simple_agent/README.md)

从目标 Runtime 的「快速调用」复制完整 Endpoint 和 API Key。接下来会用到两把 Key。

| 调用方向 | 使用哪把 Key | 填在哪里 |
| --- | --- | --- |
| MCP Server → 目标智能体 | 目标 Runtime 的 Key | MCP Server 的 `AGENTKIT_RUNTIME_API_KEY` |
| Hi Agent → MCP Server | 第 4 步部署的 MCP Server Runtime 的 Key | Hi Agent 插件的 `Authorization` 请求头 |

## 2. 下载目标智能体的卡片

以下命令使用 Python 3.12。从样例仓库根目录开始，后续操作在 `mcp_server/` 中完成。

```bash
cd python/01-tutorials/01-agentkit-runtime/call_hiagent/mcp_server
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

在 `.env` 中将 `AGENTKIT_RUNTIME_API_KEY` 设为目标 Runtime 的 Key，只填 Key 本身。将下方的 `SIMPLE_AGENT_ENDPOINT` 换成目标的完整 Endpoint，然后下载 Agent Card。`source .env` 让当前终端能读取 Key。

```bash
SIMPLE_AGENT_ENDPOINT='https://<网关域名>/runtime/<目标 Runtime ID>'
source .env
curl -fsS -H "Authorization: Bearer ${AGENTKIT_RUNTIME_API_KEY}" \
  "${SIMPLE_AGENT_ENDPOINT%/}/.well-known/agent-card.json" -o remote_agentcard.json
```

打开 `remote_agentcard.json`，核对 `url` 指向目标 Runtime，且 MCP Server 能访问它。如果示例目标的未签名卡片写着 `http://localhost:8000/`，将其换成目标的完整 Endpoint 加 `/`，保留 `/runtime/<id>`。同步修改 `additionalInterfaces` 中相同的本机地址。若卡片已签名，请发布方更新卡片。

## 3. 在本机调用工具

启动 MCP Server。

```bash
python mcp_server.py
```

在另一终端向本地 `/mcp` 发送 `tools/call`。工具会把 `message` 发给卡片指向的智能体。

```bash
curl -fsS http://127.0.0.1:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2025-11-25' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"remote_agent_poc_hiagent","arguments":{"message":"请介绍你自己"}}}'
```

检查响应的 `result.content`。示例目标的回复应包含「我是Agentkit-01」。自己的目标应返回第 1 步核对过的特征。若只想查看工具列表，将 `-d` 的值改为 `'{"jsonrpc":"2.0","id":1,"method":"tools/list"}'`。列出工具仅验证 MCP Server 可用。

## 4. 部署 MCP Server

用已登录的 AgentKit CLI（`ak`）在有 Runtime 部署权限的项目中操作。在 `mcp_server/` 运行 `ak config -i`。

| 配置项 | 填写内容 |
| --- | --- |
| 应用名称 | 给 MCP Server 取一个与目标 Runtime 不同的名字 |
| 语言、入口、依赖 | `Python`、`mcp_server.py`、`requirements.txt` |
| 部署方式与鉴权 | `cloud`、目标项目和地域、`key_auth` |
| Runtime 环境变量 | `AGENTKIT_RUNTIME_API_KEY` 设为**目标 Runtime 的 Key** |

保持 `remote_agentcard.json` 在本目录。Dockerfile 会将卡片打入镜像，本地 `.env` 仅用于本机测试。配置完成后执行部署。

```bash
ak launch
```

打开新部署的 **MCP Server Runtime** 的「快速调用」，复制它自己的 Endpoint 和 API Key，供 Hi Agent 连接。

## 5. 在 Hi Agent 添加并验证工具

1. 创建 **MCP 插件**。MCP 传输方式选 **Streamable HTTP**，URL 填 `<MCP Server Endpoint>/mcp`。
2. 鉴权选 **API Key**，位置选 **Header**，名称填 `Authorization`，值填 `Bearer <MCP Server Runtime 的 Key>`。
3. 点击「同步工具」，应看到 `remote_agent_poc_hiagent`。发布插件，把这个工具添加到 Hi Agent 智能体。
4. 在对话中发送「请调用 remote_agent_poc_hiagent，让远端智能体介绍自己」。打开工具调用记录，核对工具名和结果中的自我介绍是否与第 1 步一致。

同步时报 401，检查插件里的 MCP Server Key。同步成功、调用工具时报目标鉴权错误，检查 MCP Server 环境里的目标 Runtime Key。
