# Bedrock AgentCore 迁移 AgentKit Runtime 示例

## 概述

本项目演示如何将已有 Bedrock AgentCore Runtime 项目适配到 AgentKit Runtime。

示例模拟一个用户已有的 AgentCore Runtime 客服 agent。原项目入口是 `agent.py:app`，类型为 `BedrockAgentCoreApp`。`@app.entrypoint` 后面运行一个 Strands Agent，提供商品查询和退货政策两个本地工具。

迁移时不需要改写原有 AgentCore 入口。`agentkit migrate` 会生成 `agentkit_app.py` 和 `.agentkit/` 配置，生成后的 Runtime 应用通过 `BedrockAgentCoreAgentkitBridge` 调用原始 `agent.py:app`。

## 核心功能

- 展示 Bedrock AgentCore Runtime `BedrockAgentCoreApp` 入口如何被 AgentKit Runtime 调用。
- 保留 `@app.entrypoint` 业务入口，内部继续运行 Strands Agent。
- 使用 `@tool` 声明本地商品查询和退货政策工具。
- 使用 Strands `OpenAIModel` 创建 OpenAI-compatible 模型，兼容 `MODEL_AGENT_NAME`、`MODEL_AGENT_API_BASE` 和 `MODEL_AGENT_API_KEY`。
- 本地 tools 使用最小 mock 数据，重点展示迁移结构而不是业务复杂度。

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
agent.py:app  # BedrockAgentCoreApp
    ↓
@app.entrypoint invoke
    ↓
Strands Agent
    ├── OpenAIModel
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
└── requirements.txt   # Python 依赖列表，分为原生 AgentCore agent 和 AgentKit 运行时两段
```

`agentkit migrate` 执行后会在当前目录生成 `agentkit_app.py` 和 `.agentkit/` 目录。生成文件不需要提前提交到样例源码中。

## 本地运行

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

复制 `.env.example` 为 `.env`，保留需要的模型变量 key，使用 dotenv 空值形式：

```text
MODEL_AGENT_NAME=
MODEL_AGENT_API_BASE=
MODEL_AGENT_API_KEY=
```

实际模型配置通过 shell 环境变量提供：

```bash
export MODEL_AGENT_NAME=
export MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/responses
export MODEL_AGENT_API_KEY=
```

当前代码在配置 `MODEL_AGENT_NAME` 和 `MODEL_AGENT_API_KEY` 后使用 Strands `OpenAIModel` 创建模型，provider 已由 `OpenAIModel` 类决定，因此不需要 `MODEL_AGENT_PROVIDER`。`MODEL_AGENT_API_BASE` 可以使用 Ark Responses endpoint，样例传给 `OpenAIModel` 前会归一化为 OpenAI-compatible API root `https://ark.cn-beijing.volces.com/api/v3`。

如使用火山引擎国内版，将账号 AK/SK 导入环境变量：

```bash
export VOLCENGINE_ACCESS_KEY=
export VOLCENGINE_SECRET_KEY=
```

如使用 BytePlus 海外版 AgentKit，导入以下环境变量：

```bash
export BYTEPLUS_ACCESS_KEY=
export BYTEPLUS_SECRET_KEY=
export CLOUD_PROVIDER=byteplus
export BYTEPLUS_REGION=ap-southeast-1
```

账号凭证不写入 `.env.example` 或 `.env`，也不被原生 AgentCore 业务 agent 读取。

运行 `python agent.py` 或执行带 `--verify` 的迁移校验前，需要配置 `MODEL_AGENT_NAME` 和 `MODEL_AGENT_API_KEY`。未配置时，样例会抛出清晰错误，避免把本地假模型和真实 Strands 调用链路混在一起。

### 调试方法

直接启动原生 Bedrock AgentCore Runtime 本地服务：

```bash
python agent.py
```

服务启动后可以用 AgentCore 原生 `/invocations` 协议调用：

```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt":"PROD-002 这款智能手表多少钱？如果不合适可以退货吗？"}'
```

也可以使用迁移后的 Runtime 应用进行调试。先执行迁移命令：

```bash
agentkit migrate . \
  --framework agentcore \
  --entry agent.py:app \
  --name migration-agentcore-strands \
  --verify \
  --force
```

参数含义如下：

- `--framework agentcore`：按 Bedrock AgentCore Runtime entrypoint 方式迁移。
- `--entry agent.py:app`：指定原生 `BedrockAgentCoreApp` 入口。
- `--verify`：生成后执行基础校验。
- `--force`：如已存在生成文件，则覆盖旧的生成结果。

注意这里不是 `--framework strands`。虽然业务 agent 使用 Strands 编写，但待迁移的项目入口是 `BedrockAgentCoreApp`。

`agentkit migrate` 对 AgentCore 项目可能会提示没有启用 model replacement。这个样例没有构造 `BedrockModel` 或 `AnthropicModel`，模型层已经显式使用 Strands `OpenAIModel` 和 `MODEL_AGENT_*` 环境变量，因此不需要额外传 `--model-id`。

## AgentKit 部署

确认 `.agentkit/agentkit.yaml` 后执行：

```bash
agentkit deploy
```

部署后，Runtime 入口是 `agentkit_app.py`，业务逻辑仍由 `agent.py:app` 后面的 AgentCore entrypoint、Strands Agent 和原有 tools 执行。

部署时需要在部署环境中提供模型相关环境变量；账号凭证继续按上面火山引擎或 BytePlus 版本导入环境变量：

```bash
export MODEL_AGENT_NAME=
export MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/responses
export MODEL_AGENT_API_KEY=
```

## 示例提示词

- PROD-002 这款智能手表多少钱？如果不合适可以退货吗？
- 我想买耳机，帮我查一下产品信息和退货政策。

## 效果展示

运行示例提示词后，agent 会调用本地商品资料和退货政策工具，并输出商品价格、分类、质保和退货规则。

```text
Smart Watch 的价格是 $249.99，分类是 electronics，质保 24 months。
electronics 的退货政策是 30-day return window，非质量问题退货需要保留原包装。
```

## 常见问题

- 为什么这个样例不用 BedrockModel？

  为了和本项目其他 migration demo 的环境变量保持一致，样例使用 Strands `OpenAIModel` 调用 OpenAI-compatible 模型。这样可直接复用 `MODEL_AGENT_NAME`、`MODEL_AGENT_API_BASE` 和 `MODEL_AGENT_API_KEY`。

- 没有模型环境变量怎么办？

  `agent.py` 会抛出清晰错误。请先配置 `MODEL_AGENT_NAME` 和 `MODEL_AGENT_API_KEY`，或只执行不导入运行源 agent 的迁移 dry-run。

- 迁移命令会改写原有 `agent.py` 吗？

  不会。迁移命令会新增 Runtime 适配文件，原有 AgentCore 业务入口保持不变。

## 代码许可

本工程遵循 Apache 2.0 License。
