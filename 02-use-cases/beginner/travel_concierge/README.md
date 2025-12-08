# 旅游行程规划 Agent

本项目是一个旅游行程规划师 Agent，可以根据用户的需求，规划出包含自然景点、人文景点和当地美食的旅游行程。

# 运行方法

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
cd travel_concierge
# 这一步直接运行即可
export VEFAAS_ENABLE_KEY_AUTH=false
# 这一步需要把YOUR_AK换成自己的ak
export VOLCENGINE_ACCESS_KEY=YOUR_AK
# 这一步需要把YOUR_AK换成自己的sk
export VOLCENGINE_SECRET_KEY=YOUR_SK
# 这一步部署应用到云上
veadk deploy --vefaas-app-name=travel_example --use-adk-web 
# 可以使用更多的复杂配置进行部署
veadk deploy --vefaas-app-name=travel_example --use-adk-web --veapig-instance-name=<your veapig instance name> --iam-role "trn:iam::<your account id>:role/<your iam role name>"

```

### 6. 部署到AgentKit 并且使用client.py测试

```bash
cd travel_concierge
# Uncomment the following line in agent.py to run the agentkit app server
# agent_server_app.run(host="0.0.0.0", port=8000)
agentkit config
agentkit launch

# 使用命令进行调试
agentkit invoke '帮我制定一个杭州三日游'
```
