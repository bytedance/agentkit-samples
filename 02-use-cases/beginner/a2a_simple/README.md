# A2A Simple - Agent-to-Agent 通信协议

基于火山引擎 VeADK 和 A2A (Agent-to-Agent) 协议构建的分布式智能体示例，展示如何实现智能体之间的通信和协作。

## 概述

本示例演示 A2A 协议的基础应用，展示如何构建可互操作的分布式智能体系统。

## 核心功能

- A2A 协议：标准化的智能体间通信协议
- 远程服务：提供工具能力的远程 Agent
- 本地客户端：调用远程 Agent 的客户端
- 工具能力：投掷骰子和检查质数
- 状态管理：跨工具调用的状态持久化

## Agent 能力

```text
方式一：直接客户端调用
本地客户端 (local_client.py)
    ↓
A2A 协议 (HTTP/JSONRPC)
    ↓
远程 Agent 服务 (remote/agent.py:8001)
    ├── roll_die 工具 (投掷骰子)
    │   └── 状态管理：rolls 历史
    │
    └── check_prime 工具 (检查质数)

方式二：Agent 级联调用
本地 Agent (agent.py:8000)
    ├── add 工具 (加法)
    └── RemoteVeAgent → 远程 Agent 服务 (remote/agent.py:8001)
        ├── roll_die 工具 (投掷骰子)
        └── check_prime 工具 (检查质数)
```

## 目录结构说明

```bash
a2a_simple/
├── agent.py                 # 本地 Agent 服务（端口 8000，可调用远程 Agent）
├── local_client.py          # A2A 客户端实现
├── remote/                  # 远程 Agent 服务
│   ├── agent.py            # Agent 定义和 A2A App（端口 8001）
│   ├── agentkit.yaml       # AgentKit 部署配置
│   ├── requirements.txt    # Python 依赖
│   ├── Dockerfile          # Docker 镜像构建
│   └── tools/              # 工具实现
│       ├── roll_die.py     # 投掷骰子工具
│       └── check_prime.py  # 质数检查工具
├── requirements.txt         # 客户端依赖
├── pyproject.toml          # 项目配置
└── README.md               # 项目说明文档
```

### 核心组件

