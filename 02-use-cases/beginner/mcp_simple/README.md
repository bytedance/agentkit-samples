# MCP Simple - MCP 协议工具集成示例

基于火山引擎 VeADK 和 AgentKit 构建的 MCP (Model Context Protocol) 集成示例，展示如何通过 MCP 协议让 Agent 调用火山引擎 TOS 对象存储服务。

## 📋 概述

本示例展示 Agent 如何集成 MCP 工具，实现对火山引擎对象存储（TOS）的智能化管理：

- 集成火山 MCP Server 作为 Agent 工具
- 通过自然语言操作对象存储（列举存储桶、查询文件、读取内容等）
- 使用 MCPToolset 管理工具连接和调用
- 展示生产级工具集成模式

## 🏗️ 架构

```
用户自然语言指令
    ↓
AgentKit 运行时
    ↓
TOS MCP Agent
    ├── VeADK Agent (对话引擎)
    ├── MCPToolset (工具管理器)
    │   └── 火山 TOS MCP Server
    │       ├── list_buckets (列举存储桶)
    │       ├── list_objects (列举对象)
    │       ├── get_object (读取文件)
    │       └── ... (更多 TOS 操作)
    └── ShortTermMemory (会话记忆)
```

### 核心组件

| 组件                 | 描述                                                |
| -------------------- | --------------------------------------------------- |
| **Agent 服务** | [agent.py](agent.py) - 集成 MCP 工具的 Agent 应用      |
| **测试客户端** | [client.py](client.py) - SSE 流式调用客户端            |
| **项目配置**   | [pyproject.toml](pyproject.toml) - 依赖管理（uv 工具） |
| **MCP 连接**   | `MCPToolset` - 通过 HTTP 连接火山 MCP Server      |
| **短期记忆**   | 本地后端存储会话上下文                              |

### 代码特点

**MCP 工具集成**（[agent.py](agent.py:8-15)）：

```python
url = os.getenv("TOOL_TOS_URL")

tos_mcp_runner = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=url,
        timeout=120
    ),
)
```

**Agent 配置**（[agent.py](agent.py:21-26)）：

```python
root_agent = Agent(
    name="tos_mcp_agent",
    instruction="你是一个对象存储管理专家，精通使用MCP协议进行对象存储的各种操作。",
    tools=[tos_mcp_runner],
)
```

## 🚀 快速开始

### 前置条件

**重要提示**：在运行本示例之前，请先访问 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 对所有依赖服务进行授权，确保案例能够正常执行。

**1. 开通火山方舟模型服务**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)
- 开通模型服务

**2. 获取火山引擎访问凭证**

- 参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK

**3. 获取 TOS MCP 服务 URL**

