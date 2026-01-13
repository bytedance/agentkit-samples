# Restaurant Ordering - 餐厅点餐智能助手

基于火山引擎 VeADK 构建的高级点餐 Agent，展示如何实现复杂业务流程、异步工具调用、上下文管理和自定义插件等高级特性。

## 概述

本示例是一个功能完善的餐厅点餐助手，展示 VeADK 的多项高级能力。

## 核心功能

- 异步工具与并行调用：同时处理多个菜品订单
- 高级上下文管理：事件压缩和上下文过滤
- 状态管理：使用 ToolContext 维护订单状态
- 自定义插件：监控 Agent 运行次数和 LLM 调用
- Web 搜索集成：处理菜单外的特殊需求

## Agent 能力

```text
用户点餐请求
    ↓
Restaurant Ordering Agent
    ├── 菜单匹配（语义理解）
    ├── 并行工具调用
    │   ├── add_to_order (添加菜品)
    │   ├── summarize_order (汇总订单)
    │   └── web_search (菜单外查询)
    │
    ├── 状态管理 (ToolContext)
    │   └── order: [] (订单列表)
    │
    └── 插件系统
        ├── CountInvocationPlugin (计数插件)
        ├── ContextFilterPlugin (上下文过滤)
        └── EventsCompactionConfig (事件压缩)
```

### 核心组件

| 组件 | 描述 |
| - | - |
| **Agent 服务** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/02-use-cases/08_restaurant_ordering/agent.py#L82-L117) - order_agent，点餐助手 |
| **测试脚本** | [main.py](https://github.com/volcengine/agentkit-samples/blob/main/python/02-use-cases/08_restaurant_ordering/main.py) - 完整的点餐流程演示 |
| **自定义工具** | add_to_order, summarize_order |
| **自定义插件** | CountInvocationPlugin - 统计调用次数 |
| **上下文管理** | EventsCompactionConfig + ContextFilterPlugin |

### 代码特点

**异步工具定义**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/02-use-cases/08_restaurant_ordering/agent.py#L52-L79)）：

```python
async def add_to_order(dish_name: str, tool_context: ToolContext = None) -> str:
    """Adds a dish to the user's order."""
    if "order" not in tool_context.state:
        tool_context.state["order"] = []

    tool_context.state["order"] = tool_context.state["order"] + [dish_name]
    return f"I've added {dish_name} to your order."

async def summarize_order(tool_context: ToolContext = None) -> str:
    """Summarizes the user's current order."""
    order = tool_context.state.get("order", [])
    if not order:
        return "You haven't ordered anything yet."

    summary = "Here is your order so far:\n" + "\n".join(f"- {dish}" for dish in order)
    return summary
```

**Agent 配置与并行调用**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/02-use-cases/08_restaurant_ordering/agent.py#L82-L117)）：

```python
order_agent = Agent(
    name="restaurant_ordering_agent",
    description="An agent that takes customer orders at a restaurant.",
    instruction=f"""
        You are a friendly and efficient order-taking assistant for a restaurant.
        The menu contains: {", ".join(RECIPES)}.

        **Workflow:**
        1. Understand the user's request and match to menu items.
        2. You MUST call the `add_to_order` tool. You can using parallel invocations
           to add multiple dishes to the order.
        3. Handle off-menu requests using `web_search` tool.
        4. When finished, call `summarize_order` tool.
    """,
    tools=[add_to_order, summarize_order, web_search],
)
```

**自定义插件**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/02-use-cases/08_restaurant_ordering/agent.py#L120-L144)）：

```python
class CountInvocationPlugin(BasePlugin):
    """A custom plugin that counts agent and tool invocations."""

    def __init__(self) -> None:
        super().__init__(name="count_invocation")
        self.agent_count: int = 0
        self.llm_request_count: int = 0

    async def before_agent_callback(
        self, *, agent: BaseAgent, callback_context: CallbackContext
    ) -> None:
        self.agent_count += 1
        print(f"[Plugin] Agent run count: {self.agent_count}")

    async def before_model_callback(
        self, *, callback_context: CallbackContext, llm_request: LlmRequest
    ) -> None:
        self.llm_request_count += 1
        print(f"[Plugin] LLM request count: {self.llm_request_count}")
```

**上下文管理配置**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/02-use-cases/08_restaurant_ordering/agent.py#L151-L167)）：

```python
app = App(
    name="restaurant_ordering",
    root_agent=root_agent,
    plugins=[
        CountInvocationPlugin(),
        ContextFilterPlugin(num_invocations_to_keep=8),  # 保留最近8轮对话
        SaveFilesAsArtifactsPlugin(),
    ],
    # 事件压缩：每3次调用触发一次压缩
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=3,
        overlap_size=1,
    ),
)
```

## 目录结构说明

```bash
08_restaurant_ordering/
├── agent.py           # Agent 应用入口（高级特性示例）
├── main.py            # 完整的点餐流程演示脚本
├── requirements.txt   # Python 依赖列表 （agentkit部署时需要指定依赖文件)
└── README.md          # 项目说明文档
```

## 本地运行

### 前置准备

**1. 开通火山方舟模型服务：**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)
- 开通模型服务

