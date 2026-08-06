# Google ADK 迁移 AgentKit Runtime 示例

## 概述

本项目演示如何将已有 Google ADK 项目接入 AgentKit Runtime。

本示例用 `agent.py` 模拟一个已有的 Google ADK 旅行规划项目，展示如何将它迁移到 AgentKit Runtime。

本 demo 会引导您完成 Google ADK 项目的适配，生成可部署到 AgentKit Runtime 的产物，并最终完成部署。

## 核心功能

- 展示已有 Google ADK Agent 如何接入 AgentKit Runtime。
- 使用 Google ADK `Agent` 组织模型、提示词和工具。
- 使用本地函数声明旅行资料检索、预算估算和交通建议工具。
- 保留原生 Google ADK 业务代码，并通过 `agentkit migrate` 生成 Runtime 接入文件和配置。

## Agent 能力

本示例包含以下本地工具：

- `search_travel_notes`：检索内置城市旅行资料。
- `estimate_trip_budget`：按城市、天数和总预算估算预算是否宽松。
- `recommend_transport`：根据城市和同行人类型给出交通建议。

迁移后的调用链路如下：

```text
用户问题
    ↓
AgentKit Runtime
    ↓
agentkit_app.py
    ↓
AgentkitAgentServerApp
    ↓
agent.py:root_agent
    ├── Agent
    ├── search_travel_notes
    ├── estimate_trip_budget
    └── recommend_transport
```

## 目录结构说明

```bash
google_adk/
├── .env.example       # 模型配置环境变量示例
├── README.md          # 中文说明文档
├── README_en.md       # 英文说明文档
├── agent.py           # 原生 Google ADK Agent 和本地工具
└── requirements.txt   # Python 依赖列表
```

`agentkit migrate` 执行后会在当前目录生成 `agentkit_app.py` 和 `.agentkit/` 目录。生成文件不需要提前提交到样例源码中。

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

请确保 Python 版本不低于 3.12。进入当前样例目录后执行：

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

当前示例使用 Google ADK `OpenAILlm` 创建模型，因此不需要配置 `MODEL_AGENT_PROVIDER`，确保您的模型接入点支持 OpenAI 格式即可。

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
在执行迁移之前，先确保原来的 Google ADK 项目正常且可运行：

```bash
python agent.py
```

该命令会通过 ADK `Runner` 调用 `agent.py:root_agent`，向 Agent 发送固定旅行问题，并使用配置的 OpenAI-compatible 模型完成一次真实对话。

### 执行迁移命令
确认原项目可执行后，运行迁移命令生成 AgentKit Runtime 接入文件和配置：
```bash
agentkit migrate . \
  --framework adk \
  --entry agent.py:root_agent \
  --name migration-google-adk-travel \
  --verify
```

等价的 `ak` 命令：

```bash
ak migrate . \
  --framework adk \
  --entry agent.py:root_agent \
  --name migration-google-adk-travel \
  --verify
```

参数含义如下：

- `--framework adk`：按 Google ADK Agent 方式迁移。
- `--entry agent.py:root_agent`：指定原生 Google ADK Agent 入口。
- `--name migration-google-adk-travel`：指定生成的 AgentKit 应用名称。
- `--verify`：生成后执行基础校验。

Google ADK 迁移不需要 `--input-key`。迁移命令会生成 Runtime 接入文件，继续调用原生 `root_agent`，不会改写 `agent.py`。

执行成功后，会生成可部署到 AgentKit Runtime 的入口文件和配置。
迁移过程不会改写原有的 Google ADK `agent.py`。

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

- 我想带父母去北京玩 3 天，总预算 3000 元，喜欢历史文化、胡同和老北京美食，行程轻松一点。请帮我规划每天的景点、美食和交通建议。
- 我想去成都玩 2 天，预算 2000 元，喜欢美食和城市街区，请安排一个轻松路线。

## 效果展示

运行示例提示词后，Agent 会通过 Google ADK 调用本地旅行资料、预算和交通工具，并输出按天拆分的旅行规划，内容包含景点安排、餐饮建议、预算判断和交通建议。

```text
北京3天旅行规划（示例模型输出）

需求摘要：偏好历史文化, 胡同街区, 当地美食, 轻松慢游。
预算建议：北京3天总预算3000元，人均每日约1000元，预算判断：比较宽松。
```

## 常见问题

- 迁移命令会改写原有 `agent.py` 吗？

  不会。迁移命令会新增 Runtime 接入文件，原有 Google ADK 业务入口保持不变。

## 代码许可

本工程遵循 Apache 2.0 License。
