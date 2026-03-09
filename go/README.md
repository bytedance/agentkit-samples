# AgentKit 代码工坊

欢迎来到 AgentKit 代码工坊（Samples）仓库！

AgentKit 是火山引擎推出的企业级 AI Agent 开发平台，为开发者提供完整的 Agent 构建、部署和运维解决方案。平台通过标准化的开发工具链和云原生基础设施，显著降低复杂智能体应用的开发部署门槛。

本代码库包含了一系列示例和教程，帮助您理解、实现和集成 AgentKit 的各项功能到您的应用中。

## ➤ 项目结构

AgentKit 代码工坊为让您快速上手 AgentKit 平台，提供了不同入门等级的示例和教程：

- **基础教程**：包含了简单的 Agent 示例，能够帮助您快速理解 AgentKit 的基本概念和使用方法
- **使用案例**：针对有一定经验的开发者，提供了较为复杂的 Agent 实现和定制化示例

## ➤ 前置准备

| **环境要求**                                                               | **说明**                                         |
|------------------------------------------------------------------------|------------------------------------------------|
| Go 1.24.4+                                                             | 确保您的开发环境中安装了 Python 3.10 或更高版本                 |
| [`veadk-go`](https://github.com/volcengine/veadk-go)                   | 您需要安装 `veadk-go` 来开发代码                         |
| [`agentkit-sdk-python`](https://pypi.org/project/agentkit-sdk-python/) | 您需要安装 `agentkit-sdk-python` 来与 AgentKit 平台进行交互 |
| Docker（可选）                                                             | 用于本地容器构建                                       |

## ➤ 样例列表

| **名称**                                                                                                                    | **难度** | **描述**                                                             |
|---------------------------------------------------------------------------------------------------------------------------| - |--------------------------------------------------------------------|
| [`llm_auditor`](https://github.com/volcengine/agentkit-samples/tree/main/go/02-use-cases/llm_auditor)               | ![label](https://img.shields.io/badge/%E5%85%A5%E9%97%A8-E6E6FA) | 入门级对话智能体，展示如何创建一个具备短期记忆能力的基础 AI Agent                              |

每个用例都包含完整的实现，并详细说明如何结合 AgentKit 组件构建应用。

## ➤ 贡献

欢迎您提交您的 Agent 到本仓库！详细的贡献指南请参考 [CONTRIBUTING.md](CONTRIBUTING.md)。

## ➤ 问题反馈

- **文档**: 查看 [AgentKit 官方文档](https://www.volcengine.com/docs/86681/1844823?lang=zh)
- **问题**: 在 GitHub Issues 中报告问题

## ➤ 相关资源

- [AgentKit 官方网站](https://www.volcengine.com/docs/86681/1844823?lang=zh)
- [AgentKit SDK/CLI文档](https://volcengine.github.io/agentkit-sdk-python/)
- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)

## ➤ 许可证

本项目采用 [Apache 2.0 许可证](LICENSE) 开源。

---

*Happy AgentKit!*
