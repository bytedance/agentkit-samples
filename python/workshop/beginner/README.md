# Beginner 案例集 - AgentKit 入门示例

欢迎来到 AgentKit 的 Beginner 案例集！本目录包含一系列从基础到进阶的 Agent 开发示例，帮助您快速掌握火山引擎 VeADK 和 AgentKit 平台的核心功能。

## 📚 案例概览

### 基础入门

| 案例 | 描述 | 核心能力 |
| - | - | - |
| **[Hello World](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/hello_world)** | 最简单的对话 Agent | 基础对话、短期记忆 |
| **[Callback](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/callback)** | Agent 回调与护栏演示 | 生命周期回调、内容审核、PII 过滤 |

### 工具集成

| 案例 | 描述 | 核心能力 |
| - | - | - |
| **[MCP Simple](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/mcp_simple)** | MCP 协议工具集成 | MCP 工具、对象存储管理 |
| **[Travel Concierge](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/travel_concierge)** | 旅游行程规划助手 | Web 搜索、专业指令系统 |
| **[Restaurant Ordering](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/restaurant_ordering)** | 餐厅点餐助手 | 异步工具、并行调用、上下文压缩 |

### 记忆与知识库

| 案例 | 描述 | 核心能力 |
| - | - | - |
| **[VikingDB](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/vikingdb)** | 知识库检索增强 | RAG、向量检索、文档问答 |
| **[VikingMem](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/vikingmem)** | 长短期记忆管理 | 短期记忆、长期记忆、跨会话记忆 |

### 多智能体

| 案例 | 描述 | 核心能力 |
| - | - | - |
| **[Multi Agents](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/multi_agents)** | 多智能体协作系统 | 顺序执行、并行执行、循环优化 |
| **[A2A Simple](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/a2a_simple)** | Agent-to-Agent 通信 | A2A 协议、远程 Agent 调用 |

### 内容生成

| 案例 | 描述 | 核心能力 |
| - | - | - |
| **[Episode Generation](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/episode_generation)** | 图片视频生成 | 子 Agent、图像生成、视频生成 |

## 🚀 快速开始

### 前置条件

**重要提示**：在运行任何示例之前，请先访问 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 对所有依赖服务进行授权，确保案例能够正常执行。

**1. 开通火山方舟模型服务：**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)开通模型服务

**2. 获取火山引擎访问凭证：**

- 参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK

**3. 安装必要工具：**

```bash
# 安装 uv 包管理器（推荐）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 Homebrew（macOS）
brew install uv

# 安装 VeADK Python SDK
pip install --upgrade veadk-python

# 安装 AgentKit Python SDK（用于部署到 AgentKit 平台）
pip install --upgrade agentkit-sdk-python
```

### 统一调试方式

在 beginner 目录下，您可以使用统一的方式调试大部分案例：

```bash
# 导出所有案例需要的环境变量
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
export TOOL_TOS_URL=https://tos.mcp.volcbiz.com/mcp\?token\=xxxxx  # 可选，仅 mcp_simple 需要

# 进入到beginner案例的根目录
cd 02-use-cases/beginner

# 安装所有案例的依赖（使用 uv）
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 启动 VeADK Web 调试界面
veadk web --port 8080

# 在浏览器访问：http://127.0.0.1:8080
```

通过 VeADK Web 界面，您可以：

- 选择任意案例进行交互测试
- 实时查看 Agent 执行流程
- 调试工具调用和返回结果
- 查看日志和性能指标

**注意事项**：

部分案例需要额外配置才能在 VeADK Web 中正常运行：

- **a2a_simple**：不适合在 VeADK Web 中调试,因为它需要先启动远程 Agent 服务。请参考该案例的 README 使用命令行方式运行。
- **mcp_simple**：需要先配置 `TOOL_TOS_URL` 环境变量（MCP 服务地址）。未配置时 Agent 仍可加载但工具不可用。
- **vikingmem**：需要开通 VikingDB 服务，建议先配置 `VIKINGMEM_APP_NAME` 环境变量（默认为 `vikingmem_test_app`）。
- **vikingdb**：需要开通 VikingDB 和 TOS 服务，首次运行需要等待 2-5 分钟构建向量索引。

