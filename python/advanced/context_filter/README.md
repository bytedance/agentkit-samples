# Context Filter Agent - 上下文过滤智能体

## 概述

本示例展示如何为 AgentKit Agent 配置**上下文过滤（Context Filter）**。在长对话场景下，随着轮次增加，历史事件会不断累积并占满上下文窗口，导致 token 成本升高甚至超出模型上限。通过 `ContextFilterPlugin`，框架会在每次调用模型前只保留最近 N 次调用的对话内容，直接丢弃更早的历史，从而以极低的开销控制上下文长度。

## 核心功能

- 使用 `ContextFilterPlugin` 开启上下文过滤
- 通过 `num_invocations_to_keep` 控制保留的最近调用轮数
- 以 App 级 `plugins` 的方式装载插件
- 结合短期记忆维护多轮对话上下文

## Agent 能力

主要使用的火山引擎产品或 Agent 组件：

- 方舟大模型：deepseek-v4-pro-260425
- 内置工具：web_search
- 短期记忆（ShortTermMemory）
- AgentKit Runtime

## 目录结构说明

```bash
context_filter/
├── README.md          # 项目说明文档
├── __init__.py
├── agent.py           # Agent 应用入口，包含上下文过滤配置
└── pyproject.toml     # Python 项目依赖配置（uv 工具）
```

## 本地运行

### 前置准备

1. Python 3.10 或更高版本
2. 开通[火山方舟模型服务](https://exp.volcengine.com/ark?mode=chat)
3. 参考[用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK

### 启动

```bash
uv sync
uv run agent.py
```

服务默认监听 `0.0.0.0:8000`。你可以进行多轮对话，当对话轮数超过 `num_invocations_to_keep` 设定的阈值后，框架会在调用模型前自动丢弃更早的历史。

## AgentKit 部署

```bash
# 生成 AgentKit 部署配置（首次执行）
agentkit config

# 部署到 AgentKit 平台
agentkit deploy
```

## 示例提示词

进行连续多轮对话即可观察过滤效果，例如：

```text
1. 我叫小明，正在计划一次为期 5 天的日本旅行。
2. 帮我推荐东京的三个必去景点。
3. 大阪有什么美食值得尝试？
4. 我预算有限，帮我规划一下每天的行程。
5. 你还记得我叫什么名字吗？
```

当保留窗口为 3 时，到第 5 轮，第 1 轮"我叫小明"的对话已被过滤出上下文，Agent 可能无法再回答姓名。这直观地体现了过滤策略"信息直接丢弃"的特性——与压缩策略保留摘要不同。

## 效果展示

多轮对话后，超出保留窗口的早期对话会在调用模型前被丢弃，上下文长度稳定在最近 N 轮，token 开销显著下降。

## 技术要点

### 上下文过滤（ContextFilterPlugin）

```python
app = App(
    name="context_filter",
    root_agent=root_agent,
    plugins=[
        ContextFilterPlugin(
            num_invocations_to_keep=3,  # 只保留最近 3 次调用的上下文
        )
    ],
)
```

- **num_invocations_to_keep**：保留的最近调用轮数。一次调用指"一条或多条连续的用户消息 + 一次模型响应"。值越小上下文越短、成本越低，但越容易丢失早期关键信息。
- 插件也支持传入 `custom_filter` 自定义过滤函数，对 `contents` 列表做更精细的裁剪。

### 与 EventsCompactionConfig 的区别

- `ContextFilterPlugin`：直接**丢弃**超出保留轮数的对话，实现最简单、几乎零额外开销，但可能丢失关键信息。
- `EventsCompactionConfig`：把旧对话**总结压缩**成摘要，信息有损但保留要点，适合需要长期记住上下文脉络的场景（参见同级 `auto_compaction` 示例）。

两者可以组合使用，兼顾成本与信息保真度。

## 常见问题

无。

## 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)

## 代码许可

本工程遵循 Apache 2.0 License
