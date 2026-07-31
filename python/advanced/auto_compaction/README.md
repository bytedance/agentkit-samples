# Auto Compaction Agent - 自动上下文压缩智能体

## 概述

本示例展示如何为 AgentKit Agent 配置**自动上下文压缩（Events Compaction）**。在长对话场景下，随着轮次增加，历史事件会不断累积并占满上下文窗口，导致 token 成本升高甚至超出模型上限。通过 `EventsCompactionConfig`，框架会周期性地把较早的对话事件自动总结压缩为摘要，从而在保留关键信息的同时显著降低上下文长度。

## 核心功能

- 使用 `EventsCompactionConfig` 开启自动上下文压缩
- 通过 `compaction_interval` 控制压缩触发频率
- 通过 `overlap_size` 保留窗口重叠，避免信息断层
- 结合短期记忆维护多轮对话上下文

## Agent 能力

主要使用的火山引擎产品或 Agent 组件：

- 方舟大模型：deepseek-v4-pro-260425
- 内置工具：web_search
- 短期记忆（ShortTermMemory）
- AgentKit Runtime

## 目录结构说明

```bash
auto_compaction/
├── README.md          # 项目说明文档
├── __init__.py
├── agent.py           # Agent 应用入口，包含自动压缩配置
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

服务默认监听 `0.0.0.0:8000`。你可以进行多轮对话，当对话轮数超过 `compaction_interval` 设定的阈值后，框架会自动触发历史事件压缩。

## AgentKit 部署

```bash
# 生成 AgentKit 部署配置（首次执行）
agentkit config

# 部署到 AgentKit 平台
agentkit deploy
```

## 示例提示词

进行连续多轮对话即可触发压缩，例如：

```text
1. 我叫小明，正在计划一次为期 5 天的日本旅行。
2. 帮我推荐东京的三个必去景点。
3. 大阪有什么美食值得尝试？
4. 我预算有限，帮我规划一下每天的行程。
5. 你还记得我叫什么名字、要去哪个国家旅行吗？
```

在第 5 轮时，早期对话已被压缩为摘要，但 Agent 仍能正确回答姓名与目的地，说明关键信息被保留。

## 效果展示

多轮对话后，早期的原始事件被替换为一条压缩摘要事件，上下文长度显著下降，而 Agent 依然能记住关键信息。

## 技术要点

### 事件压缩（EventsCompactionConfig）

```python
app = App(
    name="auto_compaction",
    root_agent=root_agent,
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=3,  # 每 3 次调用触发一次压缩
        overlap_size=1,         # 压缩时保留上一个窗口的最后 1 次调用
    ),
)
```

- **compaction_interval**：每新增多少次调用触发一次压缩。值越小压缩越频繁、上下文越短，但摘要开销更高。
- **overlap_size**：压缩窗口之间的重叠调用数，用于保证跨窗口的上下文连续性，避免"断片"。

### 与 ContextFilterPlugin 的区别

- `EventsCompactionConfig`：把旧对话**总结压缩**成摘要，信息有损但保留要点，适合需要长期记住上下文脉络的场景。
- `ContextFilterPlugin`：直接**丢弃**超出保留轮数的对话，实现更简单但可能丢关键信息。

两者可以组合使用，兼顾成本与信息保真度。

## 常见问题

无。

## 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)

## 代码许可

本工程遵循 Apache 2.0 License