### 单独调试与部署

进入各个案例目录，您可以：

#### 1. 本地开发调试

```bash
cd <案例目录>

# 初始化虚拟环境和安装依赖
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 激活虚拟环境
source .venv/bin/activate

# 配置环境变量
export MODEL_AGENT_NAME=doubao-seed-1-6-251015
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>

# 运行 Agent 服务
uv run agent.py
```

#### 2. 部署到 AgentKit 平台

```bash
cd <案例目录>

# 配置部署参数
agentkit config

# 启动云端服务
agentkit launch

# 测试部署的 Agent
agentkit invoke 'your test prompt'
```

## 📖 学习路径

### 路径一：基础入门（推荐新手）

1. **[Hello World](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/hello_world)** - 了解 Agent 基本结构和短期记忆
2. **[Callback](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/callback)** - 掌握回调机制和护栏功能
3. **[Travel Concierge](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/travel_concierge)** - 学习工具集成和专业指令
4. **[VikingDB](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/vikingdb)** - 实践知识库检索增强

### 路径二：工具与集成

1. **[Hello World](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/hello_world)** - 基础知识
2. **[MCP Simple](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/mcp_simple)** - MCP 协议工具集成
3. **[Restaurant Ordering](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/restaurant_ordering)** - 异步工具和并行调用
4. **[Episode Generation](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/episode_generation)** - 内容生成工具

### 路径三：多智能体系统

1. **[Hello World](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/hello_world)** - 单 Agent 基础
2. **[Multi Agents](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/multi_agents)** - 多智能体协作模式
3. **[A2A Simple](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/a2a_simple)** - Agent 间通信
4. **[VikingMem](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/vikingmem)** - 跨会话记忆管理

## 🔍 案例详解

### Hello World - 基础对话 Agent

最简单的入门示例，展示：

- 如何创建一个基础 Agent
- 如何使用短期记忆维护对话上下文
- 如何实现多轮对话

**适合人群**：所有新手

**学习时间**：15 分钟

**关键代码**：

```python
agent = Agent()
short_term_memory = ShortTermMemory(backend="local")
runner = Runner(agent=agent, short_term_memory=short_term_memory)
```

### Callback - 回调与护栏

深入了解 Agent 生命周期，展示：

- 六大回调函数的使用
- 输入输出护栏机制
- PII 信息过滤
- 参数校验和结果后处理

**适合人群**：需要实现内容审核和安全控制的开发者

**学习时间**：30 分钟

**关键能力**：before_agent_callback、after_model_callback、before_tool_callback

### MCP Simple - 工具协议集成

学习 MCP 协议，展示：

- 如何集成 MCP Server
- 通过自然语言操作对象存储
- 自动工具发现和调用

**适合人群**：需要集成外部服务的开发者

**学习时间**：30 分钟

**关键技术**：MCPToolset、StreamableHTTPConnectionParams

### Travel Concierge - 专业领域 Agent

构建专业旅游规划师，展示：

- 详细的专业指令系统
- Web 搜索工具使用
- 复杂任务的工作流程设计

**适合人群**：需要构建领域专家 Agent 的开发者

**学习时间**：45 分钟

**关键技巧**：角色定义、工作流程、约束条件、输出格式

### Restaurant Ordering - 高级工具使用

餐厅点餐助手，展示：

- 异步工具和并行调用
- 上下文管理和压缩
- 工具状态管理
- 自定义插件

**适合人群**：需要优化性能和处理长对话的开发者

**学习时间**：60 分钟

**关键技术**：EventsCompactionConfig、ContextFilterPlugin、ToolContext.state

### VikingDB - 知识库检索

RAG 实践示例，展示：

- 文档导入和向量索引
- 知识库检索
- 基于知识的问答

**适合人群**：需要构建知识库问答系统的开发者

**学习时间**：45 分钟

**关键组件**：KnowledgeBase、Viking 后端

### VikingMem - 记忆管理

记忆系统实践，展示：

- 短期记忆（单会话）
- 长期记忆（跨会话）
- 记忆持久化和检索

**适合人群**：需要实现用户个性化和历史记忆的开发者

**学习时间**：40 分钟

