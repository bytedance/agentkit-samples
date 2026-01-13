# Hello World - 最简单的聊天 Agent

基于火山引擎 VeADK 和 AgentKit 构建的入门级对话智能体，展示如何创建一个具备短期记忆能力的基础 AI Agent。

## 概述

本示例是 AgentKit 的 "Hello World"，展示最基本的 Agent 构建流程。

## 核心功能

- 创建一个简单的对话 Agent
- 使用本地短期记忆维护对话上下文
- 实现多轮对话中的信息记忆
- 支持本地调试和云端部署

## Agent 能力

```text
用户消息
    ↓
AgentKit 运行时
    ↓
Hello World Agent
    ├── VeADK Agent (对话引擎)
    ├── ShortTermMemory (会话记忆)
    └── 火山方舟模型 (LLM)
```

### 核心组件

| 组件 | 描述 |
| - | - |
| **Agent 服务** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/01_hello_world.py) - 主应用程序，定义 Agent 和记忆组件 |
| **测试客户端** | [client.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/01_hello_world/client.py) - SSE 流式调用客户端 |
| **项目配置** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/01_hello_world/pyproject.toml) - 依赖管理（uv 工具） |
| **AgentKit 配置** | agentkit.yaml - 云端部署配置文件 |
| **短期记忆** | 使用本地后端存储会话上下文 |

### 代码特点

**Agent 定义**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/01_hello_world/agent.py#L11-L18)）：

```python
agent = Agent()
short_term_memory = ShortTermMemory(backend="local")

runner = Runner(
    agent=agent,
    short_term_memory=short_term_memory,
    app_name=app_name,
    user_id=user_id
)
```

**多轮对话测试**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/01_hello_world/agent.py#L21-L26)）：

```python
async def main():
    response1 = await runner.run(messages="我叫VeADK", session_id=session_id)
    response2 = await runner.run(messages="你还记得我叫什么吗？", session_id=session_id)
```

## 目录结构说明

```bash
01_hello_world/
├── agent.py           # Agent 应用入口
├── client.py          # 测试客户端（SSE 流式调用）
├── requirements.txt   # Python 依赖列表 （agentkit部署时需要指定依赖文件)
├── pyproject.toml     # 项目配置（uv 依赖管理）
├── agentkit.yaml      # AgentKit 部署配置（运行agentkit config之后会自动生成）
├── Dockerfile         # Docker 镜像构建文件（运行agentkit config之后会自动生成）
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
cd python/01-tutorials/01-agentkit-runtime/01_hello_world
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
cd python/01-tutorials/01-agentkit-runtime

# 启动 VeADK Web 界面
veadk web --port 8080

# 在浏览器访问：http://127.0.0.1:8080
```

Web 界面提供图形化对话测试环境，支持实时查看消息流和调试信息。

#### 方式二：命令行测试

```bash
cd python/01-tutorials/01-agentkit-runtime/01_hello_world

# 启动 Agent 服务
uv run agent.py
# 服务将监听 http://0.0.0.0:8000

# 新开终端，运行测试客户端
# 需要编辑 client.py，将其中的第 14 行和第 15 行的 base_url 和 api_key 修改为 agentkit.yaml 中生成的 runtime_endpoint 和 runtime_apikey 字段
uv run client.py
```

**运行效果**：

```bash
[create session] Response from server: {"session_id": "agentkit_session"}
[run agent] Event from server:
data: {"event":"on_agent_start",...}
data: {"event":"on_llm_chunk","data":{"content":"你好VeADK！很高兴认识你。"}}
data: {"event":"on_llm_chunk","data":{"content":"当然记得，你叫VeADK。"}}
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
cd python/01-tutorials/01-agentkit-runtime/01_hello_world

# 配置部署参数
agentkit config

# 启动云端服务
agentkit launch

# 测试部署的 Agent
agentkit invoke 'who r u'

# 或使用 client.py 连接云端服务
# 需要编辑 client.py，将其中的第 14 行和第 15 行的 base_url 和 api_key 修改为 agentkit.yaml 中生成的 runtime_endpoint 和 runtime_apikey 字段
uv run client.py
```

## 示例提示词

### 基础对话测试

**测试短期记忆**：

```text
用户：我叫VeADK
Agent：你好VeADK！很高兴认识你。

用户：你还记得我叫什么吗？
Agent：当然记得，你叫VeADK。
```

### 更多测试场景

**测试信息记忆**：

```text
用户：我今年25岁，喜欢编程
Agent：收到！你25岁，喜欢编程，很棒的爱好。

用户：我多大了？有什么爱好？
Agent：你今年25岁，喜欢编程。
```

**测试上下文关联**：

```text
用户：我住在北京，在一家互联网公司工作
Agent：明白了，你在北京工作，在互联网公司。

用户：你知道我的基本情况吗？
Agent：知道的，你叫VeADK，25岁，喜欢编程，在北京的一家互联网公司工作。
```

## 效果展示

## 技术要点

### 短期记忆

- **存储方式**：本地内存（`backend="local"`）
- **作用范围**：单个 session_id 内的所有对话
- **生命周期**：进程重启后清空
- **适用场景**：开发调试、单机部署

### 多轮对话

- 通过 `session_id` 关联同一会话
- 每次调用时自动加载历史消息
- Agent 根据上下文理解用户意图

### AgentKit 集成

```python
from agentkit.apps import AgentkitAgentServerApp

agent_server_app = AgentkitAgentServerApp(
    agent=agent,
    short_term_memory=short_term_memory,
)
```

## 常见问题

无。

## 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)
- [火山方舟模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)

## 代码许可

本工程遵循 Apache 2.0 License