**2. 获取火山引擎访问凭证：**

- 参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK

### 依赖安装

#### 1. 安装 uv 包管理器

```bash
# macOS / Linux（官方安装脚本）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 Homebrew（macOS）
brew install uv
```

#### 2. 初始化项目依赖

```bash
# 进入项目目录
cd python/02-use-cases/08_restaurant_ordering
```

使用 `uv` 工具来安装本项目依赖：

```bash
# 如果没有 `uv` 虚拟环境，可以使用命令先创建一个虚拟环境
uv venv --python 3.12

# 使用 `pyproject.toml` 管理依赖
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 激活虚拟环境
source .venv/bin/activate
```

### 环境准备

```bash
# 火山方舟模型名称
export MODEL_AGENT_NAME=doubao-seed-1-6-251015

# 火山引擎访问凭证（必需）
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### 调试方法

#### 方式一：使用 VeADK Web 调试界面

```bash
# 进入上级目录
cd ..

# 启动 VeADK Web 界面
veadk web

# 在浏览器访问：http://127.0.0.1:8000
```

Web 界面提供图形化对话测试环境，支持实时查看订单状态和调试信息。

#### 方式二：命令行测试（推荐学习）

```bash
# 运行完整的点餐流程演示
python main.py

# 或直接启动 Agent 服务
python agent.py
# 服务将监听 http://0.0.0.0:8000
```

## AgentKit 部署

### 前置准备

**重要提示**：在运行本示例之前，请先访问 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 对所有依赖服务进行授权，确保案例能够正常执行。

**1. 开通火山方舟模型服务：**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)
- 开通模型服务

**2. 获取火山引擎访问凭证：**

- 参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK

### AgentKit 云上部署

```bash
cd python/02-use-cases/08_restaurant_ordering

# 配置部署参数
agentkit config

# 启动云端服务
agentkit launch

# 测试部署的 Agent
agentkit invoke '你好，我想吃点辣的。'

# 或使用 client.py 连接云端服务
# 需要编辑 client.py，将其中的第 14 行和第 15 行的 base_url 和 api_key 修改为 agentkit.yaml 中生成的 runtime_endpoint 和 runtime_apikey 字段
# 按需修改 client.py，第 56 行，请求的内容
uv run client.py
```

## 示例提示词

### 基础点餐流程

**单品点餐**：

```text
用户：你好，我想吃点辣的。
Agent：我推荐宫保鸡丁，这是一道经典的辣味菜品。
      [调用 add_to_order("Kung Pao Chicken")]
      已为您添加宫保鸡丁。

用户：再来一份饺子。
Agent：好的！
      [调用 add_to_order("Dumplings")]
      已为您添加饺子。

用户：我点完了，结账。
Agent：[调用 summarize_order]
      这是您的订单：
      - Kung Pao Chicken
      - Dumplings
