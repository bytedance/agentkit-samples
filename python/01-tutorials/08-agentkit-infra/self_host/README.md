# SelfHosted 后端接入

## 概述

先在 [resource_to_chat_http](../resource_to_chat_http/README.md) 执行
`01_create_resources.py`，选择 `n` 创建 SelfHosted Environment。
将输出的 `ANTHROPIC_BASE_URL`、`ANTHROPIC_ENVIRONMENT_ID` 和
`ANTHROPIC_ENVIRONMENT_KEY` 用于后端配置。

## 核心功能

使用 [AgentKit 沙箱模式](agentkit_sandbox_mode/README.md) 可通过 AppO
`CreateTool` 创建工具模板，通过 `CreateRuntime` 部署常驻 Dispatcher。
该模式直接复用共享配置、签名客户端及资源状态。

## Agent 能力

后端就绪后，回到 `resource_to_chat_http` 发起对话。SelfHosted Environment
登记完成后，仍需 Dispatcher 创建实际工具实例，工具调用才可执行。

## 目录结构说明

| 目录 | 用途 |
| --- | --- |
| [AgentKit](agentkit_sandbox_mode/README.md) | AppO Runtime Dispatcher 与 AgentKit 工具实例 |
| [Kubernetes](k8s_mode/README.md) | Kubernetes 内的 Dispatcher 与工具 Worker |
| [本地模式](local_mode/README.md) | 本地模式预留目录 |

## 本地运行

依赖安装、共享配置和资源创建步骤见
[资源到对话教程](../resource_to_chat_http/README.md)。

## AgentKit 部署

按顺序运行 `agentkit_sandbox_mode/01_create_self_host_sandbox.py`、
`agentkit_sandbox_mode/02_create_dispatcher.py`。先取得 ToolId，再创建 Dispatcher。

## 示例提示词

先发送“请只回复 SELFHOST TEXT OK”，再要求工具在 `/workspace` 写入并读取
随机标记。完整六工具验收命令见 [AgentKit 模式](agentkit_sandbox_mode/README.md)。

## 效果展示

对话应以 `end_turn` 结束；工具应有真实成功结果，读取内容应包含本次随机标记。

## 常见问题

工具执行需要同一环境的 Key、数据面地址及运行中的后端。
模板配额不足时可使用兼容模板，实际工具实例仍由 Dispatcher 创建。

## 代码许可

本工程遵循仓库的 [Apache 2.0 License](../../../../LICENSE)。
