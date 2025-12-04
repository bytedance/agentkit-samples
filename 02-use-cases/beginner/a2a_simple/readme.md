# A2A Simple Demo

## 简介
一个基于 VEADK 和 A2A (Agent-to-Agent) 协议的示例，展示了本地客户端与远程骰子代理的交互。

## 项目说明
本项目演示了分布式智能体系统的基础构建模块。它包含一个**本地客户端**和一个**远程代理服务**。远程代理具备“投掷骰子”和“检查质数”的工具能力。
**目的**：展示如何在火山引擎方舟（Ark）平台上实现代理间的通信、工具调用以及状态管理。

## 前置依赖
1. **开通火山方舟模型服务**：前往 [Ark console](https://exp.volcengine.com/ark?mode=chat)
2. **准备 model_api_key**：在控制台获取 **API Key**。

## 运行方法

### 1. 配置环境变量
在 `config.yaml` 中设置你的鉴权信息：
```yaml
model:
  agent:
    name: doubao-seed-1-6-251015
    api_key: XXXX
```

### 2. 启动远程代理服务
在一个终端窗口中运行服务端（监听 8001 端口）：
```bash
uvicorn remote.agent:a2a_app --host localhost --port 8001
```
*启动成功后，可访问 `http://localhost:8001/.well-known/agent-card.json` 验证服务。*

### 3. 运行本地客户端
新建一个终端窗口，运行客户端进行交互：
```bash
python local_client.py
```

## 示例 Prompt
你可以修改 `local_client.py` 中的消息内容，尝试以下指令：

1. **基础能力**：  
   > Hello, show me one number.  
   (代理将投掷一次骰子并告知结果)

2. **复合任务**：  
   > Please roll 10 times, show counts, and tell me which results are prime.  
   (代理将连续调用工具并进行统计分析)

3. **指定参数**：  
   > Roll a 12-sided die.  
   (代理将使用非默认面数进行投掷)

4. **状态记忆**：  
   > Show previous roll history.  
   (代理将读取工具上下文中的历史数据)