**关键组件**：ShortTermMemory、LongTermMemory、save_session_to_long_term_memory

### Multi Agents - 多智能体协作

多 Agent 系统，展示：

- 三种协作模式（顺序、并行、循环）
- Agent 层级架构
- 专业分工和任务分发

**适合人群**：需要构建复杂协作系统的开发者

**学习时间**：90 分钟

**关键组件**：SequentialAgent、ParallelAgent、LoopAgent

### Episode Generation - 内容生成

图片视频生成，展示：

- 子 Agent 使用
- 图像生成工具
- 视频生成工具
- 工具链编排

**适合人群**：需要实现多模态内容生成的开发者

**学习时间**：45 分钟

**关键工具**：image_generate、video_generate、web_search

### A2A Simple - Agent 间通信

Agent-to-Agent 协议，展示：

- A2A 协议实现
- 远程 Agent 调用
- Agent 卡片配置
- 分布式 Agent 系统

**适合人群**：需要构建分布式 Agent 系统的开发者

**学习时间**：60 分钟

**关键组件**：RemoteVeAgent、AgentkitA2aApp、AgentCard

## 💡 常见问题

### Q1: 如何选择第一个学习的案例？

**A**: 强烈推荐从 [Hello World](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/hello_world) 开始，它涵盖了最基础的 Agent 创建和记忆管理。完成后根据您的需求选择：

- 需要内容审核 → [Callback](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/callback)
- 需要工具集成 → [MCP Simple](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/mcp_simple) 或 [Travel Concierge](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/travel_concierge)
- 需要知识库 → [VikingDB](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/vikingdb)
- 需要多 Agent → [Multi Agents](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/multi_agents)

### Q2: 为什么我的案例无法运行？

**A**: 请检查以下几点：

1. 是否访问了 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 进行服务授权
2. 是否正确配置了环境变量（MODEL_AGENT_NAME、VOLCENGINE_ACCESS_KEY、VOLCENGINE_SECRET_KEY）
3. 是否安装了必要的依赖（veadk-python、agentkit-sdk-python）
4. 对于需要 VikingDB 的案例，是否已开通并创建了知识库

### Q3: VeADK Web 和 AgentKit 平台有什么区别？

**A**:

- **VeADK Web**: 本地调试工具，提供图形化界面快速测试 Agent，无需部署
- **AgentKit 平台**: 云端部署平台，提供生产级部署、监控、版本管理等功能

推荐流程：本地开发 → VeADK Web 调试 → AgentKit 平台部署

### Q4: 如何部署到生产环境？

**A**: 生产环境部署建议使用 AgentKit 平台：

```bash
agentkit config
agentkit launch
```

**注意**：生产环境必须启用密钥认证并配置 IAM 角色。

**注意**：生产环境必须启用密钥认证并配置 IAM 角色。

### Q5: 如何监控 Agent 的性能和日志？

**A**: 有以下查看性能和日志的方式

- **本地开发**：查看控制台输出和日志文件
- **VeADK Web**：实时查看执行流程和工具调用
- **AgentKit 平台**：提供完整的监控、日志、追踪功能
- **自定义监控**：使用 Callback 机制实现自定义指标收集

### Q6: 多个案例之间有依赖关系吗？

**A**: 案例之间相对独立，但建议按学习路径顺序学习。某些高级案例会用到基础案例的概念：

- Multi Agents 基于 Hello World 的 Agent 概念
- VikingMem 扩展了 Hello World 的记忆管理
- Restaurant Ordering 综合了多个基础概念

## 🎯 下一步

完成 Beginner 案例后，您可以：

1. **探索高级案例**：查看 `02-use-cases/` 下的其他目录
2. **阅读官方文档**：深入了解 VeADK 和 AgentKit 的高级功能
3. **构建自己的 Agent**：将学到的知识应用到实际项目中
4. **加入社区**：与其他开发者交流经验

## 📖 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)
- [火山方舟模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
- [VikingDB 文档](https://www.volcengine.com/docs/84313/1860732?lang=zh)
- [MCP 协议规范](https://modelcontextprotocol.io)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来改进这些示例！

---

**祝您学习愉快！如有任何问题，请查阅各案例的 README 或联系技术支持。**
