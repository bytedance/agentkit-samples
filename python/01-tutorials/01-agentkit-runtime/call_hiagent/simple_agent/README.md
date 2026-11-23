# 部署供 Hi Agent 调用的 AgentKit 智能体

[双向调用示例](../README.md) · [English](README_en.md)

## 在调用链中的位置

本目录实现 AgentKit 上的目标智能体 `simple_agent`。Hi Agent 有两条路径可以调用它。

- **MCP 路径（POC 2）**　Hi Agent 的 MCP 插件 → [MCP Server](../mcp_server/README.md) → `simple_agent`（A2A）。
- **HTTP 补充路径**　Hi Agent 的 HTTP 插件 → [HTTP 适配器](../http_plugin/README.md) → `simple_agent`（HTTP）。

两条路径可以共用一个目标 Runtime。`simple_agent` 生成回复，再由对应的服务传回 Hi Agent。示例给智能体设定了一句自我介绍“我是Agentkit-01”，方便在 Hi Agent 的工具记录中认出它。

已有兼容的目标 Runtime 时，可直接从第 4 步接入。MCP 需要可访问的 A2A 服务、Agent Card 和文本回复。HTTP 普通调用使用目标的 `/invoke`，流式调用还需要会话接口和 `/run_sse`。使用自己的智能体时，先记下它的自我介绍，供后续核对。

## 1. 安装依赖并配置模型

以下命令使用 Python 3.12。从样例仓库根目录开始，后续命令在 `simple_agent/` 中执行。

```bash
cd python/01-tutorials/01-agentkit-runtime/call_hiagent/simple_agent
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

在模型服务的控制台打开已开通模型的 API 调用示例，填写 `.env`。

| 变量 | 填写内容 |
| --- | --- |
| `MODEL_AGENT_NAME` | 模型名或推理接入点 ID |
| `MODEL_AGENT_API_BASE` | 模型服务的 OpenAI 兼容 API 基址。保留版本路径，去掉末尾的 `/chat/completions` |
| `MODEL_AGENT_API_KEY` | 有权调用该模型的 API Key |

## 2. 检查本地回复和服务入口

```bash
python veadk_agent.py
```

脚本会发送「请你介绍自己」。检查终端回复是否包含「我是Agentkit-01」。

再启动部署时使用的服务入口。

```bash
python agent_server.py
```

在另一个终端读取应用列表和 Agent Card。

```bash
curl -fsS http://127.0.0.1:8000/list-apps
curl -fsS http://127.0.0.1:8000/.well-known/agent-card.json
```

应用列表应包含 `simple_agent`，卡片的 `name` 也应为 `simple_agent`。正向调用示例 `a2a_caller` 也用了这个名字。检查服务是从本目录启动的，再用上面的自我介绍核对身份。完成后在服务终端按 Ctrl+C 停止服务。

## 3. 部署并取得目标 Runtime 的地址和 Key

用已登录的 AgentKit CLI（`ak`）在有 Runtime 部署权限的项目中操作。在 `simple_agent/` 运行 `ak config -i`。

| 配置项 | 填写内容 |
| --- | --- |
| 应用名称 | 给目标取独立名称，例如 `hiagent-demo-target` |
| 语言、入口、依赖 | `Python`、`agent_server.py`、`requirements.txt` |
| 部署方式与鉴权 | `cloud`、目标项目和地域、`key_auth` |
| Runtime 环境变量 | 第 1 步的三个模型变量。本地 `.env` 不会打入镜像 |

保存配置后，在同一目录部署。

```bash
ak launch
```

在刚部署的目标 Runtime 的在线测试中发送「请你介绍自己」。收到包含「我是Agentkit-01」的回复后，打开该 Runtime 的「快速调用」，复制完整的 **Endpoint** 和 **API Key**。保留 Endpoint 中的网关路径和 `/runtime/<id>`。如果在线测试报模型鉴权错误，先核对该 Runtime 的三个模型变量。

## 4. 将目标接入 Hi Agent

在目标 Runtime 的「快速调用」取得的 Endpoint 和 Key 供下列组件访问目标。按需要选择一种方式。

- **MCP 工具**。用目标 Key 下载目标的 Agent Card，保存到 `../mcp_server/remote_agentcard.json`。将同一把 Key 填入 MCP Server 的 `AGENTKIT_RUNTIME_API_KEY`。卡片下载命令和插件配置见 [MCP 接入步骤](../mcp_server/README.md)。
- **HTTP 插件**。将目标 Endpoint 和 Key 分别填入适配器的 `UPSTREAM_BASE_URL` 和 `UPSTREAM_API_KEY`。如果目标的内部应用名与 `simple_agent` 不同，在使用会话接口时设置 `UPSTREAM_APP_NAME`。详见 [HTTP 插件接入步骤](../http_plugin/README.md)。

下载卡片遇到 401 时，核对请求头 `Authorization: Bearer <目标 Runtime Key>`。
