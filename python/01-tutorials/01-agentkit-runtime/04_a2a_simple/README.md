# A2A Simple - Agent-to-Agent 通信协议

基于火山引擎 VeADK 和 A2A (Agent-to-Agent) 协议构建的智能体示例，展示如何实现标准化的智能体服务。

## 概述

本示例演示 A2A 协议的基础应用，展示如何构建符合 A2A 协议标准的智能体服务。

## 核心功能

- A2A 协议：标准化的智能体间通信协议
- Agent 服务：提供工具能力的 A2A Agent
- 客户端调用：通过 A2A 协议调用 Agent 服务
- 工具能力：投掷骰子和检查质数
- 状态管理：跨工具调用的状态持久化

## Agent 能力

```text
客户端调用流程
本地客户端 (local_client.py)
    ↓
A2A 协议 (HTTP/JSONRPC)
    ↓
Agent 服务 (agent.py:8000)
    ├── roll_die 工具 (投掷骰子)
    │   └── 状态管理：rolls 历史
    │
    └── check_prime 工具 (检查质数)
```

## 目录结构说明

```bash
04_a2a_simple/
├── agent.py                 # Agent 服务（端口 8000）
├── local_client.py          # A2A 客户端实现
├── tools/                   # 工具实现
│   ├── roll_die.py         # 投掷骰子工具
│   └── check_prime.py      # 质数检查工具
├── agentkit.yaml           # AgentKit 部署配置
├── requirements.txt        # Python 依赖
├── pyproject.toml          # 项目配置
├── Dockerfile              # Docker 镜像构建
└── README.md               # 项目说明文档
```

### 核心组件