```

### 并行工具调用

**一次点多个菜品**：

```text
用户：我要一个宫保鸡丁和一份饺子。
Agent：好的！
      [并行调用 add_to_order("Kung Pao Chicken")]
      [并行调用 add_to_order("Dumplings")]
      已为您添加宫保鸡丁和饺子。
```

### 菜单外请求

**特殊菜品查询**：

```text
用户：你们有螃蟹做的菜吗？
Agent：[调用 web_search 搜索螃蟹菜品信息]
      我们的菜单上没有螃蟹菜品，但我可以为您向厨房询问是否可以制作。
      您想要点一份特制螃蟹菜吗？

用户：听起来不错，就按你说的做一份吧。
Agent：[调用 add_to_order("Special Crab Dish")]
      已为您添加特制螃蟹菜。
```

### 完整对话流程

运行 `main.py` 可以看到完整的点餐演示：

```python
prompts = [
    "你好，我想吃点辣的。",
    "你们有螃蟹做的菜吗？",
    "听起来不错，就按你说的做一份吧。",
    "再来一份宫保鸡丁。",
    "我点完了，结账。",
]
```

输出：

```bash
[Plugin] Agent run count: 1
[Plugin] LLM request count: 1
** User says: 你好，我想吃点辣的。
** restaurant_ordering_agent: 我推荐宫保鸡丁...

[Plugin] Agent run count: 2
[Plugin] LLM request count: 2
** User says: 你们有螃蟹做的菜吗？
** restaurant_ordering_agent: 让我查询一下...

...

** restaurant_ordering_agent: 这是您的订单：
- Kung Pao Chicken
- Special Crab Dish
- Kung Pao Chicken
```

## 效果展示

## 技术要点

### 1. 异步工具与并行调用

**异步定义**：

```python
async def add_to_order(dish_name: str, tool_context: ToolContext = None) -> str:
    # 异步函数支持并发执行
    ...
```

**并行调用提示**：

```text
You can using parallel invocations to add multiple dishes to the order.
```

Agent 可以同时发起多个工具调用，显著提升处理速度。

### 2. 高级上下文管理

**事件压缩（EventsCompactionConfig）**：

- 自动将多轮对话历史压缩为摘要
- 节省 Token 数量，降低成本
- 配置：每 3 次调用触发一次压缩

**上下文过滤（ContextFilterPlugin）**：

- 精确控制保留的对话轮数
- 配置：保留最近 8 轮对话
- 确保核心上下文不丢失

### 3. 状态管理（ToolContext）

**共享状态**：

```python
# 添加菜品
tool_context.state["order"] = tool_context.state["order"] + [dish_name]

# 读取订单
order = tool_context.state.get("order", [])
```

`tool_context.state` 在工具调用之间持久化，实现状态共享。

### 4. 自定义插件

**插件钩子**：

- `before_agent_callback`: Agent 运行前
- `before_model_callback`: LLM 调用前

**可观测性**：

- 统计 Agent 运行次数
- 统计 LLM 调用次数
- 监控性能和成本

### 5. 语义理解与菜单匹配

Agent 能够：

- 理解模糊需求（"辣的"→宫保鸡丁）
- 匹配菜单项（"鸡肉菜"→Kung Pao Chicken）
- 处理同义词和多种表达方式

### AgentKit 集成

```python
from agentkit.apps import AgentkitAgentServerApp

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)
```

## 下一步

完成 Restaurant Ordering 示例后，可以探索更多功能：

1. **[A2A Simple](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/a2a_simple/README.md)** - 学习 Agent-to-Agent 通信协议
2. **[Multi Agents](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/multi_agents/README.md)** - 构建更复杂的多智能体协作系统
3. **[Travel Concierge](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/travel_concierge/README.md)** - 使用 Web 搜索工具规划旅行
4. **[Video Generator](../../video_gen/README.md)** - 高级视频生成示例

## 常见问题

无。

## 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)
- [火山方舟模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
- [Google ADK 上下文压缩](https://google.github.io/adk-docs/context/compaction/)

## 代码许可

本工程遵循 Apache 2.0 License