- 访问 [火山 MCP Marketplace](https://www.volcengine.com/mcp-marketplace)
- 找到 [TOS MCP](https://www.volcengine.com/mcp-marketplace/detail?name=TOS%20MCP) 服务
- 获取服务访问端点（包含 token 的 URL）

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
cd 02-use-cases/beginner/mcp_simple

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

# TOS MCP 服务地址（必需）
export TOOL_TOS_URL=https://tos.mcp.volcbiz.com/mcp?token=xxxxxx
```

**说明**：`TOOL_TOS_URL` 需要包含完整的认证 token，从火山 MCP Marketplace 获取。

### 运行方式

#### 方式一：命令行测试（推荐入门）

```bash
# 启动 Agent 服务
uv run agent.py
# 服务将监听 http://0.0.0.0:8000

# 新开终端，运行测试客户端
uv run client.py
```

**运行效果**：

```
[create session] Response from server: {"session_id": "agentkit_session"}
[run agent] Event from server:
data: {"event":"on_agent_start",...}
data: {"event":"on_tool_start","tool":"list_buckets"}
data: {"event":"on_llm_chunk","data":{"content":"您当前账号下有以下存储桶..."}}
```

#### 方式二：使用 VeADK Web 调试界面

```bash
# 进入上级目录
cd ..

# 启动 VeADK Web 界面
veadk web

# 在浏览器访问：http://127.0.0.1:8000
```

Web 界面可以实时查看 MCP 工具调用过程和返回结果。

#### 方式三：部署到火山引擎 veFaaS

**安全提示**：

> 以下命令仅用于开发测试。生产环境必须启用 `VEFAAS_ENABLE_KEY_AUTH=true`（默认值）并配置 IAM 角色。

```bash
cd mcp_simple

# 配置环境变量（仅测试用）
export VEFAAS_ENABLE_KEY_AUTH=false
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
export TOOL_TOS_URL=<Your MCP Service URL>

# 基础部署（快速开始）
veadk deploy --vefaas-app-name=mcp-simple-example --use-adk-web

# 生产级部署（推荐）
veadk deploy \
  --vefaas-app-name=mcp-simple-example \
  --use-adk-web \
  --veapig-instance-name=<Your veaPIG Instance> \
  --iam-role "trn:iam::<Your Account ID>:role/<Your IAM Role>"
```

#### 方式四：部署到 AgentKit 平台

```bash
cd mcp_simple

# 配置部署参数（需要设置 TOOL_TOS_URL 环境变量）
agentkit config

# 启动云端服务
agentkit launch

# 测试部署的 Agent
agentkit invoke '当前账号下有哪些存储桶'

# 或使用 client.py 连接云端服务
uv run client.py
```

## 💡 示例对话

### 查询存储桶列表

```
用户：当前账号下有哪些存储桶？
Agent：正在查询存储桶列表...
      [调用 MCP 工具：list_buckets]
      您当前账号下有以下存储桶：
      1. bucket-prod (北京区域)
      2. bucket-dev (上海区域)
      3. bucket-backup (广州区域)
```

### 查询对象列表

```
用户：bucket-prod 里面有哪些文件？
Agent：正在查询 bucket-prod 的文件列表...
      [调用 MCP 工具：list_objects]
      bucket-prod 中包含以下文件：
      - data/users.csv (1.2MB)
      - images/logo.png (156KB)
      - files/config.txt (2KB)
```

### 读取文件内容

```
用户：读取 bucket-prod 中 files 目录下 config.txt 的内容
Agent：正在读取文件内容...
      [调用 MCP 工具：get_object]
      config.txt 的内容如下：

      [系统配置]
      version=1.0.0
      debug=false
      ...
```

### 复杂查询

```
用户：帮我统计一下所有存储桶的总文件数量
Agent：好的，我来统计一下...
      [调用 MCP 工具：list_buckets]
      [调用 MCP 工具：list_objects (多次)]
      统计完成：
      - bucket-prod: 123 个文件
      - bucket-dev: 45 个文件
      - bucket-backup: 78 个文件
      总计: 246 个文件
```

## 📂 目录结构

```
mcp_simple/
├── agent.py           # Agent 应用入口（含 MCP 集成）
├── client.py          # 测试客户端（SSE 流式调用）
├── requirements.txt   # Python 依赖列表 （agentkit部署时需要指定依赖文件)
├── pyproject.toml     # 项目配置（uv 依赖管理）
├── .python-version    # Python 版本声明（3.12）
├── agentkit.yaml      # AgentKit 部署配置 （运行agentkit config之后会自动生成）
├── Dockerfile         # Docker 镜像构建文件 （运行agentkit config之后会自动生成）
└── README.md          # 项目说明文档
```

## 🔍 技术要点

### MCP 协议集成

**什么是 MCP**：

Model Context Protocol（MCP）是一个标准化协议，用于 AI 模型与外部工具/服务的交互。

**集成方式**：

1. **连接配置**：

```python
connection_params = StreamableHTTPConnectionParams(
    url="https://tos.mcp.volcbiz.com/mcp?token=xxx",
    timeout=120
)
```

2. **工具注册**：

```python
tos_mcp_runner = MCPToolset(connection_params=connection_params)
agent = Agent(tools=[tos_mcp_runner])
```

3. **自动工具发现**：MCPToolset 会自动发现 MCP Server 提供的所有工具

### 工具调用流程

1. 用户输入自然语言指令
2. Agent 理解用户意图
3. Agent 选择合适的 MCP 工具
4. 通过 HTTP 调用 MCP Server
5. 解析工具返回结果
6. 生成自然语言响应

### 与普通工具的区别

| 特性               | 普通工具             | MCP 工具                 |
| ------------------ | -------------------- | ------------------------ |
| **定义方式** | 在代码中直接定义函数 | 通过 MCP Server 远程提供 |
| **工具发现** | 需要手动注册         | 自动发现所有可用工具     |
| **扩展性**   | 需要修改代码         | 只需更新 MCP Server      |
| **适用场景** | 简单、本地工具       | 复杂、远程服务           |

### 火山 TOS MCP 支持的操作

常见操作包括：

- **存储桶管理**：list_buckets, head_bucket
- **对象操作**：list_objects, get_object, put_object, delete_object
- **对象属性**：head_object, copy_object
- **访问控制**：get_object_acl, set_object_acl
- **更多操作**：参考 [TOS API 文档](https://www.volcengine.com/docs/tos)

## 🎯 下一步

完成 MCP 集成后，可以探索：

1. **自定义 MCP Server** - 将自己的服务封装为 MCP Server
2. **[Multi Agents](../multi_agents/README.md)** - 在多智能体系统中使用 MCP 工具
3. **[Travel Concierge](../travel_concierge/README.md)** - 结合其他工具类型
4. **[Video Generator](../../video_gen/README.md)** - 复杂工具链编排

## 📖 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)
- [火山方舟模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
- [MCP 协议规范](https://modelcontextprotocol.io)
- [火山 MCP Marketplace](https://www.volcengine.com/mcp-marketplace)
- [TOS 对象存储文档](https://www.volcengine.com/docs/tos)
