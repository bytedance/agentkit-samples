# viking memory - 长短期记忆智能体

基于火山引擎 VeADK 和 VikingDB 构建的记忆管理示例，展示如何实现智能体的短期记忆和长期记忆功能。

## 概述

本示例演示 VeADK 的两种记忆机制，帮助理解智能体的记忆系统。

## 核心功能

- 短期记忆：仅在同一会话（session）内有效
- 长期记忆：基于 VikingDB，可跨会话持久化存储
- 记忆转换：将短期记忆转换为长期记忆
- 记忆检索：通过 LoadMemory 工具查询历史信息

## Agent 能力

```text
用户交互
    ↓
Agent + Runner
    ├── 短期记忆（ShortTermMemory）
    │   └── 本地内存存储
    │   └── session 级别隔离
    │
    └── 长期记忆（LongTermMemory）
        └── VikingDB 持久化
        └── 跨 session 共享
        └── LoadMemory 工具检索
```

### 核心组件

| 组件 | 描述 |
| - | - |
| **Agent 服务** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/05-agentkit-memory/01_viking_memory/agent.py) - 主应用程序，集成短期和长期记忆 |
| **测试脚本** | [local_test.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/05-agentkit-memory/01_viking_memory/local_test.py) - 完整的记忆功能演示 |
| **短期记忆** | ShortTermMemory - 会话级别的临时存储 |
| **长期记忆** | LongTermMemory - VikingDB 持久化存储 |
| **项目配置** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/05-agentkit-memory/01_viking_memory/pyproject.toml) - 依赖管理（uv 工具） |

### 代码特点

