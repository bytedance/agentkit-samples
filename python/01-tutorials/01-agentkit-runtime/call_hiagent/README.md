# Hi Agent 与 AgentKit Runtime 双向调用

[English](README_en.md)

## 背景

本 Demo 以 Hi Agent 为例，展示 AgentKit 与外部智能体双向调用的方式，并提供配套代码。

Hi Agent 是一个私有云环境下的外部平台。对接其他混合云平台上的智能体时，也可以参考下面的接入方式。

- **AgentKit → Hi Agent（POC 1）**。AgentKit Runtime 模拟 Hi Agent 平台外的沙箱。运行在其中的调用方从 Agent Card 读取服务地址，携带 Hi Agent 的渠道 Key，通过 A2A 调用 Hi Agent 智能体并取得回复。
- **AgentKit → Hi Agent（POC 1.1）**。外部通过 HTTP 或 JSON-RPC 请求 Runtime，服务内的 A2A Client 直接调用 Hi Agent。两个入口分别是 `/HiAgent_a2a_http` 和 `/HiAgent_a2a_client`。
- **Hi Agent → AgentKit（POC 2）**。Hi Agent 的 MCP 插件连接部署在 AgentKit 上的 MCP Server。插件调用其中的工具。工具通过 A2A 访问目标智能体，再把结果返回给 Hi Agent。
- **HTTP 补充方式**。同一个目标也可以通过 Hi Agent 的 HTTP 插件调用。请求经过 HTTP 适配器，回复经适配器以 JSON 或事件流的形式返回。MCP 和 HTTP 两条路径可以分别运行。

接入其他外部平台时，AgentKit 调用方使用对方的协议和鉴权方式。反向接入更直接。AgentKit Runtime 已支持 A2A 和 HTTP。外部智能体能访问目标 Runtime 时，可以选择兼容的接口，携带凭证直接调用。

## 五个示例项目

| 项目及运行指南 | 对应实验 | 代码作用 | 源码 |
| --- | --- | --- | --- |
| [a2a_caller](a2a_caller/README.md) | POC 1 | AgentKit 上的调用方。它从 Hi Agent 导出的服务卡片（Agent Card）读取地址，通过 A2A 发送问题。 | [调用代码](a2a_caller/veadk_agent.py) · [部署入口](a2a_caller/agent_server.py) |
| [a2a_client](a2a_client/README.md) | POC 1.1 | 在 Runtime 中直接运行 A2A Client，通过 HTTP 或 JSON-RPC 接收外部请求并返回 Hi Agent 的结果。 | [服务入口](a2a_client/a2a_server.py) · [调用代码](a2a_client/a2a_tool.py) |
| [simple_agent](simple_agent/README.md) | POC 2 和 HTTP 补充实验 | 两个实验共用的目标智能体。请它自我介绍时，它会回答“我是Agentkit-01”。 | [智能体定义](simple_agent/veadk_agent.py) |
| [mcp_server](mcp_server/README.md) | POC 2 | MCP 服务端。Hi Agent 调用它提供的工具，工具再通过 A2A 调用 `simple_agent`。 | [工具实现](mcp_server/mcp_tool.py) · [服务入口](mcp_server/mcp_server.py) |
| [http_plugin](http_plugin/README.md) | HTTP 补充实验 | 接收 Hi Agent 的 HTTP 插件请求，调用 `simple_agent`。普通请求一次返回完整回答，流式请求逐段返回。 | [服务入口](http_plugin/plugin_server.py) |

## 怎么运行

- **复现 POC 1**。按 `a2a_caller` 指南准备 Hi Agent 的 Agent Card、渠道 Key 和调用方的模型配置。在该目录运行 `python veadk_agent.py`，先从本机试一次。再以 `agent_server.py` 为入口部署调用方。在 Runtime 的在线测试中请远端智能体介绍自己，查看 `remote_agent` 工具返回的回答。
- **复现 POC 1.1**。按 `a2a_client` 指南准备 Hi Agent 的 Agent Card 和渠道 Key，用 `python a2a_server.py` 启动服务。部署到 Runtime 后，设置 `BASE_URL` 和 `APIKEY`，分别用 HTTP 和 JSON-RPC 的 curl 调用，核对任务状态和远端回复。
- **复现 POC 2**。先部署 `simple_agent`，也可以复用支持 A2A 的目标 Runtime。再部署 `mcp_server`，在 Hi Agent 中同步并添加工具。调用工具后，在记录中核对目标的自我介绍。示例目标会返回“我是Agentkit-01”。
- **试用 HTTP 插件**。部署或复用 `simple_agent`，再按 `http_plugin` 指南部署适配器。在 Hi Agent 中把 HTTP 插件地址设为适配器的地址。把插件添加到智能体后，在对话中请它调用远端智能体，查看工具记录中的回复。

## 代码许可

本示例采用 [Apache 2.0 许可证](../../../../LICENSE)。
