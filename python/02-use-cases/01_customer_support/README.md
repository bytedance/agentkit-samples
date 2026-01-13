# Customer Support Agent - 客服智能体

这是一个基于火山引擎 AgentKit 构建“客户咨询与售后服务”智能体，支持导购咨询与售后处理两类场景。系统整合知识库与CRM工具，结合短期/长期记忆与身份校验，面向真实客服流程提供高效、准确、隐私安全的服务能力。

## 概述

本用例展示如何构建一个企业级客服支持系统,具备以下能力:

- **售后助理**：基于AgentKit的售后服务助手，可以进行售后问题回答、预约上门维修等功能
- **导购助理**：基于AgentKit构建的导购助理，可以基于客户需求和喜好给用户提供购物指引
- **企业系统集成**：支持将企业系统 通过 HTTP转MCP工具方式，快速集成到 Agent中。
- **长期记忆**：支持会话记忆和用户历史记录存储，通过 Viking 向量数据库或 Mem0 实现
- **观测能力**：集成OpenTelemetry追踪和APMPlus监控

## 核心功能

![Customer Support Agent with AgentKit Runtime](img/archtecture_customer_support.jpg)

```text
客户咨询
    ↓
AgentKit 运行时
    ↓
客服智能体 (主路由器)
    ├── 导购咨询子智能体
    │   ├── 产品知识库
    │   └── 客户信息工具
    └── 售后支持子智能体
        ├── 保修与政策知识
        ├── 故障排查指南
        └── 服务工单管理 (CRUD)
```

## Agent 能力

| 组件                 | 描述                                                                                          |
| -------------------- | --------------------------------------------------------------------------------------------- |
| **Agent 服务** | [`agent.py`](agent.py) - 主应用程序,通过 `AgentkitAgentServerApp` 实现子智能体编排           |
| **CRM 工具**   | [`tools/crm_mock.py`](tools/crm_mock.py) - 模拟 CRM API,提供客户信息、购买、保修和工单增删改查 |
| **知识库**     | [`pre_build/knowledge/`](pre_build/knowledge/) - 产品指南、政策文档和故障排查文档              |
| **短期记忆**   | 本地会话上下文,保持对话连续性                                                                 |
| **长期记忆**   | Viking 向量数据库或 Mem0,持久化用户历史记录                                                   |

## 目录结构说明

```text
01_customer_support/
├── agent.py                          # 主智能体,包含子智能体编排
├── tools/
│   └── crm_mock.py                   # 模拟 CRM 工具 (客户、购买、保修、工单)
├── pre_build/
│   └── knowledge/                    # 知识库文件
│       ├── policies.md               # 退换货与保修政策
│       ├── shopping_guide.md         # 产品咨询知识
│       ├── troubleshooting_for_phone.md   # 手机故障排查指南
│       └── troubleshooting_for_tv.md      # 电视故障排查指南
├── requirements.txt                  # Python 依赖
├── README.zh.md                     # 项目文档 (中文)
└── .dockerignore                     # Docker 构建排除项
```

## 快速开始

### 前置条件

**Python 版本：**

- 需要 Python 3.12 或更高版本

**火山引擎访问凭证：**

