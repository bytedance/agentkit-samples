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
| [本地模式](local_mode/README.md) | 本机 ant Worker 及进程环境变量注入 |

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

## 环境变量

先确定变量的使用者：`runtime_template.envs` 用于模型 Runtime；Dispatcher 的
连接变量用于领取和回写 Work；业务工具需要的变量必须进入执行工具的 Worker。
给 Dispatcher 配置变量，不保证独立 Sandbox 实例能读到它。

初始化时，资源教程的 `environment.env_vars: {APP_MODE: "demo"}` 会写入
`CreateEnvironment.Config.EnvVars`。后续可通过 `UpdateEnvironment` 更新：

```json
{
  "EnvironmentId": "env_example",
  "Config": {"EnvVars": {"APP_MODE": "production"}}
}
```

如需请求幂等，由调用方为同一操作生成并复用 `ClientToken`，不要在示例中固定填写。

`EnvVars` 按整个映射替换，更新时应包含仍要保留的变量；`{}` 可清空映射。
这两种操作只保存 SelfHosted 配置，不会修改运行中的容器或进程。自研后端可读取
`GetEnvironment.Config.EnvVars`，在创建 Worker 时显式映射到进程环境；
控制面查询使用账号凭据，Environment Key 用于数据面。标准后端没有自动同步此配置。

实际注入可按部署方式选择：

- 本地进程：在启动 `ant beta:worker poll ...` 前 `export APP_MODE=demo`，或通过
  `APP_MODE=demo ant beta:worker poll ...` 启动；已运行的进程需重启后生效。
- Kubernetes：在 Worker 所在容器声明 `env` / `envFrom`，普通配置使用 ConfigMap，
  凭据使用 Secret；更新后重启 Pod。具体用法见 [Kubernetes 模式](k8s_mode/README.md#业务工具环境变量)。
- AgentKit 独立 Sandbox：通过 Tool 模板或实际 Tool Session 的原生环境变量配置注入；
  需确认 Dispatcher 创建实例时的覆盖规则。当前两段部署脚本只配置固定 Dispatcher
  连接变量，未提供业务变量自动透传。更新模板不代表已有工具实例已更新，应重建相关实例。

普通环境变量中的凭据可能出现在原生资源查询中。密钥采用部署平台的 Secret 或凭据服务，
避免填写到普通 `Config.EnvVars`、模板文件或日志。

## 代码许可

本工程遵循仓库的 [Apache 2.0 License](../../../../LICENSE)。
