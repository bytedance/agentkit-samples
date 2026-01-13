# Video Generation Agent - 视频故事生成器

这是一个基于火山引擎 AgentKit 的"成语绘本故事视频生成"Agent。它会根据用户输入的成语故事情节：

- 生成四张卡通风格的分镜插画
- 以相邻分镜为首尾帧生成三段过渡视频
- 通过本地 MCP 工具将三段视频顺序拼接为完整成片
- 上传成片到火山引擎 TOS，并返回可访问的签名 URL

## 概述

## 核心功能

本用例展示如何构建一个生产级视频生成系统,具备以下能力:

- 智能故事助手：基于用户提供的故事或情节，进行故事情节理解与提炼、结合背景信息检索、将故事拆分成三个场景并重写故事描述
- 分镜生成：基于故事描述，用大模型文生图能力，生成分镜图片
- 视频生成：基于分镜图片，按三个场景顺序配对，用大模型生成三段分镜视频
- 产物托管：下载分镜视频到本地，使用本地MCP工具拼接成完整故事视频，并将合并后的视频上传至 TOS对象存储，生成可访问的预览链接
- 观测能力：集成OpenTelemetry追踪和APMPlus监控

系统架构如下：

![Video Generation Agent with AgentKit Runtime](img/archtecture_video_gen.jpg)

```text
用户请求
    ↓
AgentKit 运行时
    ↓
视频故事生成器
    ├── 图像生成工具 (Visual AI)
    ├── 视频生成工具 (Visual AI)
    ├── 文件下载工具 (批量下载)
    ├── 视频拼接工具 (MCP)
    └── TOS 上传工具 (存储与分享)
```

主要特性包括：

- **智能分镜生成**：自动将叙事分解为 4 个视觉关键帧,保持风格一致性和角色连续性
- **无缝视频过渡**：使用先进的视觉 AI 模型在帧之间生成流畅的过渡视频
- **本地 MCP 工具集成**：利用模型上下文协议进行高效的本地视频处理,无需云端依赖
- **自动上传与分享**：将完成的视频上传到 TOS,并生成限时签名 URL 以安全分享
- **迭代优化**：维护对话上下文,允许用户请求对风格、节奏或内容进行调整

## Agent 能力

| 组件           | 描述                                                      |
| -------------- | --------------------------------------------------------- |
| **Agent 服务** | [`agent.py`](agent.py) - 主应用程序,包含 MCP 工具注册     |
| **Agent 配置** | [`agent.yaml`](agent.yaml) - 模型设置、系统指令和工具列表 |
| **自定义工具** | [`tool/`](tool/) - 文件下载和 TOS 上传实用工具            |
| **MCP 集成**   | `@pickstar-2002/video-clip-mcp` - 本地视频拼接服务        |
| **短期记忆**   | 会话上下文维护以保持对话连续性                            |

## 快速开始

### 前置条件

#### Node.js 环境

