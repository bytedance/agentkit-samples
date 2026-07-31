# Reflect & Retry Agent - 工具失败自愈智能体

## 概述

本示例展示如何为 AgentKit Agent 配置**工具失败自愈（Reflect and Retry）**。在真实场景中，工具调用可能因网络抖动、限流、上游服务瞬时不可用等原因偶发失败。通过 `ReflectAndRetryToolPlugin`，框架会拦截工具异常，把结构化的错误信息与反思引导反馈给模型，让模型自动纠正并重新发起调用，最多重试 `max_retries` 次，从而在无需人工介入的情况下从瞬时故障中恢复。

## 核心功能

- 使用 `ReflectAndRetryToolPlugin` 开启工具失败自愈
- 通过 `max_retries` 控制同一工具的最大连续重试次数
- 以 App 级 `plugins` 的方式装载插件
- 内置一个"前两次失败、第三次成功"的示例工具，直观演示重试生效

## Agent 能力

主要使用的火山引擎产品或 Agent 组件：

- 方舟大模型：deepseek-v4-pro-260425
- 自定义工具：flaky_weather（模拟瞬时故障）
- 短期记忆（ShortTermMemory）
- AgentKit Runtime

## 目录结构说明

```bash
reflect_retry/
├── README.md          # 项目说明文档
├── __init__.py
├── agent.py           # Agent 应用入口，包含失败重试配置与示例工具
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

服务默认监听 `0.0.0.0:8000`。你可以询问某个城市的天气，示例工具 `flaky_weather` 前两次会抛错，插件会引导模型反思并重试，第三次成功返回结果。

## AgentKit 部署

```bash
# 生成 AgentKit 部署配置（首次执行）
agentkit config

# 部署到 AgentKit 平台
agentkit deploy
```

## 示例提示词

```text
帮我查一下北京现在的天气。
```

Agent 会调用 `flaky_weather("Beijing")`。前两次调用抛出"上游服务暂时不可用"的错误，插件把错误反馈给模型，模型据此重试，第三次成功拿到天气并回答用户。整个过程无需人工干预。

## 效果展示

工具偶发失败时，Agent 不会直接把错误抛给用户，而是根据插件提供的反思引导自动重试，最终返回正确结果。在服务日志中可以看到工具被多次调用、失败计数递增，直至成功后计数重置。

## 技术要点

### 工具失败自愈（ReflectAndRetryToolPlugin）

```python
app = App(
    name="reflect_retry",
    root_agent=root_agent,
    plugins=[
        ReflectAndRetryToolPlugin(
            max_retries=3,  # 同一工具连续失败超过 3 次才最终放弃
        )
    ],
)
```

- **max_retries**：同一工具在给定作用域内允许的最大连续失败次数。达到上限后，默认抛出最终异常（可通过 `throw_exception_if_retry_exceeded=False` 改为返回引导信息）。
- **tracking_scope**：失败计数的生命周期，默认 `TrackingScope.INVOCATION`（按单次调用跟踪），也可设为 `TrackingScope.GLOBAL` 跨轮次、跨用户全局跟踪。
- 失败计数按工具粒度统计：某工具一次成功即重置其计数，不影响其他工具。
- 对于"不抛异常但返回体里含错误"的工具，可继承插件并重写 `extract_error_from_result` 来识别错误。

### 与普通重试的区别

- 普通的代码级重试只是重复相同调用，无法纠正错误的参数或用法。
- `ReflectAndRetryToolPlugin` 会把结构化错误反馈给模型，让模型**反思并调整**后再重试，适合需要模型根据错误信息自我纠正的场景（如参数错误、格式问题、瞬时故障）。

## 常见问题

无。

## 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)

## 代码许可

本工程遵循 Apache 2.0 License
