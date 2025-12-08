# Hello World Demo

## 简介

构建一个最简单的聊天 Agent

## 项目说明

本示例演示了 VeADK 的核心功能：

- **Agent 创建**：使用简单的配置创建 AI Agent
- **短期记忆**：使用本地后端（local backend）存储对话历史，实现会话级别的上下文记忆
- **多轮对话**：通过 session_id 关联对话，Agent 能记住之前的对话内容

## 前置依赖

1. **开通火山方舟模型服务**：前往 [Ark console](https://exp.volcengine.com/ark?mode=chat)

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
cd hello_world
# 这一步直接运行即可
export VEFAAS_ENABLE_KEY_AUTH=false
# 这一步需要把YOUR_AK换成自己的ak
export VOLCENGINE_ACCESS_KEY=YOUR_AK
# 这一步需要把YOUR_AK换成自己的sk
export VOLCENGINE_SECRET_KEY=YOUR_SK
# 这一步部署应用到云上
veadk deploy --vefaas-app-name=hello-world --use-adk-web 
# 可以使用更多的复杂配置进行部署
veadk deploy --vefaas-app-name=hello-world --use-adk-web --veapig-instance-name=<your veapig instance name> --iam-role "trn:iam::<your account id>:role/<your iam role name>"

```

### 6. 部署到AgentKit 并且使用client.py测试

```bash
cd hello_world
# Uncomment the following line in agent.py to run the agentkit app server
# agent_server_app.run(host="0.0.0.0", port=8000)
agentkit config
agentkit launch

# 使用命令进行调试
agentkit invoke 'who r u'
```

## 7. 示例 Prompt

示例代码展示了一个简单的两轮对话：

**第一轮对话**：

```
输入：我叫VeADK
输出：你好VeADK！很高兴认识你。
```

**第二轮对话**（测试记忆功能）：

```
输入：你还记得我叫什么吗？
输出：当然记得，你叫VeADK。
```

你也可以尝试以下对话：

- "我今年25岁" → "我多大了？"
- "我喜欢编程" → "你知道我的爱好吗？"
- "我住在北京" → "你记得我住在哪里吗？"

这些示例展示了 Agent 如何在同一会话中保持上下文记忆。
