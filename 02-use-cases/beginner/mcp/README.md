# MCP Agent Demo

## 简介

将火山 MCP Server 以工具形式集成到 Agent，实现对象存储（TOS）的管理操作

## 项目说明

本示例演示了 VeADK 与 MCP 工具的集成：

- **MCP 工具集成**：使用 `MCPToolset` 连接[火山 MCP Server](https://www.volcengine.com/mcp-marketplace) 服务
- **对象存储操作**：Agent 可以通过 MCP 协议执行 TOS 对象存储的各种管理操作
- **工具调用**：Agent 自动识别用户意图，调用相应的 MCP 工具完成任务

代码结构：

- 使用环境变量 `TOOL_TOS_URL` 配置 MCP 服务地址
- `MCPToolset` 管理与 MCP 服务的连接和工具调用
- Agent 具备专业的对象存储管理能力

## 前置依赖

1. **开通火山方舟模型服务**：前往 [Ark console](https://exp.volcengine.com/ark?mode=chat)
2. **准备 model_api_key**：在控制台获取 **API Key**
3. **获取MCP 服务 URL**：在火山 MCP Server Hub中获取 [TOS MCP](https://www.volcengine.com/mcp-marketplace/detail?name=TOS%20MCP) 服务访问端点

## 运行方法

### 1. 环境配置

若未安装 uv，请先安装（任选其一）

```
# macOS / Linux（官方安装脚本）
curl -LsSf https://astral.sh/uv/install.sh | sh
# 或使用 Homebrew（macOS）
brew install uv
```

初始化项目依赖

```
uv sync
source .venv/bin/activate
```

## 2. 环境变量配置

```
export MODEL_AGENT_NAME=doubao-seed-1-6-251015
# 这一步需要把YOUR_AK换成自己的ak
export VOLCENGINE_ACCESS_KEY=YOUR_AK
# 这一步需要把YOUR_AK换成自己的sk
export VOLCENGINE_SECRET_KEY=YOUR_SK
export TOOL_TOS_URL=https://tos.mcp.volcbiz.com/mcp?token=xxxxxx
```

### 3. 运行本地客户端

```bash
# 启动服务端
uv run agent.py

# 启动客户端进行测试
uv run client.py
```

### 4. 运行veadk web客户端并使用浏览器登录 http://127.0.0.1:8000

```bash
cd ..
veadk web

```

### 5. 部署到vefaas

> **安全提示：请勿在生产环境中禁用密钥认证。确保 `VEFAAS_ENABLE_KEY_AUTH` 保持为 `true`（或不设置，默认为开启），并正确配置访问密钥和角色。只有在本地受控环境调试时，才可临时关闭认证，并务必加以警告。**

```bash
cd mcp
# 这一步直接运行即可
export VEFAAS_ENABLE_KEY_AUTH=false
# 这一步需要把YOUR_AK换成自己的ak
export VOLCENGINE_ACCESS_KEY=YOUR_AK
# 这一步需要把YOUR_AK换成自己的sk
export VOLCENGINE_SECRET_KEY=YOUR_SK
# 这一步部署应用到云上
veadk deploy --vefaas-app-name=mcp_example --use-adk-web 
# 可以使用更多的复杂配置进行部署
veadk deploy --vefaas-app-name=mcp_example --use-adk-web --veapig-instance-name=<your veapig instance name> --iam-role "trn:iam::<your account id>:role/<your iam role name>"

```

### 6. 部署到AgentKit 并且使用client.py测试

```bash
cd mcp
# Uncomment the following line in agent.py to run the agentkit app server
# agent_server_app.run(host="0.0.0.0", port=8000)
agentkit config
agentkit launch

# 使用命令进行调试
agentkit invoke '当前账号下有哪些存储桶'
```

### 示例 Prompt

- 查询存储桶列表：

> 当前账号下有哪些存储桶

- 查询对象列表：

> bucket-prod 里面有哪些文件？

- 读取文本文件内容：

> 读取 bucket-prod 中 files 目录下 config.txt 的内容
