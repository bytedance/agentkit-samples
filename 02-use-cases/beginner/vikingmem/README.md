# VikingMem - 长短期记忆智能体

基于火山引擎 VeADK 和 VikingDB 构建的记忆管理示例，展示如何实现智能体的短期记忆和长期记忆功能。

## 📋 概述

本示例演示 VeADK 的两种记忆机制，帮助理解智能体的记忆系统：

- 短期记忆：仅在同一会话（session）内有效
- 长期记忆：基于 VikingDB，可跨会话持久化存储
- 记忆转换：将短期记忆转换为长期记忆
- 记忆检索：通过 LoadMemory 工具查询历史信息

## 🏗️ 架构

```
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

| 组件                 | 描述                                                |
| -------------------- | --------------------------------------------------- |
| **Agent 服务** | [agent.py](agent.py) - 主应用程序，集成短期和长期记忆  |
| **测试脚本**   | [local_test.py](local_test.py) - 完整的记忆功能演示    |
| **短期记忆**   | ShortTermMemory - 会话级别的临时存储                |
| **长期记忆**   | LongTermMemory - VikingDB 持久化存储                |
| **项目配置**   | [pyproject.toml](pyproject.toml) - 依赖管理（uv 工具） |

### 代码特点

**短期记忆配置**（[local_test.py](local_test.py:26-34)）：

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

**长期记忆配置**（[local_test.py](local_test.py:56-69)）：

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

## 🚀 快速开始

### 前置条件

**重要提示**：在运行本示例之前，请先访问 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 对所有依赖服务进行授权，确保案例能够正常执行。

**1. 开通火山方舟模型服务**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)
- 开通模型服务

**2. 开通 VikingDB 记忆库**

- 访问 [VikingDB 控制台](https://console.volcengine.com/vikingdb/region:vikingdb+cn-beijing/home?projectName=default)
- 创建记忆库实例

**3. 获取火山引擎访问凭证**

- 参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK

### 安装步骤

#### 1. 安装 uv 包管理器

```bash
# macOS / Linux（官方安装脚本）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 Homebrew（macOS）
brew install uv
```

#### 2. 初始化项目依赖

```bash
cd 02-use-cases/beginner/vikingmem

# 初始化虚拟环境和安装依赖
uv sync

# 激活虚拟环境
source .venv/bin/activate
```

#### 3. 配置环境变量

```bash
# 火山方舟模型名称
export MODEL_AGENT_NAME=doubao-seed-1-6-251015

# 火山引擎访问凭证（必需）
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### 运行方式

#### 方式一：部署到 AgentKit 平台（推荐）

```bash
cd vikingmem

# 配置部署参数
agentkit config

# 启动云端服务
agentkit launch

# 测试部署的 Agent
agentkit invoke 'What is my habby?'

# 或使用 client.py 连接云端服务
# 需要编辑 client.py，将其中的第 14 行和第 15 行的 base_url 和 api_key 修改为 agentkit.yaml 中生成的 runtime_endpoint 和 runtime_apikey 字段
# 按需修改 client.py，第 56 行，请求的内容
uv run client.py
```

#### 方式二：使用 VeADK Web 调试界面

```bash
# 进入上级目录
cd ..

# 启动 VeADK Web 界面
veadk web

# 在浏览器访问：http://127.0.0.1:8000
```

Web 界面提供图形化对话测试环境，支持实时查看记忆状态和调试信息。

#### 方式三：命令行测试（推荐学习）

```bash
# 运行完整的记忆功能演示
uv run local_test.py

# 或直接启动 Agent 服务
uv run agent.py
# 服务将监听 http://0.0.0.0:8000
```

#### 方式四：部署到火山引擎 veFaaS

**安全提示**：

> 以下命令仅用于开发测试。生产环境必须启用 `VEFAAS_ENABLE_KEY_AUTH=true`（默认值）并配置 IAM 角色。

```bash
cd vikingmem

# 配置环境变量（仅测试用）
export VEFAAS_ENABLE_KEY_AUTH=false
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>

# 基础部署（快速开始）
veadk deploy --vefaas-app-name=vikingmem-agent --use-adk-web

# 生产级部署（推荐）
veadk deploy \
  --vefaas-app-name=vikingmem-agent \
  --use-adk-web \
  --veapig-instance-name=<Your veaPIG Instance> \
  --iam-role "trn:iam::<Your Account ID>:role/<Your IAM Role>"
```

## 💡 示例对话

### 短期记忆测试

**存入信息到短期记忆**：

```
用户：My habby is 0xabcd
Agent：Got it! Your hobby is 0xabcd.
（信息存储在 session: history_session）
```

**同会话查询（成功）**：

```
用户：What is my habby?
Agent：Your hobby is 0xabcd.
（使用相同的 session_id: history_session）
```

**新会话查询（失败）**：

```
用户：What is my habby?
Agent：I don't have that information.
（使用不同的 session_id: new_session，短期记忆不可用）
```

### 长期记忆测试

**转换为长期记忆**：

```python
# 将短期记忆保存到长期记忆
await runner1.save_session_to_long_term_memory(session_id=history_session_id)
```

**跨会话查询（成功）**：

```
用户：What is my habby?
Agent：Based on my memory, your hobby is 0xabcd.
（使用新的 session_id: new_session，长期记忆生效）
（Agent 自动调用 LoadMemory 工具检索历史信息）
```

### 完整演示流程

运行 `local_test.py` 可以看到完整的记忆功能演示：

```
Response 1: Got it! Your hobby is 0xabcd.

Response 2: Your hobby is 0xabcd.
（短期记忆生效）

Response 3: I don't have that information.
（新会话，短期记忆失效）

Response 4: Based on my memory, your hobby is 0xabcd.
（长期记忆生效，跨会话检索成功）
```

## 📂 目录结构

```
vikingmem/
├── agent.py           # Agent 应用入口
├── local_test.py      # 完整的记忆功能演示脚本
├── requirements.txt   # Python 依赖列表（agentkit部署时需要指定依赖文件）
├── pyproject.toml     # 项目配置（uv 依赖管理）
└── README.md          # 项目说明文档
```

## 🔍 技术要点

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

## 🎯 下一步

完成 VikingMem 示例后，可以探索更多功能：

1. **[VikingDB](../vikingdb/README.md)** - 构建文档知识库
2. **[Episode Generation](../episode_generation/README.md)** - 生成图片和视频内容
3. **[Restaurant Ordering](../restaurant_ordering/README.md)** - 构建复杂的业务流程 Agent
4. **[Multi Agents](../multi_agents/README.md)** - 构建多智能体协作系统

## 📖 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)
- [火山方舟模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
- [VikingDB 文档](https://www.volcengine.com/docs/84313/1860732?lang=zh)
