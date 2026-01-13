# viking knowledge - 文档知识库智能问答

基于火山引擎 VeADK 和 VikingDB 构建的 RAG（检索增强生成）示例，展示如何通过向量检索实现专业文档知识库的智能问答。

## 概述

本示例演示如何使用 VikingDB 构建文档知识库，实现基于真实文档内容的专业问答系统。

## 核心功能

- 直接导入文档无需手动切片
- 自动构建向量索引
- 基于语义检索增强回答准确性
- 支持多文档源的复合查询

## Agent 能力

```text
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
| - | - |
| **Agent 服务** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/06-agentkit-knowledge/01_viking_knowledge/agent.py) - 主应用程序，集成 KnowledgeBase 和 VikingDB |
| **知识库** | VikingDB 向量数据库，存储文档向量索引 |
| **文档源** | tech.txt（技术文档）、products.txt（产品信息） |
| **项目配置** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/06-agentkit-knowledge/01_viking_knowledge/pyproject.toml) - 依赖管理（uv 工具） |
| **短期记忆** | 维护会话上下文 |

### 代码特点

**知识库创建**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/06-agentkit-knowledge/01_viking_knowledge/agent.py#L22-L29)）:

```python
# 准备知识源
with open("/tmp/product_info.txt", "w") as f:
    f.write("产品清单及价格：\n1. 高性能笔记本电脑 (Laptop Pro) - 价格：8999元...")
with open("/tmp/service_policy.txt", "w") as f:
    f.write("售后服务政策：\n1. 质保期：所有电子产品提供1年免费质保...")

# 创建知识库
kb = KnowledgeBase(backend="viking", app_name="test_app")
kb.add_from_files(files=["/tmp/product_info.txt", "/tmp/service_policy.txt"])
```

**Agent 配置**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/python/01-tutorials/06-agentkit-knowledge/01_viking_knowledge/agent.py#L31-L36)）：

```python
root_agent = Agent(
    name="test_agent",
    knowledgebase=kb,
    instruction="You are a helpful assistant. Be concise and friendly.",
)
```

## 目录结构说明

```text
01_viking_knowledge/
├── agent.py           # Agent 应用入口（集成 VikingDB）
├── requirements.txt   # Python 依赖列表
├── pyproject.toml     # 项目配置（uv 依赖管理）
└── README.md          # 项目说明文档
```

## 本地运行

### 前置准备

**1. 开通火山方舟模型服务：**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)
- 开通模型服务

**2. 开通 VikingDB 服务：**

- 访问 [VikingDB 控制台](https://console.volcengine.com/vikingdb/region:vikingdb+cn-beijing/home?projectName=default)
- 创建知识库/Collection

**3. 开通对象存储服务（TOS）：**

- VikingDB 需要将本地文件上传到 TOS，因此需要开通对象存储服务
- 访问 [TOS 控制台](https://console.volcengine.com/tos)

**4. 获取火山引擎访问凭证：**

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
cd python/01-tutorials/06-agentkit-knowledge/01_viking_knowledge
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
cd python/01-tutorials/06-agentkit-knowledge

# 启动 VeADK Web 界面
veadk web

# 在浏览器访问：http://127.0.0.1:8000
```

Web 界面提供图形化对话测试环境，支持实时查看检索结果和调试信息。

#### 方式二：命令行测试

```bash
# 启动 Agent 服务
uv run agent.py
# 服务将监听 http://0.0.0.0:8000
```

**重要提示**：VikingDB 首次插入文档需要构建向量索引（约 2-5 分钟），首次运行可能报错，请等待索引构建完成后重试。

## AgentKit 部署

### 前置准备

**重要提示**：在运行本示例之前，请先访问 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 对所有依赖服务进行授权，确保案例能够正常执行。

**1. 开通火山方舟模型服务：**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)
- 开通模型服务

**2. 开通 VikingDB 服务：**

- 访问 [VikingDB 控制台](https://console.volcengine.com/vikingdb/region:vikingdb+cn-beijing/home?projectName=default)
- 创建知识库/Collection

**3. 开通对象存储服务（TOS）：**

- VikingDB 需要将本地文件上传到 TOS，因此需要开通对象存储服务
- 访问 [TOS 控制台](https://console.volcengine.com/tos)

**4. 获取火山引擎访问凭证：**

- 参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK

### AgentKit 云上部署

```bash
# 进入到项目目录
cd python/01-tutorials/06-agentkit-knowledge/01_viking_knowledge

# 配置部署参数,DATABASE_TOS_BUCKET环境变量需要传入到Agent中，用来上传本地文件到TOS，进而将文件从TOS导入到知识库中
agentkit config \
--agent_name vikingdb_agent \
--entry_point 'agent.py' \
--runtime_envs DATABASE_TOS_BUCKET=agentkit-platform-2107625663 \
--runtime_envs DATABASE_VIKING_COLLECTION=agentkit_knowledge_app \
--launch_type cloud

# 启动云端服务
agentkit launch

# 测试部署的 Agent
agentkit invoke '高性能笔记本电脑PRO的价钱是多少'

# 或使用 client.py 连接云端服务
# 需要编辑 client.py，将其中的第 14 行和第 15 行的 base_url 和 api_key 修改为 agentkit.yaml 中生成的 runtime_endpoint 和 runtime_apikey 字段
# 按需修改 client.py，第 56 行，请求的内容
uv run client.py
```

## 示例提示词

### 产品信息查询

**基于 product_info.txt 的检索回答**：

```text
用户：高性能笔记本Pro的价钱是多少？
Agent：根据产品清单，高性能笔记本电脑 (Laptop Pro) 的价格是 8999 元。

用户：这里最便宜的产品是什么？
Agent：最便宜的产品是平板电脑 (Tablet Air)，价格为 2999 元。
```

### 售后服务查询

**基于 service_policy.txt 的数据检索**：

```text
用户：你们的退换货政策是怎样的？
Agent：根据售后服务政策，购买后 7 天内支持无理由退货，15 天内如有质量问题可以换货。

用户：笔记本电脑保修多久？
Agent：所有电子产品均提供 1 年免费质保。
```

### 上下文关联查询

**复用前文上下文的连续问答：**

```text
用户：那 SmartPhone X 呢？
Agent：SmartPhone X 的价格是 4999 元。
```

### 复合查询

**跨文档的综合查询：**

```text
用户：我想买一台用来办公和娱乐的设备，有什么推荐并告诉我售后保障？
Agent：推荐您使用平板电脑 (Tablet Air)，它轻薄便携，适合办公娱乐，价格为 2999 元。售后方面，我们提供 1 年免费质保，且支持 7 天无理由退货。
```

## 效果展示

## 技术要点

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

## 常见问题

无。

## 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)
- [火山方舟模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
- [VikingDB 文档](https://www.volcengine.com/docs/84313/1860732?lang=zh)

## 代码许可

本工程遵循 Apache 2.0 License