1. 登录 [火山引擎控制台](https://console.volcengine.com)
2. 进入"访问控制" → "用户" -> 新建用户 或 搜索已有用户名 -> 点击用户名进入"用户详情" -> 进入"密钥" -> 新建密钥 或 复制已有的 AK/SK
   - 如下图所示
     ![Volcengine AK/SK Management](../../assets/images/volcengine_aksk.jpg)
3. 为用户配置 AgentKit运行所依赖服务的访问权限:
   - 在"用户详情"页面 -> 进入"权限" -> 点击"添加权限"，将以下策略授权给用户
     - `AgentKitFullAccess`（AgentKit 全量权限）
     - `APMPlusServerFullAccess`（APMPlus 全量权限）
4. 为用户获取火山方舟模型 Agent API Key
   - 登陆[火山方舟控制台](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new)
   - 进入"API Key管理" -> 创建 或 复制已有的 API Key，后续 `MODEL_AGENT_API_KEY`环境变量需要配置为该值
   - 如下图所示
     ![Ark API Key Management](../../assets/images/ark_api_key_management.jpg)
5. 开通模型预置推理接入点
   - 登陆[火山方舟控制台](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new)
   - 进入"开通管理" -> "语言模型" -> 找到相应模型 -> 点击"开通服务"
   - 确认开通，等待服务生效（通常1-2分钟）
   - 开通本案例中使用到的以下模型（您也可以根据实际需求开通其他模型的预置推理接入点，并在 `agent.py`代码中指定使用的模型）
     - `deepseek-v3-1-terminus`
   - 如下图所示
     ![Ark Model Service Management](../../assets/images/ark_model_service_management.jpg)

**知识库(首次运行自动配置)：**:

- 如未设置 `DATABASE_VIKING_COLLECTION`,智能体将自动:
  - 上传 `pre_build/knowledge/` 中的文件到 TOS
  - 创建 Viking 集合
  - 导入知识库内容
- 生产环境建议手动创建知识库并设置集合名称

### 安装依赖

*推荐使用uv工具build项目**

```bash
# install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

cd python/02-use-cases/01_customer_support

# create virtual environment
uv venv --python 3.12

# activate virtual environment
source .venv/bin/activate

# install necessary dependencies
uv pip install -r requirements.txt
```

### 配置环境变量

设置以下环境变量:

```bash
export VOLCENGINE_ACCESS_KEY={your_ak}
export VOLCENGINE_SECRET_KEY={your_sk}
export DATABASE_TOS_BUCKET={your_tos_bucket}

# 可选: 使用已有知识库
export DATABASE_VIKING_COLLECTION=<existing_knowledge_index>

# 可选: 长期记忆 (二选一)
# 选项 1: Viking 记忆
export DATABASE_VIKINGMEM_COLLECTION=<mem_index>
export DATABASE_VIKINGMEM_MEMORY_TYPE=<memory_type>

# 选项 2: Mem0
export DATABASE_MEM0_BASE_URL=<mem0_base_url>
export DATABASE_MEM0_API_KEY=<mem0_api_key>
```

**环境变量说明:**

- `DATABASE_TOS_BUCKET`: 用于自动知识库初始化所需。若未设置 `DATABASE_VIKING_COLLECTION`，首次运行会将 `pre_build/knowledge` 自动上传至 TOS 并导入 Viking 向量库。
  - 格式: `DATABASE_TOS_BUCKET={your_tos_bucket}`
  - 示例: `DATABASE_TOS_BUCKET=agentkit-platform-12345678901234567890`
- `DATABASE_VIKING_COLLECTION`: 预创建的知识库集合名称 (生产环境推荐 在AgentKit 控制台手动创建知识库并设置集合名称)
- 模型默认为 `deepseek-v3-1-terminus` ，如需更改可在代码中调整。

> 如何创建 TOS桶 [参考](https://www.volcengine.com/docs/6349/75024?lang=zh)

## 本地运行

使用 `veadk web` 进行本地调试:

> `veadk web`是一个基于 FastAPI 的 Web 服务，用于调试 Agent 应用。运行该命令时，会启动一个web服务器，这个服务器会加载并运行您的 agentkit 智能体代码，同时提供一个聊天界面，您可以在聊天界面与智能体进行交互。在界面的侧边栏或特定面板中，您可以查看智能体运行的细节，包括思考过程（Thought Process）、工具调用（Tool calls）、模型输入/输出。

```bash
# 1. 进入上级目录
cd 02-use-cases

# 2. 启动 Web 界面
veadk web
```

服务默认运行在 8000 端口。访问 `http://127.0.0.1:8000`,选择 `01_customer_support` 智能体,在输入面板中开始测试。

### 示例提示词

**售后场景:**

- "你好,我之前买的电视坏了"
- "我的邮箱是 `zhang.ming@example.com`，电视序列号是 SN20240001"
- "我需要帮助排查电视故障 - 无法开机"

**导购咨询:**

- "我想买一款客厅用的智能电视,主要用来打游戏,预算 3000 元以内"
- "你们的智能手机保修政策是什么?"
- "能推荐一款续航好的手机吗?"

**预期行为:**

- 智能体自动识别"导购"与"售后"意图并路由到相应的子智能体
- 基于工具和知识库返回结构化响应
- 必要时引导用户进行身份验证
- 检索购买历史和保修状态
- 仅在获得用户明确同意且信息完整时创建/更新/删除服务工单

## AgentKit 部署

1. 部署到火山引擎 AgentKit Runtime:

```bash
# 1. 进入项目目录
cd python/02-use-cases/01_customer_support

# 2. 配置 agentkit
agentkit config \
--agent_name customer_support \
--entry_point 'agent.py' \
--runtime_envs DATABASE_TOS_BUCKET={your_tos_bucket} \
--launch_type cloud

# 3. 部署到运行时
agentkit launch
```

2. 调用智能体

```bash
agentkit invoke '{"prompt": "我想买一款客厅用的智能电视,主要用来打游戏,预算 3000 元以内"}'
```

## 主要特性

### 智能意图路由

自动区分导购咨询和售后支持请求,路由到配备相关工具和知识的专业子智能体。

### 知识库集成

结合结构化文档与向量搜索,为产品问题、政策查询和故障排查场景提供准确的上下文感知响应。

### CRM 工具连接

模拟 CRM 接口展示集成模式:

- 客户信息检索
- 购买历史查询
- 保修状态验证
- 服务工单 CRUD 操作

### 身份验证

在访问敏感数据或执行账户操作前,通过邮箱确认验证用户身份。

### 记忆管理

- **短期记忆**: 在会话内维护对话上下文
- **长期记忆**: 通过 Viking 或 Mem0 跨会话持久化用户偏好和历史记录

### 可扩展架构

工具和知识解耦,允许无缝替换为真实 CRM API 或添加更多业务集成。

## 效果展示

Customer Support 效果展示。

## 常见问题

**错误: `DATABASE_TOS_BUCKET not set`**

- 自动知识库初始化所需
- 设置用于上传知识文件的 TOS 存储桶名称
- 替代方案: 手动创建知识库并使用 `DATABASE_VIKING_COLLECTION`

**知识库未初始化：**

- 如果未设置 `DATABASE_VIKING_COLLECTION`,首次运行会触发自动导入
- 确保 TOS 配置正确且账户具有权限
- 在 AgentKit 控制台检查导入任务状态

**默认测试用户 `CUST001`：**

- 演示数据绑定到此客户 ID
- 生产环境部署应在请求头中传递 `user_id` 并集成真实身份系统

**将模拟 CRM 替换为真实 API：**

- 修改 [`tools/crm_mock.py`](tools/crm_mock.py) 以调用实际 CRM 端点
- 保持一致的接口语义 (查询/创建/更新/删除)
- 维护参数名称和返回值结构

**服务工单操作需要用户同意：**

- 创建/更新/删除工单需要获得用户明确批准
- 确保在操作前收集所有必需字段 (customer_id、product_sn、issue_description)

## 相关资源

- [AgentKit 官方文档](https://www.volcengine.com/docs/86681/1844878?lang=zh)
- [Viking 向量数据库](https://www.volcengine.com/docs/84313/1860732?lang=zh)
- [TOS 对象存储](https://www.volcengine.com/product/TOS)
- [Mem0 记忆管理](todo)

## 代码许可

本工程遵循 Apache 2.0 License
