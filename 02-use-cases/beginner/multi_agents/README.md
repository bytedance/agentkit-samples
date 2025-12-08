# Multi Agents

## 简介

使用 VeADK 构建一个由多个专业 Agent 组成的协作系统

## 项目说明

本示例演示了一个典型的多智能体协作场景：

- **层级架构**：主 Agent 负责任务分发，子 Agent 负责具体执行
- **专业分工**：每个 Agent 专注于特定领域（如存储管理、数据查询等）
- **工具集成**：集成火山引擎服务作为工具能力
- **协作流程**：Agent 之间通过消息传递和结果共享完成复杂任务

多智能体结构：
`<img src="./doc/architecture.jpeg" alt="assistant_agent" width="100%">`

## 前置依赖

1. **开通火山方舟模型服务**：前往 [Ark console](https://exp.volcengine.com/ark?mode=chat)
2. **准备 model_api_key**：在控制台获取 **API Key**。
3. **获取 AK、SK**：参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh)获取火山引擎访问密钥

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
cd multi-agents
# 这一步直接运行即可
export VEFAAS_ENABLE_KEY_AUTH=false
# 这一步需要把YOUR_AK换成自己的ak
export VOLCENGINE_ACCESS_KEY=YOUR_AK
# 这一步需要把YOUR_AK换成自己的sk
export VOLCENGINE_SECRET_KEY=YOUR_SK
# 这一步部署应用到云上
veadk deploy --vefaas-app-name=multi_agent_example --use-adk-web 
# 可以使用更多的复杂配置进行部署
veadk deploy --vefaas-app-name=multi_agent_example --use-adk-web --veapig-instance-name=<your veapig instance name> --iam-role "trn:iam::<your account id>:role/<your iam role name>"

```

### 6. 部署到AgentKit 并且使用client.py测试

```bash
cd multi-agents
# Uncomment the following line in agent.py to run the agentkit app server
# agent_server_app.run(host="0.0.0.0", port=8000)
agentkit config
agentkit launch

# 使用命令进行调试
agentkit invoke '我想买一台火山引擎虚拟机，用来做图像处理，可以帮我介绍一下哪个规格更适合我吗'
```

### 示例 Prompt

- 简单打招呼：

> 你好，你能提供什么帮助？

- 商品咨询与推荐

> 我想买一台火山引擎虚拟机，用来做图像处理，可以帮我介绍一下哪个规格更适合我吗？

- 订单查询与问题处理

> 我的订单 12345 什么时候发货？已经等了 3 天了
