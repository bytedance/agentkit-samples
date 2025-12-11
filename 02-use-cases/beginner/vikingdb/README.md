# VikingDB - 文档知识库智能问答

基于火山引擎 VeADK 和 VikingDB 构建的 RAG（检索增强生成）示例，展示如何通过向量检索实现专业文档知识库的智能问答。

## 📋 概述

本示例演示如何使用 VikingDB 构建文档知识库，实现基于真实文档内容的专业问答系统：

- 直接导入文档无需手动切片
- 自动构建向量索引
- 基于语义检索增强回答准确性
- 支持多文档源的复合查询

## 🏗️ 架构

```
用户查询
    ↓
Agent (知识问答)
    ↓
VikingDB 检索
    ├── 向量索引查询
    ├── 文档内容检索
    └── 相关性排序
    ↓
LLM 生成回答
```

### 核心组件

| 组件 | 描述 |
|-----------|-------------|
| **Agent 服务** | [agent.py](agent.py) - 主应用程序，集成 KnowledgeBase 和 VikingDB |
| **知识库** | VikingDB 向量数据库，存储文档向量索引 |
| **文档源** | tech.txt（技术文档）、products.txt（产品信息） |
| **项目配置** | [pyproject.toml](pyproject.toml) - 依赖管理（uv 工具） |
| **短期记忆** | 维护会话上下文 |

### 代码特点

**知识库创建**（[agent.py](agent.py:22-29)）：
```python
# 准备知识源
with open("/tmp/tech.txt", "w") as f:
    f.write("Python: programming language\nJavaScript: web development")
with open("/tmp/products.txt", "w") as f:
    f.write("Laptop: $1200\nPhone: $800\nTablet: $600")

# 创建知识库
kb = KnowledgeBase(backend="viking", app_name="test_app")
kb.add_from_files(files=["/tmp/tech.txt", "/tmp/products.txt"])
```

**Agent 配置**（[agent.py](agent.py:31-36)）：
```python
root_agent = Agent(
    name="test_agent",
    knowledgebase=kb,
    instruction="You are a helpful assistant. Be concise and friendly.",
)
```

## 🚀 快速开始

### 前置条件

**重要提示**：在运行本示例之前，请先访问 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 对所有依赖服务进行授权，确保案例能够正常执行。

**1. 开通火山方舟模型服务**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)
- 开通模型服务

**2. 开通 VikingDB 服务**

- 访问 [VikingDB 控制台](https://console.volcengine.com/vikingdb/region:vikingdb+cn-beijing/home?projectName=default)
- 创建知识库/Collection

**3. 开通对象存储服务（TOS）**

- VikingDB 需要将本地文件上传到 TOS，因此需要开通对象存储服务
- 访问 [TOS 控制台](https://console.volcengine.com/tos)

**4. 获取火山引擎访问凭证**

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
cd 02-use-cases/beginner/vikingdb

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
cd vikingdb

# 配置部署参数
agentkit config

# 启动云端服务
agentkit launch

# 测试部署的 Agent
agentkit invoke 'What is Python?'

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

Web 界面提供图形化对话测试环境，支持实时查看检索结果和调试信息。

#### 方式三：命令行测试

```bash
# 启动 Agent 服务
uv run agent.py
# 服务将监听 http://0.0.0.0:8000
```

**重要提示**：VikingDB 首次插入文档需要构建向量索引（约 2-5 分钟），首次运行可能报错，请等待索引构建完成后重试。

#### 方式四：部署到火山引擎 veFaaS

**安全提示**：
> 以下命令仅用于开发测试。生产环境必须启用 `VEFAAS_ENABLE_KEY_AUTH=true`（默认值）并配置 IAM 角色。

```bash
cd vikingdb

# 配置环境变量（仅测试用）
export VEFAAS_ENABLE_KEY_AUTH=false
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>

# 基础部署（快速开始）
veadk deploy --vefaas-app-name=vikingdb-agent --use-adk-web

# 生产级部署（推荐）
veadk deploy \
  --vefaas-app-name=vikingdb-agent \
  --use-adk-web \
  --veapig-instance-name=<Your veaPIG Instance> \
  --iam-role "trn:iam::<Your Account ID>:role/<Your IAM Role>"
```

## 💡 示例对话

### 技术知识查询

**基于 tech.txt 的检索回答**：
```
用户：What is Python?
Agent：Python is a programming language.

用户：What is JavaScript used for?
Agent：JavaScript is primarily used for web development.
```

### 产品价格查询

**基于 products.txt 的数据检索**：
```
用户：Which is more expensive, Laptop or Phone?
Agent：Laptop is more expensive. It costs $1200, while Phone costs $800.

用户：What's the cheapest product?
Agent：The cheapest product is Tablet at $600.
```

### 上下文关联查询

**复用前文上下文的连续问答**：
```
用户：What's the price difference with the cheapest one?
Agent：The Laptop is $600 more expensive than the cheapest product (Tablet).
```

### 复合查询

**跨文档的综合查询**：
```
用户：I want to learn Python, do you have any related products?
Agent：Based on our documents, Python is a programming language. We have a Laptop ($1200) which would be suitable for programming.
```

## 📂 目录结构

```
vikingdb/
├── agent.py           # Agent 应用入口（集成 VikingDB）
├── requirements.txt   # Python 依赖列表
├── pyproject.toml     # 项目配置（uv 依赖管理）
└── README.md          # 项目说明文档
```

## 🔍 技术要点

### VikingDB 知识库

- **存储方式**：向量数据库（`backend="viking"`）
- **文档导入**：支持直接导入多个文件
- **自动索引**：自动构建向量索引（首次需等待 2-5 分钟）
- **检索方式**：基于语义相似度的向量检索
- **适用场景**：文档知识库、专业问答、RAG 应用

### RAG 工作流程

1. **文档准备**：将文档内容写入文件
2. **向量化**：KnowledgeBase 自动将文档转换为向量
3. **存储**：向量存储在 VikingDB 中
4. **检索**：用户查询时检索相关文档片段
5. **生成**：LLM 基于检索内容生成回答

### AgentKit 集成

```python
from agentkit.apps import AgentkitAgentServerApp

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)
```

## 🎯 下一步

完成 VikingDB 示例后，可以探索更多功能：

1. **[VikingMem](../vikingmem/README.md)** - 使用 VikingDB 实现长期记忆
2. **[Episode Generation](../episode_generation/README.md)** - 生成图片和视频内容
3. **[Restaurant Ordering](../restaurant_ordering/README.md)** - 构建复杂的业务流程 Agent
4. **[Travel Concierge](../travel_concierge/README.md)** - 使用 Web 搜索工具规划旅行

## 📖 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)
- [火山方舟模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
- [VikingDB 文档](https://www.volcengine.com/docs/84313/1860732?lang=zh)