- 安装 Node.js 18+ 和 npm ([Node.js 安装](https://nodejs.org/zh-cn))
- 确保终端中可以使用 `npx` 命令
- MCP 视频拼接工具运行所需

#### 火山引擎访问凭证

1. 登录 [火山引擎控制台](https://console.volcengine.com)
2. 进入"访问控制" → "用户" -> 新建用户 或 搜索已有用户名 -> 点击用户名进入"用户详情" -> 进入"密钥" -> 新建密钥 或 复制已有的 AK/SK
   - 如下图所示
     ![Volcengine AK/SK Management](../img/volcengine_aksk.jpg)
3. 为用户配置 AgentKit运行所依赖服务的访问权限:
   - 在"用户详情"页面 -> 进入"权限" -> 点击"添加权限"，将以下策略授权给用户
   - `AgentKitFullAccess`（AgentKit 全量权限）
   - `APMPlusServerFullAccess`（APMPlus 全量权限）
4. 为用户获取火山方舟模型 Agent API Key
   - 搜索"火山方舟"产品，点击进入控制台
   - 进入"API Key管理" -> 创建 或 复制已有的 API Key
   - 如下图所示
     ![Ark API Key Management](../img/ark_api_key_management.jpg)
5. 开通模型预置推理接入点
   - 搜索"火山方舟"产品，点击进入控制台
   - 进入"开通管理" -> "语言模型" -> 找到相应模型 -> 点击"开通服务"
   - 开通本案例中使用到的以下模型
     - root_agent模型：`deepseek-v3-2-251201`
     - 生图模型：`doubao-seedream-4-5-251128`
     - 生视频模型：`doubao-seedance-1-0-pro-250528`
   - 如下图所示
     ![Ark Model Service Management](../img/ark_model_service_management.jpg)

### 安装依赖

\*推荐使用uv工具build项目\*\*

```bash
# install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

cd python/02-use-cases/03_video_gen

# create virtual environment
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

**注意:** MCP 视频工具 (`@pickstar-2002/video-clip-mcp`) 在智能体运行时会通过 `npx` 自动启动。无需手动安装。

### 配置环境变量

设置以下环境变量:

```bash
export VOLCENGINE_ACCESS_KEY={your_ak}
export VOLCENGINE_SECRET_KEY={your_sk}
export DATABASE_TOS_BUCKET={your_tos_bucket}
export MODEL_AGENT_API_KEY={your_model_agent_api_key}

# 可选: 指定下载目录 (默认为项目根目录)
export DOWNLOAD_DIR=/tmp
```

**环境变量说明:**

- `VOLCENGINE_ACCESS_KEY`: 火山引擎访问凭证的 Access Key
- `VOLCENGINE_SECRET_KEY`: 火山引擎访问凭证的 Secret Key
- `DATABASE_TOS_BUCKET`: 用于存放最终生成的完整视频的 TOS 存储桶名称
  - 格式: `DATABASE_TOS_BUCKET={your_tos_bucket}`
  - 示例: `DATABASE_TOS_BUCKET=agentkit-platform-12345678901234567890`
- `AGENTKIT_TOOL_ID`: 从 AgentKit 控制台获取的工具 ID
- `MODEL_AGENT_API_KEY`: 从火山方舟获取的模型 Agent API Key

> 如何创建 TOS桶 [参考](https://www.volcengine.com/docs/6349/75024?lang=zh)

## 本地运行

### 方法 1: 直接 API 调用

启动智能体服务:

```bash
uv run agent.py
# 服务默认监听 0.0.0.0:8000
```

#### 步骤 1: 获取应用名称

智能体名称与 [`agent.yaml`](agent.yaml) 中的 `name` 字段一致,即 `storybook_illustrator`。

```bash
curl --location 'http://localhost:8000/list-apps'
```

#### 步骤 2: 创建会话

```bash
curl --location --request POST 'http://localhost:8000/apps/storybook_illustrator/users/u_123/sessions/s_123' \
--header 'Content-Type: application/json' \
--data ''
```

#### 步骤 3: 发送消息

```bash
curl --location 'http://localhost:8000/run_sse' \
--header 'Content-Type: application/json' \
--data '{
    "appName": "storybook_illustrator",
    "userId": "u_123",
    "sessionId": "s_123",
    "newMessage": {
        "role": "user",
        "parts": [{
            "text": "请根据寓言《狐假虎威》生成绘本故事视频"
        }]
    },
    "streaming": true
}'
```

### 方法 2: 使用 veadk web

使用 `veadk web` 进行本地调试:

> `veadk web`是一个基于 FastAPI 的 Web 服务，用于调试 Agent 应用。运行该命令时，会启动一个web服务器，这个服务器会加载并运行您的 agentkit 智能体代码，同时提供一个聊天界面，您可以在聊天界面与智能体进行交互。在界面的侧边栏或特定面板中，您可以查看智能体运行的细节，包括思考过程（Thought Process）、工具调用（Tool calls）、模型输入/输出。

```bash
# 1. 进入上一级目录
cd 02-use-cases

# 2.启动 veadk web 界面
veadk web
```

在浏览器中访问 `http://localhost:8000`,选择 `03_video_gen` 智能体,输入提示词并点击"Send"。

### 示例提示词

- **中国成语**: "后羿射日,嫦娥奔月,吴刚伐木真人版"
- **经典故事**: "愚公移山与精卫填海绘本故事"
- **武侠小说**: "射雕英雄传的真人版视频故事"
- **玄幻小说**: "凡人修仙传韩立结婴"
- **3D 动画**: "凡人修仙传虚天殿大战,3D 动漫风格"

**预期行为:**

1. 生成 4 张插画分镜帧
2. 在连续帧之间创建 3 段过渡视频
3. 启动本地 MCP 工具拼接视频
4. 上传最终视频到 TOS
5. 返回用于观看的签名 URL

## AgentKit 部署

### 部署到火山引擎 AgentKit Runtime

步骤1: 进入项目目录

```bash
cd python/02-use-cases/03_video_gen
```

步骤2: 配置 AgentKit**

```bash
agentkit config \
--agent_name storybook_illustrator \
--entry_point 'agent.py' \
--runtime_envs DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}} \
--launch_type cloud
```

修改`agentkit.yaml`部署配置

> 目的：修改后会在镜像build阶段前置安装video-clip-mcp，以加速runtime启动

```bash
# linux os命令
sed -i 's/docker_build: {}/docker_build:\n  build_script: "scripts\/setup.sh"/' agentkit.yaml

# mac os命令
sed -i '' 's/docker_build: {}/docker_build:/' agentkit.yaml && sed -i '' '/docker_build:/a\
  build_script: "scripts\/setup.sh"' agentkit.yaml
```

步骤4: 部署到运行时

```bash
agentkit launch
```

### 测试已部署的智能体

部署成功后:

1. 访问 [火山引擎 AgentKit 控制台](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/runtime)
2. 点击 **Runtime** 查看已部署的智能体 `storybook_illustrator`
3. 获取公网访问域名 (例如: `https://xxxxx.apigateway-cn-beijing.volceapi.com`) 和 API Key

#### **基于页面chatui调试**

Agentkit的智能体列表页面提供了调试入口，点击之后即可以UI可视化的方式调试智能体功能

![img](./img/agent-test-run-01.png)

![img](./img/agent-test-run-02.png)

#### 基于命令行调试

可以直接使用agentkit invoke发起对当前智能体的调试，命令如下

```bash
agentkit invoke '{"prompt": "用国风画一个熊猫冒险的故事"}'
```

#### 基于API调试

**创建会话:**

```bash
curl --location --request POST 'https://xxxxx.apigateway-cn-beijing.volceapi.com/apps/storybook_illustrator/users/u_123/sessions/s_124' \
--header 'Content-Type: application/json' \
--header 'Authorization: <您的_api_key>' \
--data ''
```

**发送消息:**

```bash
curl --location 'https://xxxxx.apigateway-cn-beijing.volceapi.com/run_sse' \
--header 'Authorization: <您的_api_key>' \
--header 'Content-Type: application/json' \
--data '{
    "appName": "storybook_illustrator",
    "userId": "u_123",
    "sessionId": "s_124",
    "newMessage": {
        "role": "user",
        "parts": [{
            "text": "请根据寓言《狐假虎威》生成绘本故事视频"
        }]
    },
    "streaming": false
}'
```

## 目录结构说明

```bash
03_video_gen/
├── agent.py              # Agent 入口,包含 MCP 集成
├── agent.yaml            # Agent 配置 (模型、指令、工具)
├── tool/                 # 自定义工具实现
│   ├── file_download.py  # 批量文件下载工具
│   └── tos_upload.py     # TOS 上传及签名 URL 生成
├── requirements.txt      # Python 依赖
├── pyproject.toml        # 项目配置 (uv/pip 依赖与元数据)
├── __init__.py           # 包初始化文件
├── .python-version       # Python 版本声明 (开发环境)
├── README.md            # 项目文档
└── .dockerignore         # Docker 构建排除项
```

## 效果展示

视频生成效果展示。

## 常见问题

**错误: `npx` 命令未找到**

- 安装 Node.js 18+ 和 npm
- 在终端中验证 `npx --version` 可以正常运行

**TOS 上传失败：**

- 确认已设置 `VOLCENGINE_ACCESS_KEY` 和 `VOLCENGINE_SECRET_KEY`
- 验证您的账户具有 TOS 存储桶访问权限

**MCP 工具连接错误：**

- 确保默认 MCP 端口没有冲突
- 查看 Node.js 进程日志以获取详细错误信息

**使用自定义 TOS 存储桶：**

- 通过环境变量设置: `export DATABASE_TOS_BUCKET="agentkit-platform-{{account_id}}"`
- 或在 [`tool/tos_upload.py`](tool/tos_upload.py) 中修改默认值

**`uv sync` 失败：**

- 确保已安装 Python 3.12+
- 检查 `.python-version` 文件与您的 Python 安装版本是否匹配
- 尝试使用 `uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple --refresh` 重新构建依赖

## 🔗 相关资源

- [AgentKit 官方文档](https://www.volcengine.com/docs/86681/1844878?lang=zh)
- [TOS 对象存储](https://www.volcengine.com/product/TOS)
- [AgentKit 控制台](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/overview?projectName=default)
- [火山方舟控制台](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new)

## 代码许可

本工程遵循 Apache 2.0 License
