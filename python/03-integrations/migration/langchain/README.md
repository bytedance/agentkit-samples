# LangChain Agent 迁移示例

原生 LangChain 旅行规划 Agent 迁移到 AgentKit Runtime 的示例，展示如何保留 LangChain `Runnable`、`@tool` 和流式输出能力，并通过 `agentkit migrate` 生成可部署的 Runtime 应用。

## 概述

本示例以北京 3 天旅行规划为场景。迁移前，`agent.py` 只包含原生 LangChain Agent 和 tools；迁移后，AgentKit Runtime 通过生成的 `agentkit_app.py` 调用同一个 `agent.py:agent`。

## 核心功能

- LangChain Agent：暴露 `agent.py:agent` 作为可迁移的 `Runnable`
- Tool 调用：通过 `search_travel_web` 调用 `veadk.tools.builtin_tools.web_search` 搜索旅行信息，通过 `estimate_trip_budget` 估算预算
- 输入适配：使用 `--input-key question` 将 Runtime 输入映射为 `{"question": "..."}`
- 流式输出：保留 `astream`，迁移后可继续用于流式响应
- Runtime 部署：迁移后执行 `agentkit deploy` 部署到 AgentKit Runtime

## Agent 能力

```text
用户问题
    ↓
AgentKit Runtime
    ↓
LangChainAgentkitBridge
    ↓
agent.py:agent
    ├── search_travel_web      # 搜索景点、预约、美食、交通
    └── estimate_trip_budget   # 判断旅行预算
```

### 核心组件

| 组件 | 描述 |
| - | - |
| **LangChain Agent** | `agent.py:agent` - `TravelPlanningRunnable`，迁移入口 |
| **搜索工具** | `search_travel_web` - LangChain `@tool`，内部调用 `veadk.tools.builtin_tools.web_search` 获取旅行上下文 |
| **预算工具** | `estimate_trip_budget` - LangChain `@tool`，生成预算判断 |
| **迁移入口** | `agentkit migrate` - 生成 AgentKit Runtime wrapper 和部署配置 |
| **Runtime 应用** | `agentkit_app.py` - 迁移后生成，负责接入 AgentKit Runtime |

### 代码特点

**Agent 定义**：

```python
agent = TravelPlanningRunnable()
```

**本地调用方式**：

```python
agent.invoke({
    "question": "我想带父母去北京玩3天，总预算3000元，喜欢历史文化和轻松一点的行程。"
})
```

**迁移适配点**：

```bash
--entry agent.py:agent
--input-key question
```

迁移命令不会改写 `agent.py` 中的 LangChain tools。生成的 Runtime 应用会通过 `LangChainAgentkitBridge(input_key="question")` 调用原始 Runnable。

## 目录结构说明

```bash
langchain/
├── README.md
├── agent.py               # 原生 LangChain Runnable 和 tools
├── requirements.txt       # Python 依赖
└── tests                  # 本地行为测试和迁移链路回归测试
```

## 本地运行

### 依赖安装

```bash
pip install -r requirements.txt
```

### 调试原生 Agent

```bash
python agent.py
```

### 运行测试

```bash
python -m unittest discover -s tests -v
```

测试会直接通过 `search_travel_web` 走 `veadk.tools.builtin_tools.web_search`。

## 执行迁移

在当前目录执行：

```bash
agentkit migrate . \
  --framework langchain \
  --entry agent.py:agent \
  --name migration-langchain-travel \
  --input-key question \
  --compat langserve \
  --verify
```

参数说明：

- `--framework langchain`：按 LangChain Runnable 方式迁移
- `--entry agent.py:agent`：指定原生 LangChain Agent 入口
- `--input-key question`：将 Runtime 输入写入 `question` 字段
- `--compat langserve`：生成 LangServe 兼容路由
- `--verify`：生成后执行基础校验

迁移完成后会生成：

```bash
langchain/
├── agentkit_app.py
├── .agentkit/
│   ├── agentkit.yaml
│   ├── Dockerfile
│   └── migration-plan.json
└── requirements.txt
```

## AgentKit Runtime 部署

确认 `.agentkit/agentkit.yaml` 后执行：

```bash
agentkit deploy
```

`search_travel_web` 使用 `veadk.tools.builtin_tools.web_search`。本地或云端运行时，请参考其它 samples 的通用方式，先在 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 完成依赖服务授权，并配置火山引擎 AK/SK：

```bash
VOLCENGINE_ACCESS_KEY=<Your Access Key>
VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

部署后，AgentKit Runtime 入口是 `agentkit_app.py`，业务逻辑仍由 `agent.py:agent` 和原有 LangChain tools 执行。

## 示例提示词

```text
我想带父母去北京玩3天，总预算3000元，喜欢历史文化、胡同和老北京美食，行程轻松一点。请帮我规划每天的景点、美食和交通建议。
```
