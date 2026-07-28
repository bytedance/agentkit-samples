# LangChain Agent 迁移示例

这个示例从一个已有的 LangChain 旅行规划 Agent 开始，演示如何把它迁移到 AgentKit Runtime。

原始 Agent 的入口是 `agent.py:agent`，类型是 `TravelPlanningRunnable`。它接收用户的旅行问题，解析城市、天数、预算、同行人和兴趣偏好，然后调用搜索工具和预算工具，生成每天的景点、美食和交通建议。

`agent.py` 中和迁移相关的主要 import 是：

```python
from langchain_core.runnables import Runnable
from langchain_core.tools import tool
from veadk.tools.builtin_tools.web_search import web_search as builtin_web_search
```

- `Runnable`：定义原生 LangChain Agent 入口 `TravelPlanningRunnable`
- `tool`：把普通 Python 函数声明为 LangChain tool
- `builtin_web_search`：提供真实联网搜索能力，供 `search_travel_web` 调用

迁移时不改写 `agent.py` 的业务逻辑。`agentkit migrate` 会生成 `agentkit_app.py` 和 `.agentkit/` 配置；生成的 Runtime 应用通过 `LangChainAgentkitBridge(input_key="question")` 调用原始 `agent.py:agent`。

## Agent 能力

这个 Agent 有两个 LangChain tools：

- `search_travel_web`：调用 `veadk.tools.builtin_tools.web_search` 搜索景点、预约、美食和交通信息
- `estimate_trip_budget`：根据城市、天数和预算给出预算判断

`agent.py:agent` 会组合这两个工具的结果，生成最终行程。

```text
用户问题
    ↓
AgentKit Runtime
    ↓
agentkit_app.py
    ↓
LangChainAgentkitBridge(input_key="question")
    ↓
agent.py:agent  # TravelPlanningRunnable
    ├── search_travel_web
    │   └── veadk.tools.builtin_tools.web_search
    └── estimate_trip_budget
```

## 目录结构

```bash
langchain/
├── README.md
├── agent.py               # 原生 LangChain Runnable 和 tools
├── requirements.txt       # Python 依赖
└── tests                  # 本地行为测试和迁移链路回归测试
```

## 本地运行

安装依赖：

```bash
pip install -r requirements.txt
```

直接运行原生 Agent：

```bash
python agent.py
```

运行测试：

```bash
python -m unittest discover -s tests -v
```

测试会直接调用 `search_travel_web`，不使用 mock 或 fixture。

## 搜索配置

`search_travel_web` 直接使用 `veadk.tools.builtin_tools.web_search`。本地或云端运行时，请参考其它 samples 的通用方式，先在 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 完成依赖服务授权，并配置火山引擎 AK/SK：

```bash
VOLCENGINE_ACCESS_KEY=<Your Access Key>
VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

如果环境没有搜索权限，工具会返回搜索失败说明，Agent 仍会按示例逻辑生成可读结果。

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

参数含义：

- `--framework langchain`：按 LangChain Runnable 方式迁移
- `--entry agent.py:agent`：指定原生 Agent 入口
- `--input-key question`：把 Runtime 输入写入 `question` 字段
- `--compat langserve`：生成 LangServe 兼容路由
- `--verify`：生成后执行基础校验

迁移会生成：

```bash
langchain/
├── agentkit_app.py
├── .agentkit/
│   ├── agentkit.yaml
│   ├── Dockerfile
│   └── migration-plan.json
└── requirements.txt
```

迁移命令不会改写 `agent.py`。生成的 Runtime 应用会通过 `LangChainAgentkitBridge(input_key="question")` 调用原始 `agent.py:agent`。

## 部署到 AgentKit Runtime

确认 `.agentkit/agentkit.yaml` 后执行：

```bash
agentkit deploy
```

部署后，Runtime 入口是 `agentkit_app.py`，业务逻辑仍由 `agent.py:agent` 和原有 LangChain tools 执行。

## 示例问题

```text
我想带父母去北京玩3天，总预算3000元，喜欢历史文化、胡同和老北京美食，行程轻松一点。请帮我规划每天的景点、美食和交通建议。
```
