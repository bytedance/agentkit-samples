# LangGraph 迁移 AgentKit Runtime 示例

## 概述

本项目演示如何将已有 LangGraph 项目适配到 AgentKit Runtime。

示例模拟一个用户已有的 LangGraph 旅行规划项目。原项目入口是 `agent.py:agent`，类型为已编译的 `StateGraph`。它在图节点中使用 LangChain `create_agent` 注册模型、系统提示词和本地旅行工具，接收旅行问题后由 agent 调用工具并生成景点、美食、预算和交通建议。

迁移时不需要改写原有业务逻辑。`agentkit migrate` 会生成 `agentkit_app.py` 和 `.agentkit/` 配置，生成后的 Runtime 应用通过 `LangGraphAgentkitBridge(input_key="question")` 调用原始 `agent.py:agent`。

## 核心功能

- 展示 LangGraph compiled graph 入口如何被 AgentKit Runtime 调用。
- 使用外层 LangGraph `StateGraph` 保持 `question` 输入入口。
- 在 LangGraph 节点中使用 LangChain `create_agent` 组织模型、提示词和工具。
- 使用 `@tool` 声明本地旅行资料检索、预算估算和交通建议工具。
- 保留原生 LangGraph 业务代码，并通过 `agentkit migrate` 生成 Runtime 适配层。

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
LangGraphAgentkitBridge(input_key="question")
    ↓
agent.py:agent
    └── call_react_agent
        └── create_agent
            ├── search_travel_notes
            ├── estimate_trip_budget
            ├── recommend_transport
            └── ChatOpenAI
```

## 目录结构说明

```bash
langgraph/
├── .env.example       # 模型配置环境变量示例
├── README.md          # 中文说明文档
├── README_en.md       # 英文说明文档
├── agent.py           # 原生 LangGraph graph、ReAct agent 和 tools
└── requirements.txt   # Python 依赖列表
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

复制 `.env.example` 为 `.env`，然后再.env中写入必要的环境变量：

```text
MODEL_AGENT_NAME=<model-name>
MODEL_AGENT_API_BASE=
MODEL_AGENT_API_KEY=<api-key>
```

AgentKit CLI 在运行前会自动加载 `.env` 到 AgentKit CLI 的环境变量中。当前 demo 使用 `langchain_openai.ChatOpenAI` 创建模型，因此不需要配置 `MODEL_AGENT_PROVIDER`，确保您的模型接入点支持 OpenAI 格式即可。

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

### pre-check
在执行迁移之前，先确保原来的LangGraph项目是正常且可运行的：

```bash
python agent.py
```

该命令会调用 `agent.py:agent`，向 graph 发送固定旅行问题，并使用配置的 OpenAI-compatible 模型完成一次真实对话。

### 执行Migration命令：
在确保原项目是可执行的以后，就可以执行migration命令，进行Agentkit项目的适配了
```bash
agentkit migrate . \
  --framework langgraph \
  --entry agent.py:agent \
  --name migration-langgraph-travel \
  --input-key question \
  --verify
```

参数含义如下：

- `--framework langgraph`：按 LangGraph compiled graph 方式迁移。
- `--entry agent.py:agent`：指定原生 Graph 入口。
- `--input-key question`：把 Runtime 输入写入 `question` 字段。
- `--verify`：生成后执行基础校验。

执行成功后的产物即可直接部署到Agentkit Runtime上。
全过程对原本的LangGraph agent.py无侵入，无改造。

## AgentKit 部署

如果要执行 `agentkit deploy`，可以先关注 `.agentkit/agentkit.yaml` 当中的配置。确认后执行：

```bash
agentkit deploy
```

部署后，即可在Agentkit平台的Runtime当中找到部署的项目。

## 示例提示词

- 我想带父母去北京玩 3 天，总预算 3000 元，喜欢历史文化、胡同和老北京美食，行程轻松一点。请帮我规划每天的景点、美食和交通建议。
- 我想去成都玩 2 天，预算 2000 元，喜欢美食和城市街区，请安排一个轻松路线。

## 效果展示

运行示例提示词后，Agent 会通过 LangGraph 节点调用本地旅行资料、预算和交通工具，并输出按天拆分的旅行规划，内容包含景点安排、餐饮建议、预算判断和交通建议。

```text
北京3天旅行规划（示例模型输出）

第1天：故宫博物院 + 什刹海胡同
第2天：天坛公园 + 前门周边
```

## 常见问题

- 迁移命令会改写原有 `agent.py` 吗？

  不会。迁移命令会新增 Runtime 适配文件，原有 LangGraph 业务入口保持不变。

## 代码许可

本工程遵循 Apache 2.0 License。
