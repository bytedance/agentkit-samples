# Google ADK 迁移 AgentKit Runtime 示例

## 概述

本项目演示如何将已有 Google ADK 项目适配到 AgentKit Runtime。

示例模拟一个用户已有的 Google ADK 旅行规划项目。原项目入口是 `agent.py:root_agent`，类型为 `google.adk.agents.Agent`。它使用 Google ADK `Agent` 注册模型、系统提示词和本地旅行工具，接收旅行问题后由 ADK agent 调用工具并生成景点、美食、预算和交通建议。

为兼容更直观的入口写法，代码也提供了 `agent.py:agent` 作为 `root_agent` 的别名。README 中迁移命令使用 Google ADK 常见的 `root_agent` 入口。

## 核心功能

- 展示原生 Google ADK agent 入口如何被 AgentKit Runtime 包装。
- 保留原生业务代码，通过 `agentkit migrate` 生成 `agentkit_app.py` 和 `.agentkit/` 配置，进行Google ADK项目的Agentkit适配。
- 展示如何通过Agentkit Deploy，将迁移后的产物部署到Agentkit Runtime中。

## Agent 能力

为了更好的模拟用户使用场景，本示例的Google ADK Agent包含以下工具：

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
agent.py:root_agent  # Google ADK Agent
    ├── search_travel_notes
    ├── estimate_trip_budget
    └── recommend_transport
```

## 目录结构说明

```bash
google_adk/
├── .env.example       # 方舟模型配置环境变量示例
├── README.md          # 中文说明文档
├── README_en.md       # 英文说明文档
├── agent.py           # 原生 Google ADK Agent 和本地 tools
├── project.yaml       # 项目信息元数据
└── requirements.txt   # Python 依赖列表，分为原生 ADK 和 AgentKit 迁移运行时两段
```

`agentkit migrate` 执行后会在当前目录生成 `agentkit_app.py` 和 `.agentkit/` 目录。生成文件不需要提前提交到样例源码中。

## 本地运行

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

通过环境变量，进行下列相关参数的配置：

```bash
export MODEL_AGENT_NAME=
export MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3
export MODEL_AGENT_API_KEY=
```

当前代码使用原生 Google ADK `Agent`，并通过 ADK `OpenAILlm` 接入 OpenAI-compatible 方舟模型。`MODEL_AGENT_API_BASE` 可以使用 Ark Responses endpoint，样例传给 OpenAI SDK 前会归一化为 OpenAI-compatible API root `https://ark.cn-beijing.volces.com/api/v3`。


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


### 调试方法

直接运行原生项目：

```bash
python agent.py
```

该命令会通过 ADK `Runner` 调用 `agent.py:root_agent`，向 agent 发送固定问题 `我想去北京玩3天`，并使用配置的 Ark OpenAI-compatible 模型完成一次真实对话。

也可以使用迁移后的 Runtime 应用进行调试。先执行迁移命令：

```bash
agentkit migrate . \
  --framework adk \
  --entry agent.py:root_agent \
  --name migration-google-adk-travel \
  --verify
```

参数含义如下：

- `--framework adk`：按 Google ADK Agent 方式迁移。
- `--entry agent.py:root_agent`：指定原生 Google ADK agent 入口。
- `--name migration-google-adk-travel`：指定生成的 AgentKit 应用名称。
- `--verify`：生成后执行基础校验。

Google ADK 迁移不需要 `--input-key`。迁移命令会生成 `AgentkitAgentServerApp` 包装原生 `root_agent`，不会改写 `agent.py`。

## AgentKit 部署

确认 `.agentkit/agentkit.yaml` 后执行：

```bash
agentkit deploy
```

部署后，Runtime 入口是 `agentkit_app.py`，业务逻辑仍由原始 `agent.py:root_agent` 和本地 tools 执行。

部署时需要在部署环境中提供原生 Google ADK 模型运行所需变量；账号凭证继续按上面火山引擎或 BytePlus 版本导入环境变量：

```bash
export MODEL_AGENT_NAME=
export MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/responses
export MODEL_AGENT_API_KEY=
```

## 示例提示词

- 我想带父母去北京玩 3 天，总预算 3000 元，喜欢历史文化、胡同和老北京美食，行程轻松一点。请帮我规划每天的景点、美食和交通建议。
- 我想去成都玩 2 天，预算 2000 元，喜欢美食和城市街区，请安排一个轻松路线。

## 效果展示

运行 `python agent.py` 后会调用 `root_agent` 并输出模型返回的旅行规划结果。示例问题固定为：

```text
我想去北京玩3天
```

## 常见问题

- 为什么没有 `MODEL_AGENT_PROVIDER`？

  本示例使用原生 Google ADK `Agent` 和 ADK `OpenAILlm`。provider 已由 `OpenAILlm` 以及 `MODEL_AGENT_API_BASE` 指向的 Ark OpenAI-compatible endpoint 决定，不需要单独配置 provider。

- 账号凭证要放在哪里？

  不写入 `.env.example` 或 `.env`。执行 `agentkit migrate` 或 `agentkit deploy` 前，按火山引擎或 BytePlus 版本导入对应环境变量即可。

- 迁移命令会改写原有 `agent.py` 吗？

  不会。迁移命令会新增 Runtime 适配文件，原有 Google ADK 业务入口保持不变。

## 代码许可

本工程遵循 Apache 2.0 License。
