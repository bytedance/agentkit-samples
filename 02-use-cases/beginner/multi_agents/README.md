# Multi Agents - 多智能体协作系统

基于火山引擎 VeADK 和 AgentKit 构建的多智能体协作示例，展示如何通过层级结构和专业分工实现复杂任务的智能化处理。

## 📋 概述

本示例构建了一个智能客服系统，展示多 Agent 协作的典型场景：

- **层级架构**：主 Agent 负责任务分发，子 Agent 负责具体执行
- **三种协作模式**：顺序执行（Sequential）、并行执行（Parallel）、循环优化（Loop）
- **专业分工**：预处理、信息检索、回复优化等专项能力
- **工具集成**：Web 搜索、知识库检索等外部工具

## 🏗️ 架构

```
用户请求
    ↓
Customer Service Agent（客服主 Agent）
    ├── Pre-process Agent（预处理 Agent）
    │   └── 分析用户需求，提取关键信息
    │
    └── Sequential Service Agent（顺序服务 Agent）
        ├── Parallel Get Info Agent（并行信息获取）
        │   ├── RAG Search Agent（知识库搜索）
        │   └── Web Search Agent（网络搜索）
        │       └── web_search（搜索工具）
        │
        └── Loop Refine Response Agent（循环优化回复）
            ├── Judge Agent（评价 Agent）
            └── Refine Agent（改写 Agent）
```

### 核心组件

| 组件                   | 描述                                                                |
| ---------------------- | ------------------------------------------------------------------- |
| **主 Agent**     | [agent.py](agent.py) - 客服主 Agent，负责整体调度                      |
| **子 Agent**     | [sub_agents/](sub_agents/) - 三个专业子 Agent                          |
| **- Sequential** | [sequential_agent.py](sub_agents/sequential_agent.py) - 顺序执行工作流 |
| **- Parallel**   | [parallel_agent.py](sub_agents/parallel_agent.py) - 并行信息获取       |
| **- Loop**       | [loop_agent.py](sub_agents/loop_agent.py) - 循环优化回复质量           |
| **Prompts**      | [prompts.py](prompts.py) - 各 Agent 的系统指令                         |
| **测试客户端**   | [client.py](client.py) - SSE 流式调用客户端                            |

### 代码特点

**层级 Agent 定义**（[agent.py](agent.py:11-22)）：

```python
pre_process_agent = Agent(
    name="pre_process_agent",
    description="分析用户需求，提取关键信息",
    instruction=PRE_PROCESS_AGENT_PROMPT,
)

customer_service_agent = Agent(
    name="customer_service_agent",
    description="智能客服，根据用户需求回答问题",
    instruction=CUSTOMER_SERVICE_AGENT_PROMPT,
    sub_agents=[pre_process_agent, sequential_service_agent]
)
```

**顺序执行 Agent**（[sub_agents/sequential_agent.py](sub_agents/sequential_agent.py:10-15)）：

```python
sequential_service_agent = SequentialAgent(
    name="sequential_service_agent",
    description="根据用户需求，逐步执行工作流",
    instruction=SEQUENTIAL_SERVICE_AGENT_PROMPT,
    sub_agents=[parallel_get_info_agent, loop_refine_response_agent]
)
```

**并行执行 Agent**（[sub_agents/parallel_agent.py](sub_agents/parallel_agent.py:19-24)）：

```python
parallel_get_info_agent = ParallelAgent(
    name="parallel_get_info_agent",
    description="并行执行子任务，快速获取相关信息",
    instruction=PARALLEL_GET_INFO_AGENT_PROMPT,
    sub_agents=[rag_search_agent, web_search_agent]
)
```

**循环优化 Agent**（[sub_agents/loop_agent.py](sub_agents/loop_agent.py:24-31)）：

```python
loop_refine_response_agent = LoopAgent(
    name="loop_refine_response_agent",
    description="统筹客服回复处理，接收最终优化结果",
    instruction=LOOP_REFINE_RESPONSE_AGENT_PROMPT,
    sub_agents=[judge_agent, refine_agent],
    tools=[exit_tool],
    max_iterations=1
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
cd 02-use-cases/beginner/multi_agents

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
data: {"event":"on_agent_start","agent":"customer_service_agent"}
data: {"event":"on_agent_start","agent":"pre_process_agent"}
data: {"event":"on_agent_start","agent":"parallel_get_info_agent"}
data: {"event":"on_tool_start","tool":"web_search"}
data: {"event":"on_llm_chunk","data":{"content":"根据您的需求..."}}
```

#### 方式二：使用 VeADK Web 调试界面

```bash
# 进入上级目录
cd ..

# 启动 VeADK Web 界面
veadk web

# 在浏览器访问：http://127.0.0.1:8000
```

