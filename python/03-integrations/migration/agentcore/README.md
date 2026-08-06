# Bedrock AgentCore 迁移 AgentKit Runtime 示例

## 概述

本项目演示如何将已有 Bedrock AgentCore Runtime 项目接入 AgentKit Runtime。

本示例用 `agent.py` 模拟一个已有的 Bedrock AgentCore Runtime 客服项目，展示如何将它迁移到 AgentKit Runtime。

本 demo 会引导您完成 Bedrock AgentCore Runtime 项目的适配，生成可部署到 AgentKit Runtime 的产物，并最终完成部署。

## 核心功能

- 展示 Bedrock AgentCore Runtime `BedrockAgentCoreApp` 入口如何被 AgentKit Runtime 调用。
- 保留 `@app.entrypoint` 业务入口，内部继续运行 Strands Agent。
- 使用 Strands `Agent` 组织模型、提示词和工具。
- 使用 `@tool` 声明本地商品查询和退货政策工具。
- 保留原生 AgentCore 业务代码，并通过 `agentkit migrate` 生成 Runtime 适配层。

## Agent 能力

本示例包含以下本地工具：

- `get_product_info`：按商品 ID 查询内置商品资料。
- `get_return_policy`：按商品分类查询内置退货政策。

迁移后的调用链路如下：

```text
用户问题
    ↓
AgentKit Runtime
    ↓
agentkit_app.py
    ↓
BedrockAgentCoreAgentkitBridge
    ↓
agent.py:app
    ↓
@app.entrypoint invoke
    ↓
Strands Agent
    ├── get_product_info
    └── get_return_policy
```

## 目录结构说明

```bash
agentcore/
├── .env.example       # 模型配置环境变量示例
├── README.md          # 中文说明文档
├── README_en.md       # 英文说明文档
├── agent.py           # 原生 Bedrock AgentCore app、Strands Agent 和 tools
└── requirements.txt   # Python 依赖列表
```


## 本地运行

### 检查 AgentKit CLI 版本

请先确认本机安装的是 TypeScript 版本的 AgentKit CLI，且版本不低于 `0.51.1`：

```bash
agentkit -v
```

或者

```bash
ak -v
```

如未安装，或版本低于 `0.51.1`，可以使用以下命令安装 TypeScript 版本 AgentKit CLI：

```bash
curl https://agentkit-cli.tos-cn-beijing.volces.com/install.sh | sh
```

> 迁移命令建议使用 TypeScript AgentKit CLI 的 `ak` 入口，以避免 Python `uv` 环境或 `agentkit-python-sdk` 带来的同名 `agentkit` 命令冲突。`ak` 由安装脚本自动配置，无需额外操作。

### 依赖安装

请确保 Python 版本不低于 3.10。进入当前样例目录后执行：

```bash
pip install -r requirements.txt
```

也可以使用 `uv` 安装依赖：

```bash
uv pip install -r requirements.txt
```

### 环境准备

复制 `.env.example` 为 `.env`，并在 `.env` 中填写需要的模型配置：

```text
MODEL_AGENT_NAME=<model-name>
MODEL_AGENT_API_BASE=
MODEL_AGENT_API_KEY=<api-key>
```

AgentKit CLI 在运行前会自动加载 `.env` 到 AgentKit CLI 的环境变量中。当前 demo 使用 Strands `OpenAIModel` 创建模型，因此不需要配置 `MODEL_AGENT_PROVIDER`，确保您的模型接入点支持 OpenAI 格式即可。

如果需要将生成的产物部署到 AgentKit Runtime，则将对应平台的账号配置写入 `.env`。

火山引擎国内版：

```text
VOLCENGINE_ACCESS_KEY=<access-key>
VOLCENGINE_SECRET_KEY=<secret-key>
```

BytePlus 海外版 AgentKit：

```text
BYTEPLUS_ACCESS_KEY=<access-key>
BYTEPLUS_SECRET_KEY=<secret-key>
CLOUD_PROVIDER=byteplus
BYTEPLUS_REGION=ap-southeast-1
```

### 迁移前检查
在执行迁移之前，先确保原来的 AgentCore 项目正常且可运行：

```bash
python agent.py
```

服务启动后可以用 AgentCore 原生 `/invocations` 协议调用：

```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt":"PROD-002 这款智能手表多少钱？如果不合适可以退货吗？"}'
```

该命令会调用 `agent.py:app` 后面的 AgentCore entrypoint，向 Strands Agent 发送固定客服问题，并使用配置的 OpenAI-compatible 模型完成一次真实对话。

### 执行迁移命令
确认原项目可执行后，运行迁移命令生成 AgentKit Runtime 接入文件和配置：
```bash
agentkit migrate . \
  --framework agentcore \
  --entry agent.py:app \
  --name migration-agentcore-strands \
  --verify
```

等价的 `ak` 命令：

```bash
ak migrate . \
  --framework agentcore \
  --entry agent.py:app \
  --name migration-agentcore-strands \
  --verify
```

参数含义如下：

- `--framework agentcore`：按 Bedrock AgentCore Runtime entrypoint 方式迁移。
- `--entry agent.py:app`：指定原生 `BedrockAgentCoreApp` 入口。
- `--verify`：生成后执行基础校验。

注意这里不是 `--framework strands`。虽然业务 agent 使用 Strands 编写，但待迁移的项目入口是 `BedrockAgentCoreApp`。

执行成功后的产物即可直接部署到 AgentKit Runtime 上。
全过程对原本的 AgentCore `agent.py` 无侵入、无改造。

## AgentKit 部署

如果您想将生成的产物部署到 AgentKit Runtime 上，可以执行：

```bash
agentkit release
```

等价的 `ak` 命令：

```bash
ak release
```

部署后，即可在 AgentKit 平台的 Runtime 中找到部署的项目。

## 示例提示词

- PROD-002 这款智能手表多少钱？如果不合适可以退货吗？
- 我想买耳机，帮我查一下产品信息和退货政策。

## 效果展示

运行示例提示词后，Agent 会通过 Strands 调用本地商品资料和退货政策工具，并输出商品价格、分类、质保和退货规则。

```text
Smart Watch 的价格是 $249.99，分类是 electronics，质保 24 months。
electronics 的退货政策是 30-day return window，非质量问题退货需要保留原包装。
```

## 常见问题

- 迁移命令会改写原有 `agent.py` 吗？

  不会。迁移命令会新增 Runtime 适配文件，原有 AgentCore 业务入口保持不变。

## 代码许可

本工程遵循 Apache 2.0 License。
