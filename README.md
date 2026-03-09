# AgentKit 代码工坊

欢迎来到 AgentKit 代码工坊（Samples）仓库！

AgentKit 是火山引擎推出的企业级 AI Agent 开发平台，为开发者提供完整的 Agent 构建、部署和运维解决方案。平台通过标准化的开发工具链和云原生基础设施，显著降低复杂智能体应用的开发部署门槛。

本代码库包含了一系列示例和教程，帮助您理解、实现和集成 AgentKit 的各项功能到您的应用中。

## ➤ 项目结构

AgentKit 代码工坊为让您快速上手 AgentKit 平台，提供了不同入门等级的示例和教程：

- **基础教程**：包含了简单的 Agent 示例，能够帮助您快速理解 AgentKit 的基本概念和使用方法
- **使用案例**：针对有一定经验的开发者，提供了较为复杂的 Agent 实现和定制化示例

## ➤ 前置准备

| **环境要求** | **说明** |
| -------- | -------- |
| Python 3.10+ | 确保您的开发环境中安装了 Python 3.10 或更高版本 |
| [`veadk-python`](https://pypi.org/project/veadk-python/) | 您需要安装 `veadk-python` 来执行代码 |
| [`agentkit-sdk-python`](https://pypi.org/project/agentkit-sdk-python/) | 您需要安装 `agentkit-sdk-python` 来与 AgentKit 平台进行交互 |
| Docker（可选） | 用于本地容器构建 |

## ➤ 样例列表

| **名称**                                                                                                                    | **难度** | **描述**                                                             |
|---------------------------------------------------------------------------------------------------------------------------| - |--------------------------------------------------------------------|
| [`hello_world`](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/hello_world)               | ![label](https://img.shields.io/badge/%E5%85%A5%E9%97%A8-E6E6FA) | 入门级对话智能体，展示如何创建一个具备短期记忆能力的基础 AI Agent                              |
| [`multi_agents`](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/multi_agents)             |  ![label](https://img.shields.io/badge/%E5%85%A5%E9%97%A8-E6E6FA) | 多智能体协作示例，展示如何通过层级结构和专业分工实现复杂任务的智能化处理                               |
| [`episode_generation`](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/episode_generation) | ![label](https://img.shields.io/badge/%E5%85%A5%E9%97%A8-E6E6FA) | 图片与视频生成智能体，展示多种 VeADK 内置工具能力                                       |
| [`mcp_simple`](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/mcp_simple)                 | ![label](https://img.shields.io/badge/%E5%85%A5%E9%97%A8-E6E6FA) | MCP 集成示例，通过 MCP 协议实现 Agent 调用火山引擎 TOS 对象存储服务                       |
| [`vikingdb_agent`](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/vikingdb)               | ![label](https://img.shields.io/badge/%E5%85%A5%E9%97%A8-E6E6FA) | 基于火山引擎 VeADK 和 VikingDB 构建的 RAG（检索增强生成）示例，展示如何通过向量检索实现专业文档知识库的智能问答 |
| [`vikingmem_agent`](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/vikingmem)             | ![label](https://img.shields.io/badge/%E5%85%A5%E9%97%A8-E6E6FA) | 基于火山引擎 VeADK 和 VikingDB 构建的记忆管理示例，展示如何实现智能体的短期记忆和长期记忆功能            |
| [`a2a_simple`](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/a2a_simple)                 | ![label](https://img.shields.io/badge/%E5%85%A5%E9%97%A8-E6E6FA) | 分布式多 Agents 示例，展示如何实现智能体之间的通信和协作                                   |
| [`agent_callbacks`](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/callback)              | ![label](https://img.shields.io/badge/%E5%85%A5%E9%97%A8-E6E6FA) | Agent 运行时生命周期回调示例，展示 Agent 生命周期各阶段的回调函数和护栏功能                       |
| [`旅行规划助手`](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/travel_concierge)               | ![label](https://img.shields.io/badge/%E6%99%AE%E9%80%9A-008000) | 结合 Web 搜索工具和专业领域知识，自动规划完整的旅行行程                                     |
| [`餐厅智能点餐助手`](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/restaurant_ordering)          | ![label](https://img.shields.io/badge/%E6%99%AE%E9%80%9A-008000) | 通过点餐智能体，实现复杂业务流程、异步工具调用、上下文管理和自定义插件等高级特性                           |
| [`实时语音聊天助手`](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/realtime_voice)                              | ![label](https://img.shields.io/badge/%E8%BF%9B%E9%98%B6-CD853F) | 实时语音聊天助手，它包含了Python服务端和用于用户交互的Web客户端                               |
| [`AI 编程助手`](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/ai_coding)                              | ![label](https://img.shields.io/badge/%E8%BF%9B%E9%98%B6-CD853F) | AI 编程助手，帮助开发者编写和优化代码                                               |
| [`客户服务智能体`](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/customer_support)                       | ![label](https://img.shields.io/badge/%E8%BF%9B%E9%98%B6-CD853F) | 提供自动的售后咨询和售前导购                                                     |
| [`视频生成智能体`](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/video_gen)                              | ![label](https://img.shields.io/badge/%E8%BF%9B%E9%98%B6-CD853F) | 结合多种工具实现视频内容创作                                                     |
| [`门店巡检智能体`](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/inspection_assistant)              | ![label](https://img.shields.io/badge/%E8%BF%9B%E9%98%B6-CD853F) | 基于多 Agents 协作的智能门店巡检系统                                              |
| [`数据分析智能体`](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/data_analysis_with_datalake)            | ![label](https://img.shields.io/badge/%E4%B8%93%E5%AE%B6-CD5C5C) | 基于 LanceDB 构建的数据分析智能体                                              |
| [`电商营销视频生成`](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/multimedia)                            | ![label](https://img.shields.io/badge/%E4%B8%93%E5%AE%B6-CD5C5C) | 基于A2A构建的多智能体电商营销视频生成示例，展示如何利用A2A以及图片、视频生成工具进行智能视频内容创作              |
| [`运行skills的智能体`](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/agent_skills)                            | ![label](https://img.shields.io/badge/%E4%B8%93%E5%AE%B6-CD5C5C) | 基于 AgentKit & VeADK & sandbox 构建可以运行 skills 的智能体 |

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