Web 界面可以可视化查看多 Agent 协作流程和执行轨迹。

#### 方式三：部署到火山引擎 veFaaS

**安全提示**：

> 以下命令仅用于开发测试。生产环境必须启用 `VEFAAS_ENABLE_KEY_AUTH=true`（默认值）并配置 IAM 角色。

```bash
cd multi_agents

# 配置环境变量（仅测试用）
export VEFAAS_ENABLE_KEY_AUTH=false
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>

# 基础部署（快速开始）
veadk deploy --vefaas-app-name=multi-agent-example --use-adk-web

# 生产级部署（推荐）
veadk deploy \
  --vefaas-app-name=multi-agent-example \
  --use-adk-web \
  --veapig-instance-name=<Your veaPIG Instance> \
  --iam-role "trn:iam::<Your Account ID>:role/<Your IAM Role>"
```

#### 方式四：部署到 AgentKit 平台

```bash
cd multi_agents

# 配置部署参数
agentkit config

# 启动云端服务
agentkit launch

# 测试部署的 Agent
agentkit invoke '我想买一台火山引擎虚拟机，用来做图像处理，可以帮我介绍一下哪个规格更适合我吗'

# 或使用 client.py 连接云端服务
uv run client.py
```

## 💡 示例对话

### 场景一：简单打招呼

```
用户：你好，你能提供什么帮助？
Agent：[Pre-process Agent 分析需求]
      您好！我是智能客服助手，我可以帮您：

      1. 产品咨询与推荐
      2. 订单查询与处理
      3. 技术支持与问题解答
      4. 其他售前售后服务

      请问有什么可以帮到您的吗？
```

### 场景二：产品咨询（并行搜索）

```
用户：我想买一台火山引擎虚拟机，用来做图像处理，可以帮我介绍一下哪个规格更适合我吗？

Agent 执行流程：
1. [Pre-process Agent] 提取关键信息：
   - 需求：虚拟机
   - 用途：图像处理
   - 目标：规格推荐

2. [Sequential Service Agent] 启动工作流

3. [Parallel Get Info Agent] 并行获取信息：
   ├── [RAG Search Agent] 搜索内部知识库
   │   找到：GPU 实例规格文档
   └── [Web Search Agent] 搜索互联网
       找到：图像处理性能对比

4. [Loop Refine Response Agent] 优化回复：
   ├── [Judge Agent] 评价初始回复
   │   评分：内容准确但不够友好
   └── [Refine Agent] 改写回复
       优化：增加礼貌用语和结构化

Agent：根据您的图像处理需求，我为您推荐以下规格：

      1. **GPU 通用型 - ecs.g2n.2xlarge**
         - GPU: NVIDIA V100 16GB
         - vCPU: 8核
         - 内存: 32GB
         - 适合: 深度学习图像处理
         - 价格: 约5元/小时

      2. **GPU 计算型 - ecs.gn6v.xlarge**
         - GPU: NVIDIA T4 16GB
         - vCPU: 4核
         - 内存: 16GB
         - 适合: 图像识别和渲染
         - 价格: 约3元/小时

      如需更详细的配置方案或有其他问题，欢迎随时咨询！
```

### 场景三：订单问题（完整流程）

```
用户：我的订单 12345 什么时候发货？已经等了 3 天了

Agent 执行流程：
1. [Pre-process Agent] 提取信息：
   - 订单号：12345
   - 问题：发货时间
   - 情绪：焦虑（等待 3 天）

2. [Sequential Service Agent] 启动工作流

3. [Parallel Get Info Agent] 并行查询：
   ├── [RAG Search Agent] 查询订单系统
   │   结果：订单已发货，物流单号 SF123456
   └── [Web Search Agent] 查询物流信息
       结果：快件在途中，预计明天送达

4. [Loop Refine Response Agent] 优化回复：
   ├── [Judge Agent] 评价：信息完整但缺少歉意
   └── [Refine Agent] 改写：增加道歉和安抚

Agent：非常抱歉让您久等了！

      我已为您查询到订单 12345 的最新状态：

      ✓ 订单已于昨天发货
      ✓ 物流单号：SF123456（顺丰速运）
      ✓ 当前状态：运输途中
      ✓ 预计送达：明天（12月9日）

      您可以通过顺丰官网或微信小程序跟踪物流详情。
      如有其他问题，我随时为您服务！
```

## 📂 目录结构

