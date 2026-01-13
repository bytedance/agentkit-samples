# 股票分析智能助手 - Stock Analysis

## 概述

这是一个基于火山引擎AgentKit构建的具备股票分析功能的智能助手。

本助手仅作教程使用，输出内容不构成投资建议，请您根据应用场景合理使用或修改，必要时可以寻求专业投资顾问的指导。

## 核心功能

- 功能 1：股票数据分析
- 功能 2：股票走势预测
- 功能 3：股票投资建议

## Agent 能力

```text
用户消息
    ↓
AgentKit 运行时
    ↓
Stock Analysis Agent
    ├── 网页信息工具 (web_search)
    ├── 代码执行工具 (run_code)
```

## 目录结构说明

```bash
07_stock_analysis/
├── agent.py           # Agent
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

**3. 开通`web_search`工具权限：**

- 使用[`web_search`工具](https://www.volcengine.com/docs/85508/1650263)，需提前开通并创建联网问答Agent[相应权限](https://www.volcengine.com/docs/85508/1544858)

**4. 创建 AgentKit 工具：**

- 工具类型选择：预置工具 -> AIO Sandbox

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
cd python/02-use-cases/07_stock_analysis
```

您可以通过 `pip` 工具来安装本项目依赖：

```bash
pip install -r requirements.txt
```

或者使用 `uv` 工具来安装本项目依赖：

```bash
# 如果没有 `uv` 虚拟环境，可以使用命令先创建一个虚拟环境
uv venv --python 3.12

# 使用 `pyproject.toml` 管理依赖
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 使用 `requirements.txt` 管理依赖
uv pip install -r requirements.txt

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

export AGENTKIT_TOOL_ID=<Your Tool ID>
```

### 调试方法

#### 单线程运行：使用 VeADK Web 调试界面，调试 agent.py

```bash
# 进入 02-use-cases 目录
cd agentkit-samples/02-use-cases

# 启动 VeADK Web 界面
veadk web --port 8080

# 在浏览器访问：http://127.0.0.1:8080
```

Web 界面提供图形化对话测试环境，支持实时查看消息流和调试信息。

此外，还可以使用命令行测试，调试 agent.py。

```bash
cd python/02-use-cases/07_stock_analysis

# 启动 Agent 服务
uv run agent.py
# 服务将监听 http://0.0.0.0:8000

# 新开终端，运行测试客户端
# 需要编辑 client.py，将其中的第 14 行和第 15 行的 base_url 和 api_key 修改为 agentkit.yaml 中生成的 runtime_endpoint 和 runtime_apikey 字段
uv run client.py
```

## AgentKit 部署

### 前置准备

**重要提示**：在运行本示例之前，请先访问 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 对所有依赖服务进行授权，确保案例能够正常执行。

**1. 开通火山方舟模型服务：**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)
- 开通模型服务

**2. 获取火山引擎访问凭证：**

- 参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK

**3. 开通`web_search`工具权限：**

- 使用[`web_search`工具](https://www.volcengine.com/docs/85508/1650263)，需提前开通并创建联网问答Agent[相应权限](https://www.volcengine.com/docs/85508/1544858)

**4. 创建 AgentKit 工具：**

- 工具类型选择：预置工具 -> AIO Sandbox

**5. 设置环境变量：**

```bash
# 火山引擎访问凭证（必需）
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### AgentKit 云上部署

```bash
cd python/02-use-cases/07_stock_analysis

# 配置部署参数
# optional：如果 agentkit config 中不添加 --runtime_envs AGENTKIT_TOOL_ID={{your_tool_id}}，可以在 AgentKit 控制台 智能体运行时 中，关键组件，选择 沙箱工具，并发布
agentkit config \
--agent_name stock_analysis \
--entry_point 'agent.py' \
--runtime_envs AGENTKIT_TOOL_ID={{your_tool_id}} \
--launch_type cloud

# 启动云端服务
agentkit launch

# 测试部署的 Agent
agentkit invoke '帮我搜一下宁德时代近期的股票走势, 并给我一个简单的投资建议。'

# 或使用 client.py 连接云端服务
# 需要编辑 client.py，将其中的第 14 行和第 15 行的 base_url 和 api_key 修改为 agentkit.yaml 中生成的 runtime_endpoint 和 runtime_apikey 字段
uv run client.py
```

## 示例提示词

以下是一些常用的提示词示例：

- "帮我搜一下比亚迪近期股票数据，分析一下走势"
- "帮我搜一下宁德时代近期的股票走势, 并给我一个简单的投资建议"

## 效果展示

| 示例提示词 1 | 示例提示词 2 |
| -------- | ------- |
| 帮我搜一下比亚迪近期股票数据，分析一下走势。 | 帮我搜一下宁德时代近期的股票走势, 并给我一个简单的投资建议 |
| ![示例提示词 1 截图](assets/images/prompt1.jpeg) | ![示例提示词 2 截图](assets/images/prompt2.jpeg) |

## 常见问题

无。

## 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)
- [火山方舟模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)

## 代码许可

本工程遵循 Apache 2.0 License
