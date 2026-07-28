# LangGraph 项目适配 AgentKit Runtime 示例

本示例将演示如何将 LangGraph 项目适配到 AgentKit Runtime 上。

示例项目模拟一个用户已有的 LangGraph 旅行规划项目。该项目的业务入口是 `agent.py:agent`，类型是已编译的 `StateGraph`。它接收用户的旅行问题后，会通过 LangGraph 的图编排能力，把一次旅行规划拆成多个节点执行：先解析需求，再检索旅行上下文和预算信息，最后汇总成每天的景点、美食和交通建议。

示例中的工具用于模拟真实 LangGraph 项目中的 tool use：

- `search_travel_web`：模拟依赖外部知识检索的工具，内部调用 `veadk.tools.builtin_tools.web_search`
- `estimate_trip_budget`：模拟本地业务计算工具，根据城市、天数和预算生成预算判断

`agent.py` 是一个基于 LangGraph 构建的 Agent，重点模拟用户使用 LangGraph 搭建 agent 的真实使用场景：

- `StateGraph(TravelState)`：定义旅行规划的共享状态，并编译为 `agent.py:agent`
- `parse_request` 节点：解析用户问题中的城市、天数、预算、同行人和偏好
- `search_travel_context` 节点：调用 `search_travel_web` 和 `estimate_trip_budget`，把外部知识和本地预算判断写回 graph state
- `build_final_answer` 节点：读取前面节点写入的 state，汇总搜索上下文、预算判断和行程安排
- `add_edge`：声明节点执行顺序，让请求沿着 `START -> parse_request -> search_travel_context -> build_final_answer -> END` 流转
- `InMemorySaver`：保留同一个 `thread_id` 下的会话状态，模拟真实 LangGraph workflow 的状态延续

适配到 AgentKit Runtime 时，不需要改写 `agent.py` 的业务逻辑。`agentkit migrate` 会生成 `agentkit_app.py` 和 `.agentkit/` 配置；生成的 Runtime 应用通过 `LangGraphAgentkitBridge(input_key="question")` 调用原始 `agent.py:agent`。

## 适配后的图编排调用链路

适配前，用户可以直接调用 `agent.py:agent`。适配后，AgentKit Runtime 会通过生成的 `agentkit_app.py` 调用同一个入口；进入 `agent.py:agent` 后，执行逻辑仍然由 LangGraph 的节点和边驱动：

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
    ├── parse_request
    ├── search_travel_context
    │   ├── search_travel_web
    │   │   └── veadk.tools.builtin_tools.web_search
    │   └── estimate_trip_budget
    └── build_final_answer
```

## 目录结构

```bash
langgraph/
├── README.md
├── agent.py               # 原生 LangGraph graph、节点和 tools
├── requirements.txt       # Python 依赖
└── tests                  # 本地行为测试和迁移链路回归测试
```

## 本地运行

安装依赖：

```bash
pip install -r requirements.txt
```

直接运行原生 Graph：

```bash
python agent.py
```

运行测试：

```bash
python -m unittest discover -s tests -v
```

测试会直接覆盖 `search_travel_web` 的真实工具调用链路。

## 搜索配置

`search_travel_web` 直接使用 `veadk.tools.builtin_tools.web_search`。本地或云端运行时，请参考其它 samples 的通用方式，先在 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 完成依赖服务授权，并配置火山引擎 AK/SK：

```bash
VOLCENGINE_ACCESS_KEY=<Your Access Key>
VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

如果环境没有搜索权限，工具会返回搜索失败说明，Graph 仍会按示例逻辑生成可读结果。

## 执行迁移

在当前目录执行：

```bash
agentkit migrate . \
  --framework langgraph \
  --entry agent.py:agent \
  --name migration-langgraph-travel \
  --input-key question \
  --verify
```

参数含义：

- `--framework langgraph`：按 LangGraph compiled graph 方式迁移
- `--entry agent.py:agent`：指定原生 Graph 入口
- `--input-key question`：把 Runtime 输入写入 `question` 字段
- `--verify`：生成后执行基础校验

迁移会生成：

```bash
langgraph/
├── agentkit_app.py
├── .agentkit/
│   ├── agentkit.yaml
│   ├── Dockerfile
│   └── migration-plan.json
└── requirements.txt
```

迁移命令不会改写 `agent.py`。生成的 Runtime 应用会通过 `LangGraphAgentkitBridge(input_key="question")` 调用原始 `agent.py:agent`，并将 AgentKit 会话映射到 LangGraph `thread_id`。

## 部署到 AgentKit Runtime

确认 `.agentkit/agentkit.yaml` 后执行：

```bash
agentkit deploy
```

部署后，Runtime 入口是 `agentkit_app.py`，业务逻辑仍由 `agent.py:agent` 中的 LangGraph 节点、checkpointer 和原有 tools 执行。

## 示例问题

```text
我想带父母去北京玩3天，总预算3000元，喜欢历史文化、胡同和老北京美食，行程轻松一点。请帮我规划每天的景点、美食和交通建议。
```
