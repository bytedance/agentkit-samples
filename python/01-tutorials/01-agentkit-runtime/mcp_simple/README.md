# MCPSimpleAgent - MCP 协议工具集成示例

基于火山引擎 VeADK 和 AgentKit 构建的 MCP (Model Context Protocol) 集成示例，展示如何通过 `mcp_router` 调用 MCP 工具集。

## 概述

本示例展示 Agent 如何通过内置的 `mcp_router` 工具集成和调度 MCP 工具集。Agent 被配置为一个具备深度推理能力的助手，能够根据用户意图自动路由到相应的 MCP 工具完成任务。

## 核心功能

- 集成火山 MCP Server 作为 Agent 工具
- 用户自然语言指令，agent 调用 MCP 工具集完成任务。
- 使用 MCPToolset 管理工具连接和调用
- 展示生产级工具集成模式

## Agent 能力

```text
用户自然语言指令
    ↓
AgentKit 运行时
    ↓
TOS MCP Agent
    ├── VeADK Agent (对话引擎)
    ├── MCPToolset (工具管理器)
    │   └── mcp_search_tool (搜索工具)
    │   └── mcp_use_tool (使用工具)
    │ 
    └── ShortTermMemory (会话记忆)
```

### 核心组件

| 组件 | 描述 |
| - | - |
| **Agent 服务** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/mcp_simple/agent.py) - 集成 MCP 工具的 Agent 应用 |
| **测试客户端** | [client.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/mcp_simple/client.py) - SSE 流式调用客户端 |
| **项目配置** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/mcp_simple/pyproject.toml) - 依赖管理（uv 工具） |
| **短期记忆** | 本地后端存储会话上下文 |

### 代码特点

**Agent 配置**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/01-agentkit-runtime/mcp_simple/agent.py#L10-L20)）：

```python
root_agent = Agent(
    name="mcp_agent",
    instruction="你是一个具备深度推理能力的 AI 助手。当你遇到复杂逻辑、数学、编程或需要多步推理的问题时，请务必使用MCP工具辅助完成用户的问题。",
    tools=[mcp_router],  # 集成 MCP 路由工具
    model_extra_config={
        "extra_body": {
            "thinking": {"type": "disabled"}
        }
    },
)
```

## 目录结构说明

```bash
mcp_simple/
├── agent.py           # Agent 应用入口
├── client.py          # 测试客户端
├── requirements.txt   # Python 依赖列表
├── pyproject.toml     # 项目配置（uv 依赖管理）
└── README.md          # 项目说明文档
```

## 本地运行

### 前置准备

**1. 开通火山方舟模型服务**
- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat) 并开通服务。

**2. 获取访问凭证**
- 参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK。

**3. 准备 MCP 服务**
- 参考 [火山MCP工具集](https://www.volcengine.com/docs/86681/1844858?lang=zh) 配置和启动MCP服务创建MCP工具集，并且获取URL和API Key。

### 依赖安装

#### 1. 安装 uv 包管理器

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 2. 初始化项目依赖

```bash
cd python/01-tutorials/01-agentkit-runtime/mcp_simple

# 创建虚拟环境并安装依赖
uv venv --python 3.12
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple
source .venv/bin/activate
```

### 环境配置

```bash
# 火山方舟模型名称
export MODEL_AGENT_NAME=deepseek-v3-2-251201

# 火山引擎访问凭证
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>

# 火山MCP工具集地址和访问凭证
export TOOL_MCP_ROUTER_URL=https://*****.apigateway-cn-****.volceapi.com/mcp
export TOOL_MCP_ROUTER_API_KEY=<Your API Key>
```

### 调试方法

#### 1. 启动 Agent 服务

```bash
uv run agent.py
```

#### 2. 运行测试客户端

```bash
# 运行客户端
uv run client.py
```

**运行效果示例**：

```text
[run agent] Event from server:
[create session] Response from server: {'id': 'agentkit_session', 'appName': 'mcp_agent', 'userId': 'agentkit_user', 'state': {}, 'events': [], 'lastUpdateTime': 1768465256.520708}
data: {"modelVersion":"deepseek-v3-2-251201"...
...
```

#### 3. 使用 VeADK Web 调试

```bash
cd python/01-tutorials/01-agentkit-runtime
veadk web
# 访问 http://127.0.0.1:8000
```

## AgentKit 部署

### 云上部署流程

**1. 授权与准备**
确保已在 [AgentKit 控制台](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 完成服务授权。

**2. 部署命令**

```bash
cd python/01-tutorials/01-agentkit-runtime/mcp_simple

# 生成/更新配置
agentkit config
注意: Application-level runtime environment variables  需要配置上 MODEL_AGENT_NAME, TOOL_MCP_ROUTER_URL 和 TOOL_MCP_ROUTER_API_KEY 三个环境变量
# 启动云端服务
agentkit launch

# 命令行测试
agentkit invoke '一只青蛙一次可以跳 1 级台阶，也可以跳 2 级。它要跳上一个 10 级台阶，总共有多少种跳法？如果是 n 级呢？'
```

**3. 使用 Client 连接云端**
修改 `client.py` 中的 `base_url` 和 `api_key` 为 `agentkit.yaml` 中生成的 `runtime_endpoint` 和 `runtime_apikey`，然后运行：

```bash
uv run client.py
```

## 技术要点

### `mcp_router` 工具

`mcp_router` 是 VeADK 框架提供的通用 MCP 路由工具。它不仅仅是一个单一的工具，而是一个能够感知和分发请求到多个 MCP Server 的网关。

- **自动路由**：根据用户指令，自动选择合适的 MCP 工具。
- **协议封装**：屏蔽了底层的 MCP 协议细节（如 JSON-RPC 消息格式）。
- **统一接口**：Agent 只需与 `mcp_router` 交互，无需单独管理每个 MCP 连接。

### 深度推理配置

Agent 在配置时指定了 `instruction` 强调深度推理能力：

```python
instruction="你是一个具备深度推理能力的 AI 助手...请务必使用MCP工具辅助完成用户的问题。"
```

这引导模型在面对复杂问题时，主动思考并利用外部工具（通过 MCP）来解决问题，而不是仅凭训练数据回答。

## 常见问题
无

## 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)
- [火山方舟模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
- [MCP 协议规范](https://modelcontextprotocol.io)
- [火山 MCP Marketplace](https://www.volcengine.com/mcp-marketplace)
- [TOS 对象存储文档](https://www.volcengine.com/docs/tos)

## 代码许可

本工程遵循 Apache 2.0 License