| 组件 | 描述 |
| - | - |
| **Agent 服务** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/01-tutorials/01-agentkit-runtime/04_a2a_simple/agent.py) - hello_world_agent，提供工具服务（端口 8000） |
| **本地客户端** | [local_client.py](https://github.com/volcengine/agentkit-samples/blob/main/01-tutorials/01-agentkit-runtime/04_a2a_simple/local_client.py) - A2ASimpleClient，调用 Agent 服务 |
| **工具：roll_die** | [tools/roll_die.py](https://github.com/volcengine/agentkit-samples/blob/main/01-tutorials/01-agentkit-runtime/04_a2a_simple/tools/roll_die.py) - 投掷骰子 |
| **工具：check_prime** | [tools/check_prime.py](https://github.com/volcengine/agentkit-samples/blob/main/01-tutorials/01-agentkit-runtime/04_a2a_simple/tools/check_prime.py) - 检查质数 |
| **AgentCard** | Agent 元数据和能力描述 |
| **项目配置** | [agentkit.yaml](https://github.com/volcengine/agentkit-samples/blob/main/01-tutorials/01-agentkit-runtime/04_a2a_simple/agentkit.yaml) - AgentKit 部署配置 |

### 代码特点

**Agent 定义**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/01-tutorials/01-agentkit-runtime/04_a2a_simple/agent.py#L9-L35)）：

```python
root_agent = Agent(
    name="hello_world_agent",
    description=(
        "hello world agent that can roll a dice of 8 sides and check prime numbers."
    ),
    instruction="""
      You roll dice and answer questions about the outcome of the dice rolls.
      You can roll dice of different sizes.
      You can use multiple tools in parallel by calling functions in parallel(in one request and in one round).
      It is ok to discuss previous dice roles, and comment on the dice rolls.
      When you are asked to roll a die, you must call the roll_die tool with the number of sides. Be sure to pass in an integer. Do not pass in a string.
      You should never roll a die on your own.
      When checking prime numbers, call the check_prime tool with a list of integers. Be sure to pass in a list of integers. You should never pass in a string.
      You should not check prime numbers before calling the tool.
      When you are asked to roll a die and check prime numbers, you should always make the following two function calls:
      1. You should first call the roll_die tool to get a roll. Wait for the function response before calling the check_prime tool.
      2. After you get the function response from roll_die tool, you should call the check_prime tool with the roll_die result.
        2.1 If user asks you to check primes based on previous rolls, make sure you include the previous rolls in the list.
      3. When you respond, you must include the roll_die result from step 1.
      You should always perform the previous 3 steps when asking for a roll and checking prime numbers.
      You should not rely on the previous history on prime results.
    """,
    tools=[
        roll_die,
        check_prime,
    ],
)
```

**AgentCard 配置**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/01-tutorials/01-agentkit-runtime/04_a2a_simple/agent.py#L45-L55)）：

```python
agent_card = AgentCard(
    capabilities=AgentCapabilities(streaming=True),
    description=root_agent.description,
    name=root_agent.name,
    default_input_modes=["text"],
    default_output_modes=["text"],
    provider=AgentProvider(organization="agentkit", url=""),
    skills=[AgentSkill(id="0", name="chat", description="Chat", tags=["chat"])],
    url="http://localhost:8000",
    version="1.0.0",
)
```

**本地客户端调用**（[local_client.py](https://github.com/volcengine/agentkit-samples/blob/main/01-tutorials/01-agentkit-runtime/04_a2a_simple/local_client.py#L28-L88)）：

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

**工具状态管理**（[tools/roll_die.py](https://github.com/volcengine/agentkit-samples/blob/main/01-tutorials/01-agentkit-runtime/04_a2a_simple/tools/roll_die.py#L6-L21)）：

```python
def roll_die(sides: int, tool_context: ToolContext) -> int:
    result = random.randint(1, sides)

    # 状态持久化
    if "rolls" not in tool_context.state:
        tool_context.state["rolls"] = []

    tool_context.state["rolls"] = tool_context.state["rolls"] + [result]
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
cd python/01-tutorials/01-agentkit-runtime/04_a2a_simple
```

使用 `uv` 工具来安装本项目依赖：

```bash
# 如果没有 `uv` 虚拟环境，可以使用命令先创建一个虚拟环境
uv venv --python 3.12

# 激活虚拟环境
source .venv/bin/activate

# 使用 `pyproject.toml` 管理依赖
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple
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
cd python/01-tutorials/01-agentkit-runtime

# 启动 VeADK Web 界面
veadk web

# 在浏览器访问：http://127.0.0.1:8000
```

Web 界面提供图形化对话测试环境，支持实时查看调用过程。

#### 方式二：命令行测试（推荐学习）

**步骤 1：启动 Agent 服务：**

```bash
# 在终端窗口 1 中运行
cd python/01-tutorials/01-agentkit-runtime/04_a2a_simple
uv run agent.py

# 服务启动后，可访问 Agent Card
# http://localhost:8000/.well-known/agent-card.json
```

**步骤 2：运行本地客户端：**

```bash
# 在终端窗口 2 中运行
cd python/01-tutorials/01-agentkit-runtime/04_a2a_simple
python local_client.py
```

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
cd python/01-tutorials/01-agentkit-runtime/04_a2a_simple

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
# Agent Card
http://localhost:8000/.well-known/agent-card.json
```

### 工具状态管理

`ToolContext.state`

- 在工具调用之间持久化状态
- 支持复杂的状态管理逻辑
- 示例：记录投掷历史

```python
tool_context.state["rolls"] = tool_context.state["rolls"] + [result]
```

### 调用流程

**客户端调用流程（local_client.py）：**

1. **获取 Agent Card**：了解 Agent 的能力
2. **创建客户端**：基于 Agent Card 创建 A2A 客户端
3. **发送消息**：通过 A2A 协议发送请求
4. **接收响应**：处理 Agent 的响应

### AgentKit A2A App

```python
from agentkit.apps import AgentkitA2aApp
from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor

a2a_app = AgentkitA2aApp()

@a2a_app.agent_executor(runner=runner)
class MyAgentExecutor(A2aAgentExecutor):
    pass

a2a_app.run(agent_card=agent_card, host="0.0.0.0", port=8000)
```

## 常见问题

无。

## 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)
- [A2A 协议规范](https://github.com/google/adk)
- [火山方舟模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)

## 代码许可

本工程遵循 Apache 2.0 License