| 组件 | 描述 |
| - | - |
| **远程 Agent** | [remote/agent.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/a2a_simple/remote/agent.py#L14-L40) - hello_world_agent，提供工具服务（端口 8001） |
| **本地 Agent** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/a2a_simple/agent.py#L16-L21) - a2a_sample_agent，具有 add 工具和 sub_agents（端口 8000） |
| **本地客户端** | [local_client.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/a2a_simple/local_client.py) - A2ASimpleClient，调用远程服务 |
| **工具：roll_die** | [remote/tools/roll_die.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/a2a_simple/remote/tools/roll_die.py) - 投掷骰子 |
| **工具：check_prime** | [remote/tools/check_prime.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/a2a_simple/remote/tools/check_prime.py) - 检查质数 |
| **AgentCard** | Agent 元数据和能力描述 |
| **项目配置** | [remote/agentkit.yaml](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/a2a_simple/remote/agentkit.yaml) - AgentKit 部署配置 |

### 代码特点

**本地 Agent 定义**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/a2a_simple/agent.py#L16-L21)）:

```python
agent = Agent(
    name="a2a_sample_agent",
    instruction="You are a helpful assistant that can add numbers and delegate tasks to a remote agent that can roll dice and check prime numbers.",
    tools=[add],
    sub_agents=[remote_agent],
)
```

**远程 Agent 定义**（[remote/agent.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/a2a_simple/remote/agent.py#L14-L40)）：

```python
root_agent = Agent(
    name='hello_world_agent',
    description=(
        'hello world agent that can roll a dice of 8 sides and check prime numbers.'
    ),
    instruction="""
      You roll dice and answer questions about the outcome of the dice rolls.
      You can roll dice of different sizes.
      You can use multiple tools in parallel by calling functions in parallel.
      When you are asked to roll a die, you must call the roll_die tool.
      When checking prime numbers, call the check_prime tool with a list of integers.
    """,
    tools=[roll_die, check_prime],
)
```

**AgentCard 配置**（[remote/agent.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/a2a_simple/remote/agent.py#L48-L58)）：

```python
agent_card = AgentCard(
  capabilities=AgentCapabilities(streaming=True),
  description=root_agent.description,
  name=root_agent.name,
  defaultInputModes=["text"],
  defaultOutputModes=["text"],
  provider=AgentProvider(organization="agentkit", url=""),
  skills=[AgentSkill(id="0", name="chat", description="Chat", tags=["chat"])],
  url="http://localhost:8001",
  version="1.0.0",
)
```

**本地客户端调用**（[local_client.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/a2a_simple/local_client.py#L32-L97)）：

```python
async def create_task(self, agent_url: str, message: str) -> str:
    # 获取 Agent Card
    agent_card_response = await httpx_client.get(
        f'{agent_url}{AGENT_CARD_WELL_KNOWN_PATH}'
    )
    agent_card = AgentCard(**agent_card_response.json())

    # 创建 A2A 客户端
    factory = ClientFactory(config)
    client = factory.create(agent_card)

    # 发送消息
    async for response in client.send_message(message_obj):
        responses.append(response)
```

**工具状态管理**（[remote/tools/roll_die.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/a2a_simple/remote/tools/roll_die.py#L4-L18)）：

```python
def roll_die(sides: int, tool_context: ToolContext) -> int:
    result = random.randint(1, sides)

    # 状态持久化
    if not 'rolls' in tool_context.state:
        tool_context.state['rolls'] = []

    tool_context.state['rolls'] = tool_context.state['rolls'] + [result]
    return result
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
cd 02-use-cases/beginner/a2a_simple
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

Web 界面提供图形化对话测试环境，支持实时查看远程调用过程。

#### 方式二：命令行测试（推荐学习）

**步骤 1：启动远程 Agent 服务：**

```bash
# 在终端窗口 1 中运行
cd 02-use-cases/beginner/a2a_simple
uv run uvicorn remote.agent:a2a_app --host localhost --port 8001

# 服务启动后，可访问 Agent Card
# http://localhost:8001/.well-known/agent-card.json
```

**步骤 2：运行本地客户端：**

```bash
# 在终端窗口 2 中运行
cd 02-use-cases/beginner/a2a_simple
python local_client.py
```

**步骤 3（可选）：启动本地 Agent 服务：**

```bash
# 在终端窗口 3 中运行（需要先启动远程 Agent）
cd 02-use-cases/beginner/a2a_simple
python agent.py

# 服务启动后，可访问 Agent Card
# http://localhost:8000/.well-known/agent-card.json
```

此时您有两个 Agent 服务：

- **远程 Agent**（端口 8001）：提供 roll_die 和 check_prime 工具
- **本地 Agent**（端口 8000）：提供 add 工具，并可调用远程 Agent

## AgentKit 部署

### 前置准备

**重要提示**：在运行本示例之前，请先访问 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 对所有依赖服务进行授权，确保案例能够正常执行。

**1. 开通火山方舟模型服务：**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)
- 开通模型服务

**2. 获取火山引擎访问凭证：**

- 参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK

### Agentkit 云上部署

```bash
cd 02-use-cases/beginner/a2a_simple/remote

# 配置部署参数（重要：agent_type 必须为 a2a）
agentkit config

# 查看配置
agentkit config --show

# 启动云端服务
agentkit launch

# 测试部署的 Agent
agentkit invoke 'Hello, show me one number.'
```

**重要提示：**

- 务必确保 `agentkit.yaml` 中的 `common.agent_type` 配置值为 `a2a`
- 否则无法成功部署 A2A 类型的 Agent

## 示例提示词

### 基础能力测试

**投掷骰子**：

```text
用户：Hello, show me one number.
Agent：I'll roll a die for you.
      [调用 roll_die(sides=6)]
      I rolled a 4.
```

### 复合任务

**多次投掷并统计：**

```text
用户：Please roll 10 times, show counts, and tell me which results are prime.
Agent：[连续调用 roll_die 10 次]
      Results: 3, 7, 2, 5, 8, 1, 9, 4, 6, 3
      [调用 check_prime([3, 7, 2, 5, 8, 1, 9, 4, 6, 3])]
      Prime numbers found: 2, 3, 5, 7
```

### 指定参数

**自定义骰子面数：**

```text
用户：Roll a 12-sided die.
Agent：[调用 roll_die(sides=12)]
      I rolled an 8 on a 12-sided die.
```

### 状态记忆

**查询历史记录：**

```text
用户：Show previous roll history.
Agent：[读取 tool_context.state['rolls']]
      Your previous rolls: [4, 8, 3, 7, 2]
```

### 实际运行输出

运行 `local_client.py` 的示例输出：

```text
5 are prime numbers.
No prime numbers found.
3 are prime numbers.
5 are prime numbers.
2 are prime numbers.
5 are prime numbers.
3 are prime numbers.
5 are prime numbers.
5 are prime numbers.
3 are prime numbers.
```

## 效果展示

## 技术要点

### A2A 协议

- **标准化通信**：Agent 之间的标准化通信协议
- **Agent Card**：描述 Agent 的元数据和能力
- **传输协议**：支持 HTTP/JSON 和 JSONRPC
- **互操作性**：不同实现的 Agent 可以互相调用

### Agent Card

Agent Card 提供以下信息：

- **基本信息**：名称、描述、版本
- **能力**：支持的功能（如流式输出）
- **技能**：Agent 可以执行的任务
- **接口**：输入输出模式（文本、图片等）

访问方式：

```bash
# 远程 Agent Card
http://localhost:8001/.well-known/agent-card.json

# 本地 Agent Card（如果启动了 agent.py）
http://localhost:8000/.well-known/agent-card.json
```

### 工具状态管理

`ToolContext.state`

- 在工具调用之间持久化状态
- 支持复杂的状态管理逻辑
- 示例：记录投掷历史

```python
tool_context.state['rolls'] = tool_context.state['rolls'] + [result]
```

### 远程调用流程

**方式一：直接客户端调用（local_client.py）：**

1. **获取 Agent Card**：了解远程 Agent 的能力
2. **创建客户端**：基于 Agent Card 创建 A2A 客户端
3. **发送消息**：通过 A2A 协议发送请求
4. **接收响应**：处理远程 Agent 的响应

**方式二：Agent 级联调用（agent.py）：**

1. **定义 RemoteVeAgent**：配置远程 Agent 的 URL
2. **注册为 sub_agents**：将远程 Agent 注册到本地 Agent
3. **自动路由**：本地 Agent 自动将任务委派给合适的 Agent
4. **统一接口**：对外提供统一的 A2A 接口

### Agent 级联（Sub-Agents）

通过 `sub_agents` 参数，可以构建 Agent 级联架构：

```python
from veadk.a2a.remote_ve_agent import RemoteVeAgent

remote_agent = RemoteVeAgent(
    name="a2a_agent",
    url="http://localhost:8001/",
)

agent = Agent(
    name="a2a_sample_agent",
    tools=[add],
    sub_agents=[remote_agent],  # 级联远程 Agent
)
```

**优势：**

- 本地 Agent 可以同时使用本地工具和远程 Agent 的工具
- 自动处理工具路由和调用
- 支持多个远程 Agent 级联
- 对外暴露统一的 A2A 接口

### AgentKit A2A App

```python
from agentkit.apps import AgentkitA2aApp

a2a_app = AgentkitA2aApp()

@a2a_app.agent_executor(runner=runner)
class MyAgentExecutor(A2aAgentExecutor):
    pass

a2a_app.run(agent_card=agent_card, host="0.0.0.0", port=8000)
```

## 下一步

完成 A2A Simple 示例后，可以探索更多功能：

1. **[Multi Agents](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/multi_agents/README.md)** - 构建多智能体协作系统
2. **[Restaurant Ordering](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/restaurant_ordering/README.md)** - 高级 Agent 特性
3. **[Travel Concierge](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/travel_concierge/README.md)** - 使用 Web 搜索工具
4. **分布式系统**：部署多个 A2A Agent 构建分布式智能体网络

## 常见问题

无。

## 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)
- [A2A 协议规范](https://github.com/google/adk)
- [火山方舟模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)

## 代码许可

本工程遵循 Apache 2.0 License
