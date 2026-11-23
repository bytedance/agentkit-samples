# 从 AgentKit 调用 Hi Agent 智能体

[双向调用示例](../README.md) · [English](README_en.md)

## 调用链路

**AgentKit Runtime 上的调用方（本目录）→ `remote_agent` 工具 → 私有云 Hi Agent 的 A2A 服务 → Hi Agent 智能体**

这是 POC 1 的调用方代码。AgentKit Runtime 在这里充当 Hi Agent 平台外的运行环境。调用方模型使用 `remote_agent` 工具，把任务发给 Hi Agent。Hi Agent 智能体处理请求，工具将回复交回调用方。

开始前，准备一个支持工具调用的模型。在 Hi Agent 中选择或新建一个测试智能体，按下一步发布为 A2A 服务。

## 1. 在 Hi Agent 获取卡片和 Key

1. 打开要调用的 Hi Agent 智能体。选一句能认出它的自我介绍，或专门为测试设置一句。
2. 将智能体发布到 **A2A 服务**渠道。从同一渠道导出完整的 **Agent Card**，并复制渠道的 **API Key**。
3. 将卡片保存为本目录的 `remote_agentcard.json`，与 `veadk_agent.py` 放在一起。检查卡片的 `url`。本机测试时，电脑要能访问该地址。部署之后，调用方 Runtime 也要能访问它。

## 2. 配置调用方模型和渠道 Key

以下命令使用 Python 3.12。从样例仓库根目录执行，后续操作均在 `a2a_caller/` 中完成。

```bash
cd python/01-tutorials/01-agentkit-runtime/call_hiagent/a2a_caller
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

在 `.env` 中填写四项。

| 变量 | 填写内容 |
| --- | --- |
| `MODEL_AGENT_NAME` | 调用方模型的名称或推理接入点 ID，可从模型服务的 API 调用示例中复制 |
| `MODEL_AGENT_API_BASE` | 该模型的 OpenAI 兼容 API 基址。保留版本路径，去掉末尾的 `/chat/completions` |
| `MODEL_AGENT_API_KEY` | 有权调用该模型的 API Key |
| `HI_AGENT_API_KEY` | 第 1 步的 Hi Agent A2A 渠道 Key。工具会将它放入 `Apikey` 请求头 |

## 3. 在本机调用 Hi Agent

```bash
python veadk_agent.py
```

脚本要求远端智能体自我介绍，并让调用方原样转述。核对终端输出中是否有第 1 步选定的短语。

要检查部署时使用的 HTTP 服务入口，再启动以下服务。

```bash
python agent_server.py
```

在另一个终端运行以下命令。

```bash
curl -fsS http://127.0.0.1:8000/list-apps
```

本例调用方和反向示例的目标智能体都使用 `simple_agent` 作为应用名。列表出现该名称只表示本地 HTTP 服务已启动。核对启动目录是 `a2a_caller/`，并用上面的自我介绍验证远端调用。检查完成后，在服务终端按 Ctrl+C 停止服务。

## 4. 部署调用方并核对工具记录

用已登录的 AgentKit CLI（`ak`）在有 Runtime 部署权限的项目中操作。在 `a2a_caller/` 运行 `ak config -i`。

| 配置项 | 填写内容 |
| --- | --- |
| 应用名称 | 给调用方取独立名称，例如 `hiagent-a2a-caller` |
| 语言、入口、依赖 | `Python`、`agent_server.py`、`requirements.txt` |
| 部署方式与鉴权 | `cloud`、目标项目和地域、`key_auth` |
| Runtime 环境变量 | 第 2 步的四个变量。本地 `.env` 不会打入镜像 |

确认 `remote_agentcard.json` 在当前目录，执行部署。

```bash
ak launch
```

打开刚部署的**调用方 Runtime**，在在线测试中发送「请调用远程 Agent，让它介绍自己，并原样转述」。检查调用记录中是否有 `remote_agent`，再核对工具返回的 Hi Agent 自我介绍。其他客户端如需访问此调用方，可从该 Runtime 的「快速调用」复制它的 Endpoint 和 API Key。

远端返回 401 时，检查卡片与 `HI_AGENT_API_KEY` 是否来自同一个 Hi Agent 智能体的 A2A 渠道。本机成功而云端超时时，检查调用方 Runtime 能否访问卡片中的地址。
