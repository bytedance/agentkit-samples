# Strands 迁移 AgentKit Runtime 示例

## 概述

本项目演示如何将已有 Strands 项目适配到 AgentKit Runtime。

示例模拟一个用户已有的 Strands 旅行规划项目。原项目入口是 `agent.py:agent`，类型为零参 Strands `Agent` factory。它使用 Strands `Agent` 注册模型、系统提示词和本地旅行工具，接收旅行问题后由 agent 结合城市资料、预算判断和交通建议，生成景点、美食、预算和交通安排。

迁移时不需要改写原有业务逻辑。`agentkit migrate` 会生成 `agentkit_app.py` 和 `.agentkit/` 配置，生成后的 Runtime 应用通过 `StrandsAgentkitBridge` 调用原始 `agent.py:agent`。

## 核心功能

- 展示 Strands `Agent` factory 入口如何被 AgentKit Runtime 调用。
- 使用 `@tool` 声明本地旅行资料检索、预算估算和交通建议工具。
- 使用 Strands `OpenAIModel` 创建真实模型；provider 由 `OpenAIModel` 类决定，不需要 `MODEL_AGENT_PROVIDER`。
- 保留原生 Strands 业务代码，并通过 `agentkit migrate` 生成 Runtime 适配层。

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
StrandsAgentkitBridge
    ↓
agent.py:agent  # zero-argument factory that creates a Strands Agent
    ├── OpenAIModel / local demo model
    ├── search_travel_notes
    ├── estimate_trip_budget
    └── recommend_transport
```

## 目录结构说明

```bash
strands/
├── .env.example       # 模型配置环境变量示例
├── README.md          # 中文说明文档
├── README_en.md       # 英文说明文档
├── agent.py           # 原生 Strands Agent factory、tools 和模型配置
└── requirements.txt   # Python 依赖列表，分为原生 agent 和 AgentKit 运行时两段
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

账号凭证不写入 `.env.example` 或 `.env`，也不被原生 Strands agent 业务代码读取。

如果没有配置模型环境变量，样例会使用本地 demo model，便于直接查看迁移前后的调用链路。

### 调试方法

直接运行原生 Strands Agent：

```bash
python agent.py
```

该命令会创建 `agent.py:agent` 返回的 Strands Agent，向 agent 发送固定旅行问题，并输出可读的旅行规划结果。

也可以使用迁移后的 Runtime 应用进行调试。先执行迁移命令：

```bash
agentkit migrate . \
  --framework strands \
  --entry agent.py:agent \
  --name migration-strands-travel \
  --verify 
```

参数含义如下：

- `--framework strands`：按 Strands Agent 方式迁移。
- `--entry agent.py:agent`：指定原生 Strands Agent 零参 factory 入口。
- `--verify`：生成后执行基础校验。

## AgentKit 部署

确认 `.agentkit/agentkit.yaml` 后执行：

```bash
agentkit deploy
```

部署后，Runtime 入口是 `agentkit_app.py`，业务逻辑仍由 `agent.py:agent` 创建的 Strands Agent 和原有 tools 执行。

部署时需要在部署环境中提供模型相关环境变量；账号凭证继续按上面火山引擎或 BytePlus 版本导入环境变量：

```bash
export MODEL_AGENT_NAME=
export MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/responses
export MODEL_AGENT_API_KEY=
```

## 示例提示词

- 我想带父母去北京玩 3 天，总预算 3000 元，喜欢历史文化、胡同和老北京美食，行程轻松一点。请帮我规划每天的景点、美食和交通建议。
- 我想去西安玩 2 天，预算 1800 元，喜欢历史遗迹和当地小吃，请安排一个不太累的路线。

## 效果展示

运行示例提示词后，agent 会调用本地旅行资料、预算和交通工具，并输出按天拆分的旅行规划，内容包含景点安排、餐饮建议、预算判断和交通建议。

```text
北京3天旅行规划（示例模型输出）

第1天：故宫博物院，餐饮可安排北京烤鸭，节奏保持轻松。
第2天：天坛公园，餐饮可安排炸酱面，节奏保持轻松。
```

## 常见问题

- 没有模型环境变量怎么办？

  样例会使用本地 demo model 返回可读结果；配置 `MODEL_AGENT_NAME`、`MODEL_AGENT_API_BASE` 和 `MODEL_AGENT_API_KEY` 后，会改用真实 Strands `OpenAIModel`。

- 账号凭证要放在哪里？

  不写入 `.env.example` 或 `.env`。执行 `agentkit migrate` 或 `agentkit deploy` 前，按火山引擎或 BytePlus 版本导入对应环境变量即可。

- 迁移命令会改写原有 `agent.py` 吗？

  不会。迁移命令会新增 Runtime 适配文件，原有 Strands 业务入口保持不变。

## 代码许可

本工程遵循 Apache 2.0 License。