```
multi_agents/
├── agent.py                      # 主 Agent 应用入口
├── client.py                     # 测试客户端（SSE 流式调用）
├── prompts.py                    # 各 Agent 的系统指令
├── sub_agents/                   # 子 Agent 定义
│   ├── __init__.py
│   ├── sequential_agent.py       # 顺序执行 Agent
│   ├── parallel_agent.py         # 并行执行 Agent
│   └── loop_agent.py             # 循环优化 Agent
├── requirements.txt              # Python 依赖列表 （agentkit部署时需要指定依赖文件)
├── pyproject.toml                # 项目配置（uv 依赖管理）
├── agentkit.yaml                 # AgentKit 部署配置 （运行agentkit config之后会自动生成）
├── Dockerfile                    # Docker 镜像构建文件 （运行agentkit config之后会自动生成）
└── README.md                     # 项目说明文档
```

## 🔍 技术要点

### 三种协作模式

#### 1. Sequential Agent（顺序执行）

**特点**：

- 子 Agent 按顺序依次执行
- 后一个 Agent 可以使用前一个的结果
- 适合有依赖关系的任务链

**使用场景**：

- 信息收集 → 分析 → 回复（本示例）
- 数据获取 → 清洗 → 处理
- 规划 → 执行 → 验证

#### 2. Parallel Agent（并行执行）

**特点**：

- 子 Agent 同时执行，互不阻塞
- 提高执行效率
- 适合独立的子任务

**使用场景**：

- 同时查询多个数据源（本示例）
- 并行调用多个 API
- 多维度信息收集

#### 3. Loop Agent（循环执行）

**特点**：

- 循环执行子 Agent 直到满足条件
- 支持设置最大迭代次数
- 适合需要优化和改进的任务

**使用场景**：

- 回复质量优化（本示例）
- 代码调试和修复
- 迭代式规划

### 实现原理

**顺序执行**：

```python
from veadk.agents.sequential_agent import SequentialAgent

agent = SequentialAgent(
    sub_agents=[agent1, agent2, agent3]  # 按顺序执行
)
```

**并行执行**：

```python
from veadk.agents.parallel_agent import ParallelAgent

agent = ParallelAgent(
    sub_agents=[agent1, agent2]  # 并行执行
)
```

**循环执行**：

```python
from veadk.agents.loop_agent import LoopAgent

agent = LoopAgent(
    sub_agents=[judge_agent, refine_agent],
    max_iterations=3,  # 最多循环 3 次
    tools=[exit_tool]  # 提前退出工具
)
```

### 专业分工

| Agent                        | 职责       | 特点                       |
| ---------------------------- | ---------- | -------------------------- |
| **Customer Service**   | 总调度     | 理解用户意图，分派任务     |
| **Pre-process**        | 预处理     | 提取关键信息，标准化输入   |
| **Sequential Service** | 工作流控制 | 协调子 Agent 顺序执行      |
| **Parallel Get Info**  | 信息获取   | 并行搜索多个数据源         |
| **RAG Search**         | 知识库检索 | 查询内部文档和数据         |
| **Web Search**         | 网络搜索   | 查询互联网最新信息         |
| **Loop Refine**        | 质量控制   | 循环优化回复质量           |
| **Judge**              | 评价       | 评估回复质量，给出改进建议 |
| **Refine**             | 改写       | 根据评价优化回复内容       |

### 工具集成

**Web 搜索工具**（[sub_agents/parallel_agent.py](sub_agents/parallel_agent.py:12-17)）：

```python
from veadk.tools.builtin_tools.web_search import web_search

web_search_agent = Agent(
    name="web_search_agent",
    description="从互联网中搜索相关信息",
    instruction=WEB_SEARCH_AGENT_PROMPT,
    tools=[web_search],
)
```

**退出循环工具**（[sub_agents/loop_agent.py](sub_agents/loop_agent.py:18-23)）：

```python
def exit_tool(tool_context: ToolContext) -> str:
    tool_context.actions.end_of_agent = True
    return {}
```

## 🎯 扩展方向

### 1. 增加更多专业 Agent

- **情感分析 Agent**：识别用户情绪，调整回复风格
- **订单处理 Agent**：自动处理退换货、查询等
- **技术支持 Agent**：解答技术问题，提供解决方案

### 2. 集成更多工具

- **数据库查询**：直接查询订单、用户信息
- **邮件通知**：发送确认邮件
- **工单系统**：自动创建和更新工单

### 3. 优化协作策略

- **动态任务分配**：根据任务类型选择合适的 Agent
- **智能路由**：根据负载均衡分配任务
- **结果聚合**：智能合并多个 Agent 的结果

## 📖 相关示例

完成 Multi Agents 后，可以探索：

1. **[Hello World](../hello_world/README.md)** - 了解单 Agent 基础
2. **[MCP Simple](../mcp_simple/README.md)** - 集成远程工具服务
3. **[Travel Concierge](../travel_concierge/README.md)** - 单 Agent 多工具
4. **[Video Generator](../../video_gen/README.md)** - 复杂工具链编排

## 📖 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)
- [火山方舟模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
