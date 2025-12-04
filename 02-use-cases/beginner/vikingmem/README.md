# VeADK长短期记忆&VikingMem Demo

## 简介
一个基于VeADK实现的智能体记忆功能示例，展示短期记忆（同会话）与长期记忆（跨会话）的使用方法。

## 项目说明
本项目演示VeADK的两种记忆机制：短期记忆仅在同一会话ID下有效，长期记忆（基于VikingDB）可跨会话持久化存储。通过简单交互对比两种记忆的差异。

## 前置依赖
1. **开通火山方舟模型服务**：前往 [Ark console](https://exp.volcengine.com/ark?mode=chat) 获取`model_api_key`
2. **VikingDB资源**：前往[viking记忆库](https://console.volcengine.com/vikingdb/region:vikingdb+cn-beijing/home?projectName=default)开通

## 运行方法

### 1. 配置环境变量
在`config.yaml`中设置鉴权信息：
```yaml
model:
  agent:
    provider: openai
    name: doubao-seed-1-6-251015
    api_key: YOUR_ARK_API_KEY

volcengine:
  access_key: xxx
  secret_key: xxx
```

### 2. 运行项目
```bash
python agent.py
```

## 示例Prompt
你可以修改代码中的`messages`参数，尝试以下指令：

1. **存入记忆**：  
   > My habby is 0xabcd  
   (将信息存入短期记忆)

2. **同会话查询**：  
   > What is my habby?  
   (短期记忆生效，可正确回答)

3. **新会话查询**：  
   > What is my habby?  
   (无短期记忆，回答失败)

4. **长期记忆查询**：  
   > What is my habby?  
   (长期记忆生效，跨会话正确回答)