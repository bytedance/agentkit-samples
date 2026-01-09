# Session 1 - 带有 Sandbox 工具的智能体

## 概述

本示例演示了一个集成代码沙箱（Sandbox）执行能力的智能体。该智能体可以编写并执行 Python 代码，用于解决数学计算、模拟实验或逻辑谜题等任务。

## 核心功能

1. **Sandbox集成**：集成安全沙箱环境，支持 Python 代码的动态生成与执行。
2. **复杂计算**：利用 Python 强大的计算库解决自然语言难以处理的数学和逻辑问题。
3. **AgentKit 适配**：符合 AgentKit 标准协议，支持云端部署和流式交互。

## Agent 能力

本 Agent 具备以下基础能力：

- **代码执行**：通过 `run_code` 工具在沙箱中执行 Python 代码。
- **动态计算**：编写算法解决复杂计算问题（如蒙特卡洛模拟）。
- **结果反馈**：执行结果直接反馈给智能体，辅助生成最终答案。

## 目录结构说明

```bash
sandbox_tool_sample/
├── agent.py               # 智能体核心逻辑，集成了 run_code 工具
├── client.py              # 本地测试客户端
├── agentkit.yaml          # AgentKit 部署配置文件
├── .env                   # 环境变量配置文件
└── README.md              # 说明文档
```

## 本地运行

### 1. 前置准备

在 AgentKit 平台创建沙箱工具，获取工具 ID，步骤如下：

1. 登录 AgentKit 平台进入 Sandbox 页面

   ![toolpage](./assets/images/tool_page.png)

2. 创建沙箱工具

   ![create](./assets/images/tool_create.png)

3. 获取工具 ID

   ![get](./assets/images/tool_id.png)

环境配置：确保已安装 `uv` 并配置好环境变量。

```bash
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple
source .venv/bin/activate
cp .env.sample .env
# 编辑 .env 文件，填入必要的 AGENTKIT_TOOL_ID 环境变量

# 火山引擎访问凭证（必需）
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### 2. 启动服务与测试

首先，使用以下命令启动智能体服务（默认监听 8000 端口）：

```bash
uv run agent.py
```

在保持服务运行的同时，打开一个新的终端窗口，运行本地测试客户端：

```bash
uv run client.py
```

`client.py` 会向智能体发送请求，验证其代码生成与执行能力。

## AgentKit 部署

部署过程完全自动化，支持 `.env` 环境变量自动同步。

### 1. 初始化配置

```bash
agentkit config
```

此命令会以交互方式引导您完成配置，生成 `agentkit.yaml` 文件。

### 2. 部署上线

```bash
agentkit launch
```

`agentkit launch` 会将智能体部署到 AgentKit 平台，并自动同步本地 `.env` 中的环境变量。

### 3. 在线测试

部署完成后，您可以使用 CLI 直接调用云端智能体：

```bash
agentkit invoke '帮我通过蒙特卡洛模拟算一下圆周率 PI 的值'
```

## 示例提示词

- "帮我通过蒙特卡洛模拟算一下圆周率 PI 的值"
- "用 Python 计算第 100 个斐波那契数"
- "生成一个 10 个随机数的列表并排序"

## 效果展示

- **代码生成**：Agent 会根据问题自动生成 Python 代码。
- **执行反馈**：Sandbox 执行代码并返回 stdout/stderr，Agent 根据输出回答问题。

## 常见问题

- **Q: 为什么代码执行失败？**
  - A: 请检查 AGENTKIT_TOOL_ID 是否正确，以及网络是否通畅。
- **Q: 沙箱支持哪些库？**
  - A: 默认支持 Python 标准库。

## 代码许可

本工程遵循 Apache 2.0 License。
