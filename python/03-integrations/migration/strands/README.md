# Strands 项目适配 AgentKit Runtime 示例

本示例将演示如何将 Strands 项目适配到 AgentKit Runtime 上。

示例项目模拟一个用户已有的 Strands 旅行规划项目。该项目的业务入口是 `agent.py:build_agent`，它创建并返回一个 Strands `Agent`。Agent 接收用户的旅行问题后，会通过 Strands 的 Agent + tools 运行方式，把旅行规划能力组织成可注册、可调试、可迁移的工具调用链路。

示例中的工具用于模拟真实 Strands 项目中的 tool use：

- `search_travel_web`：模拟依赖外部知识检索的工具，内部调用 `veadk.tools.builtin_tools.web_search`
- `estimate_trip_budget`：模拟本地业务计算工具，根据城市、天数和预算生成预算判断

`agent.py` 是一个基于 Strands 构建的 Agent，重点展示原生 Strands 项目常见的 Agent 工厂和工具注册方式：

- `build_agent()`：创建原生 Strands `Agent`，并作为 `agent.py:build_agent` 暴露给迁移命令
- `TRAVEL_TOOLS`：集中注册 `search_travel_web` 和 `estimate_trip_budget`
- `@tool`：把普通 Python 函数声明为 Strands tools，让 Agent 可以按工具调用方式使用它们
- `search_travel_web`：在工具内部调用 `veadk.tools.builtin_tools.web_search`，模拟真实项目中依赖外部知识检索的能力
- `estimate_trip_budget`：保留本地业务计算逻辑，模拟真实项目中的内部工具
- `LocalTravelModel`：让样例在本地调试时可以返回稳定的可读结果，同时保留 Strands `Agent` 的运行入口和工具配置

适配到 AgentKit Runtime 时，不需要改写 `agent.py` 的业务逻辑。`agentkit migrate` 会生成 `agentkit_app.py` 和 `.agentkit/` 配置；生成的 Runtime 应用通过 `StrandsAgentkitBridge(agent_factory=True)` 调用原始 `agent.py:build_agent`。

## 适配后的 Agent 调用链路

适配前，用户可以直接调用 `agent.py:build_agent` 创建 Strands Agent。适配后，AgentKit Runtime 会通过生成的 `agentkit_app.py` 调用同一个入口；进入 `agent.py:build_agent` 后，业务逻辑仍然由 Strands `Agent` 和已注册的 tools 执行：

```text
用户问题
    ↓
AgentKit Runtime
    ↓
agentkit_app.py
    ↓
StrandsAgentkitBridge(agent_factory=True)
    ↓
agent.py:build_agent
    ↓
Strands Agent
    ├── search_travel_web
    │   └── veadk.tools.builtin_tools.web_search
    └── estimate_trip_budget
```

## 目录结构

```bash
strands/
├── README.md
├── agent.py               # 原生 Strands Agent、工厂入口和 tools
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

测试会直接覆盖 `search_travel_web` 的真实工具调用链路。

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
  --framework strands \
  --entry agent.py:build_agent \
  --name migration-strands-travel \
  --verify
```

参数含义：

- `--framework strands`：按 Strands Agent 方式迁移
- `--entry agent.py:build_agent`：指定原生 Strands Agent 工厂入口
- `--verify`：生成后执行基础校验

迁移会生成：

```bash
strands/
├── agentkit_app.py
├── .agentkit/
│   ├── agentkit.yaml
│   ├── Dockerfile
│   └── migration-plan.json
└── requirements.txt
```

迁移命令不会改写 `agent.py`。生成的 Runtime 应用会通过 `StrandsAgentkitBridge(agent_factory=True)` 调用原始 `agent.py:build_agent`。

## 部署到 AgentKit Runtime

确认 `.agentkit/agentkit.yaml` 后执行：

```bash
agentkit deploy
```

部署后，Runtime 入口是 `agentkit_app.py`，业务逻辑仍由 `agent.py:build_agent` 创建的 Strands Agent 和原有 tools 执行。

## 示例问题

```text
我想带父母去北京玩3天，总预算3000元，喜欢历史文化、胡同和老北京美食，行程轻松一点。请帮我规划每天的景点、美食和交通建议。
```
