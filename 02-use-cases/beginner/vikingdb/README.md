# VeADK VikingDB Demo

## 简介
一个基于VeADK和VikingDB的RAG（检索增强生成）示例，展示文档知识库的智能问答能力。

## 项目说明
本项目演示VikingDB的核心能力：直接导入文档（无需手动切片）、自动构建向量索引、基于论文内容的专业知识问答。实现非结构化文档的检索增强生成，支持复杂文档的智能交互。  

## 前置依赖
1. **开通火山方舟模型服务**：前往 [Ark console](https://exp.volcengine.com/ark?mode=chat)
2. **准备 model_api_key**：在控制台获取 **API Key**。
3. 开通与创建AK, SK： 详情可参考文档：https://bytedance.larkoffice.com/docx/ReW7dmAQXop3K4xvrcRcmfOknEb for viking知识库
[必须] 开通viking知识库
[必须] 创建viking知识库/collection
[必须] 开通tos (viking知识库需要将本地文件上传到tos，然后上传到viking知识库，因此需要开通tos)

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

### 2. 运行
```bash
python agent.py
```
*注：VikingDB首次插入文档需构建索引（约2-5分钟），首次运行可能报错，等待后重试即可。*

## 示例Prompt
你可以修改代码中的`query`列表，尝试以下指令：

1. **技术知识查询**：  
   > What is JavaScript used for?  
   (基于tech_docs.txt的检索回答)

2. **产品价格对比**：  
   > Which is more expensive, Laptop or Phone?  
   (基于product_info.txt的多数据对比)

3. **上下文关联查询**：  
   > What's the price difference with the cheapest one?  
   (复用前文上下文的连续问答)

4. **自定义指令验证**：  
   > Explain Python in one sentence.  
   (验证Agent的简洁回答指令)