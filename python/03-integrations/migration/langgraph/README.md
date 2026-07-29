# LangGraph 迁移 AgentKit Runtime 示例

## 概述

本项目演示如何将已有 LangGraph 项目适配到 AgentKit Runtime。

示例模拟一个用户已有的 LangGraph 旅行规划项目。原项目入口是 `agent.py:agent`，类型为已编译的 `StateGraph`。它接收旅行问题，通过 `create_react_agent` 调用真实 LLM，并让 ReAct agent 自主选择联网搜索和预算估算工具生成每天的景点、美食和交通建议。

迁移时不需要改写原有业务逻辑。`agentkit migrate` 会生成 `agentkit_app.py` 和 `.agentkit/` 配置，生成后的 Runtime 应用通过 `LangGraphAgentkitBridge(input_key="question")` 调用原始 `agent.py:agent`。

## 核心功能

- 展示 LangGraph compiled graph 入口如何被 AgentKit Runtime 调用。
- 使用外层 LangGraph `StateGraph` 保持 `question` 输入入口。
- 使用 LangGraph prebuilt `create_react_agent` 编排真实 LLM、联网搜索工具和预算估算工具。
- 使用 LangChain chat model 从环境变量读取模型配置，并调用真实 LLM 节点。
- 保留原生 LangGraph 业务代码，并通过 `agentkit migrate` 生成 Runtime 适配层。

## Agent 能力

本示例包含以下 Agent 能力：

- LangGraph `StateGraph` 输入适配。
- LangGraph prebuilt ReAct agent。
- LangChain tools 工具调用。
- LangChain OpenAI-compatible chat model LLM 节点。
- 火山引擎 AgentKit 内置联网搜索工具。
- 本地预算估算业务工具。

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
agent.py:agent  # compiled StateGraph
    └── call_react_agent
        └── create_react_agent
            ├── LangChain chat model
            ├── search_travel_web
            │   └── veadk.tools.builtin_tools.web_search
            └── estimate_trip_budget
```

## 目录结构说明

```bash
langgraph/
├── .env.example       # 模型和火山引擎访问凭证环境变量示例
├── README.md          # 中文说明文档
├── README_en.md       # 英文说明文档
├── agent.py           # 原生 LangGraph graph、ReAct agent、tools 和 LLM 调用
├── project.yaml       # 项目信息元数据
└── requirements.txt   # Python 依赖列表
```

`agentkit migrate` 执行后会在当前目录生成 `agentkit_app.py` 和 `.agentkit/` 目录。生成文件不需要提前提交到样例源码中。

## 本地运行

### 前置准备

在本地或云端运行联网搜索能力前，请访问 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 完成依赖服务授权。

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

复制 `.env.example` 为 `.env`，并填写模型和火山引擎 AK/SK：

```bash
MODEL_AGENT_NAME=<Your Model Name>
MODEL_AGENT_PROVIDER=
MODEL_AGENT_API_BASE=
MODEL_AGENT_API_KEY=<Your Ark API Key>
VOLCENGINE_ACCESS_KEY=<Your Access Key>
VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

`MODEL_AGENT_PROVIDER`、`MODEL_AGENT_API_BASE` 和 `MODEL_AGENT_API_KEY` 会传给 LangChain chat model。请按实际模型服务填写 provider、API 地址和密钥。若 API 地址以 `/responses` 或 `/chat/completions` 结尾，示例会在构建 OpenAI-compatible chat model 前归一化为 API 根地址。

如果环境没有搜索权限，`search_travel_web` 会返回搜索失败说明，Agent 仍会继续调用预算和 LLM 节点。

### 调试方法

直接运行原生 LangGraph Agent：

```bash
python agent.py
```

也可以使用迁移后的 Runtime 应用进行调试。先执行迁移命令：

```bash
agentkit migrate . \
  --framework langgraph \
  --entry agent.py:agent \
  --name migration-langgraph-travel \
  --input-key question \
  --verify \
  --force
```

参数含义如下：

- `--framework langgraph`：按 LangGraph compiled graph 方式迁移。
- `--entry agent.py:agent`：指定原生 Graph 入口。
- `--input-key question`：把 Runtime 输入写入 `question` 字段。
- `--verify`：生成后执行基础校验。

## AgentKit 部署

确认 `.agentkit/agentkit.yaml` 后执行：

```bash
agentkit deploy
```

部署后，Runtime 入口是 `agentkit_app.py`，业务逻辑仍由 `agent.py:agent` 和原有 LangGraph 节点执行。

部署时需要提供模型和搜索相关环境变量：

```bash
MODEL_AGENT_NAME=<Your Model Name>
MODEL_AGENT_PROVIDER=
MODEL_AGENT_API_BASE=
MODEL_AGENT_API_KEY=<Your Ark API Key>
VOLCENGINE_ACCESS_KEY=<Your Access Key>
VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

## 示例提示词

- 我想带父母去北京玩 3 天，总预算 3000 元，喜欢历史文化、胡同和老北京美食，行程轻松一点。请帮我规划每天的景点、美食和交通建议。
- 我想去杭州玩 2 天，预算 1800 元，喜欢西湖、博物馆和本地小吃，请安排一个慢游路线。

## 效果展示

运行示例提示词后，ReAct agent 会根据模型决策调用搜索和预算工具，并由真实 LLM 输出按天拆分的旅行规划，内容包含景点安排、餐饮建议、预算判断和交通建议。

```text
北京3天旅行规划（预算3000元，带父母/长辈）

第1天：故宫博物院 + 什刹海胡同
第2天：天坛公园 + 前门大街
```

## 常见问题

- 搜索工具报错怎么办？

  请确认已在 AgentKit 控制台完成服务授权，并正确配置 `VOLCENGINE_ACCESS_KEY` 和 `VOLCENGINE_SECRET_KEY`。搜索失败时，样例仍会继续执行预算和 LLM 节点。

- 为什么代码里没有模型默认值？

  为了避免把 endpoint、model name 或 API key 写入样例源码，模型配置必须通过环境变量注入。

## 代码许可

本工程遵循 Apache 2.0 License。