**短期记忆配置**（[local_test.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/05-agentkit-memory/01_viking_memory/local_test.py#L26-L34)）：

```python
# 短期记忆：仅同session有效
agent1 = Agent(name="test_agent", instruction="You are a helpful assistant.")

runner1 = Runner(
    agent=agent1,
    short_term_memory=ShortTermMemory(),
    app_name=app_name,
    user_id=user_id,
)
```

**长期记忆配置**（[local_test.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/05-agentkit-memory/01_viking_memory/local_test.py#L56-L69)）：

```python
# 初始化长期记忆（Viking后端）
long_term_memory = LongTermMemory(backend="viking", index=vikingmem_app_name)
agent1.long_term_memory = long_term_memory

# 短期转长期记忆
await runner1.save_session_to_long_term_memory(session_id=history_session_id)

# 长期记忆：跨session有效
agent2 = Agent(
    name="test_agent",
    instruction="Use LoadMemory tool to search previous info.",
    long_term_memory=long_term_memory,
)
```

## 目录结构说明

```text
01_viking_memory/
├── agent.py           # Agent 应用入口
├── local_test.py      # 完整的记忆功能演示脚本
├── requirements.txt   # Python 依赖列表（agentkit部署时需要指定依赖文件）
├── pyproject.toml     # 项目配置（uv 依赖管理）
└── README.md          # 项目说明文档
```

## 本地运行

### 前置准备

**1. 开通火山方舟模型服务：**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)
- 开通模型服务

**2. 开通 VikingDB 记忆库：**

- 访问 [VikingDB 控制台](https://console.volcengine.com/vikingdb/region:vikingdb+cn-beijing/home?projectName=default)
- 创建记忆库实例

**3. 获取火山引擎访问凭证：**

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
cd python/01-tutorials/05-agentkit-memory/01_viking_memory
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
cd python/01-tutorials/05-agentkit-memory

# 启动 VeADK Web 界面
veadk web

# 在浏览器访问：http://127.0.0.1:8000
```

Web 界面提供图形化对话测试环境，支持实时查看记忆状态和调试信息。

#### 方式二：命令行测试（推荐学习）

```bash
# 直接启动 Agent 服务
uv run agent.py
# 服务将监听 http://0.0.0.0:8000
uv run client.py # 测试记忆效果

# 运行完整的记忆功能演示
uv run local_test.py
```

## AgentKit 部署

### 前置准备

**重要提示**：在运行本示例之前，请先访问 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 对所有依赖服务进行授权，确保案例能够正常执行。

**1. 开通火山方舟模型服务：**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)
- 开通模型服务

**2. 开通 VikingDB 记忆库：**

- 访问 [VikingDB 控制台](https://console.volcengine.com/vikingdb/region:vikingdb+cn-beijing/home?projectName=default)
- 创建记忆库实例

**3. 获取火山引擎访问凭证：**

- 参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK

### AgentKit 云上部署

```bash
cd python/01-tutorials/05-agentkit-memory/01_viking_memory

# 配置部署参数
agentkit config \
--agent_name vikingmem_agent \
--entry_point 'agent.py' \
--runtime_envs VIKINGMEM_APP_NAME=vikingmem_agent_app \
--launch_type cloud

# 启动云端服务
agentkit launch

# 测试部署的 Agent
agentkit invoke 'What is my habby?'
```

## 示例提示词

### 短期记忆测试

**存入信息到短期记忆**：

```text
用户：我的爱好是 0xabcd
Agent：你的爱好是 0xabcd.
（信息存储在 session: history_session）
```

**同会话查询（成功）**：

```text
用户：我的爱好是什么？
Agent：你的爱好是 0xabcd.
（使用相同的 session_id: history_session）
```

### 长期记忆测试

**转换为长期记忆**：

```python
# 将短期记忆保存到长期记忆，这里我们已经默认给加到了长期记忆中
# 仅做记忆保存的演示，可以实现一个 tools，然后让 agent 根据实际需求选择会话内容保存到长期记忆中
async def after_agent_execution(callback_context: CallbackContext):
    session = callback_context._invocation_context.session
    await long_term_memory.add_session_to_memory(session)
```

**跨会话查询（成功）**：

```text
用户：我的爱好是什么？
Agent：根据记忆，你的爱好是 0xabcd.
（使用新的 session_id: new_session，长期记忆生效）
（Agent 自动调用 LoadMemory 工具检索历史信息）
```

### 完整演示流程

运行 `local_test.py` 可以看到完整的记忆功能演示：

```text
Response 1: 你的爱好是 0xabcd.

Response 2: 你的爱好是 0xabcd.
（短期记忆生效）

Response 3: 我没有这个信息.
（新会话，短期记忆失效）

Response 4: 根据我的记忆，你的爱好是 0xabcd.
（长期记忆生效，跨会话检索成功）
```

## 效果展示

## 技术要点

### 短期记忆（ShortTermMemory）

- **存储方式**：本地内存
- **作用范围**：单个 session_id 内的所有对话
- **生命周期**：进程重启后清空
- **适用场景**：单次会话的上下文维护
- **特点**：快速、轻量，但不持久

### 长期记忆（LongTermMemory）

- **存储方式**：VikingDB 向量数据库
- **作用范围**：跨 session，基于 user_id 和 app_name
- **生命周期**：持久化存储，不受进程影响
- **适用场景**：用户偏好、历史记录、知识积累
- **特点**：持久、可检索、支持语义搜索

### 记忆转换

```python
# 将短期记忆保存到长期记忆
await runner.save_session_to_long_term_memory(session_id=session_id)
```

### LoadMemory 工具

当 Agent 配置了长期记忆时，会自动获得 `LoadMemory` 工具：

```python
agent = Agent(
    instruction="Use LoadMemory tool to search previous info.",
    long_term_memory=long_term_memory,
)
```

Agent 可以自动调用 `LoadMemory` 工具检索历史记忆，无需手动处理。

### AgentKit 集成

```python
from agentkit.apps import AgentkitAgentServerApp

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)
```

## 常见问题

无。

## 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)
- [火山方舟模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
- [VikingDB 文档](https://www.volcengine.com/docs/84313/1860732?lang=zh)

## 代码许可

本工程遵循 Apache 2.0 License
