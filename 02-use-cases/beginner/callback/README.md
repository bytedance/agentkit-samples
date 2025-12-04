# Callback Demo

## 简介
一个展示智能体生命周期各阶段回调（callbacks）的示例。

## 项目说明
本项目演示了veadk中agent callbcak的用法. 目标是帮助你理解并实践以下回调在智能体中的角色与典型用法：
- before_agent_callback：在智能体开始运行前注入上下文、初始化变量或记录启动日志。
- before_model_callback：在模型调用前修改请求（如调整系统指令、补充元数据）或进行轻量级预处理。
- after_model_callback：在模型响应后做后处理（如格式化、重写部分内容、提取结构化信息）。
- before_tool_callback：在工具执行前检查或准备参数（如类型转换、默认值填充、轻量校验）。
- after_tool_callback：在工具执行后处理结果（如规范输出、追加辅助信息、落盘记录）。
- after_agent_callback：在智能体结束后收尾（如汇总日志、清理资源、产出最终报告）。

**目的**：通过最小可运行示例，直观展示“各类回调如何协同工作”。

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

### 2. 运行示例：
```bash
python agent.py
```

### 3. 查看日志：
- 控制台：INFO 级别
- 文件：debug_output.log（DEBUG 级别）

## 示例 Prompt（用于观察各类回调的效果）
1. 观察 before_model_callback 的请求改写
   - 请写一段关于“数据治理”的简介，突出关键要点。
2. 观察 before_tool_callback 的参数准备
   - 写一篇主题为“机器学习入门”的文章，字数 300。
3. 观察 after_model_callback 的响应后处理
   - 总结“强化学习的核心概念”，输出要点列表。
4. 观察 after_tool_callback 的结果规范化
   - 生成一段教程结构（标题、提纲、结论）。
5. 观察全生命周期日志（before/after_agent）
   - 写一篇关于“生成式 AI 安全”的简要说明。