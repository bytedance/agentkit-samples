# AgentKit Sandbox 模式

## 概述

通过 AgentKit 的 `CreateTool` 创建工具 Sandbox 模板，使用 `CreateRuntime`
部署单实例常驻 Dispatcher。Dispatcher 消费指定 SelfHosted Environment
的工具任务，为业务 Session 创建、复用和回收工具实例。
模型执行的 RuntimeTemplate 由资源教程创建，Dispatcher 是独立的 Runtime。

## 核心功能

- 调用 AgentKit 创建工具模板与常驻 Dispatcher，等待资源 Ready。
- 使用私有状态保存资源 ID 和幂等 token，支持等待失败后的恢复。
- 将工具任务分配到独立实例，支持同一业务 Session 的实例复用。
- 默认在 Tool 和 Dispatcher Runtime 创建请求中开启 APMPlus 与日志观测开关。

## Agent 能力

模型 RuntimeTemplate 推进对话；Harness 配置模型、工具和权限。
本后端提供工具执行实例及 `/workspace` 工作目录。

## 目录结构说明

| 文件 | 用途 |
| --- | --- |
| `01_create_self_host_sandbox.py` | 创建工具模板，保存 ToolId |
| `02_create_dispatcher.py` | 复用 ToolId，创建常驻 Dispatcher |
| `_backend.py` | 共享配置映射、校验与部署恢复 |
| `test_backend.py` | 无网络的部署边界测试 |

## 本地运行

在 `08-agentkit-infra` 目录执行：

```bash
uv venv resource_to_chat_http/.venv
uv pip install --python resource_to_chat_http/.venv/bin/python \
  -r resource_to_chat_http/requirements.txt
resource_to_chat_http/.venv/bin/python resource_to_chat_http/01_create_resources.py
```

根据共享 `config.yaml.example` 填好 `config.yaml` 的账号 AK/SK 与模型 Key Name，
创建资源时选择 `n`。脚本会创建 SelfHosted Environment、Environment API Key、
Harness、模型 RuntimeTemplate 和 Session，并输出三项连接信息。

## AgentKit 部署

在同一个 `08-agentkit-infra` 目录执行下列命令。可将三项输出填入共享
`config.yaml` 的 `self_host.agentkit_sandbox` 配置，或设置环境变量：

```bash
export ANTHROPIC_BASE_URL="<输出的数据面地址>"
export ANTHROPIC_ENVIRONMENT_ID="<输出的 EnvironmentId>"
export ANTHROPIC_ENVIRONMENT_KEY="<输出的 Environment Key>"
resource_to_chat_http/.venv/bin/python \
  self_host/agentkit_sandbox_mode/01_create_self_host_sandbox.py --dry-run
resource_to_chat_http/.venv/bin/python \
  self_host/agentkit_sandbox_mode/01_create_self_host_sandbox.py
resource_to_chat_http/.venv/bin/python \
  self_host/agentkit_sandbox_mode/02_create_dispatcher.py --dry-run
resource_to_chat_http/.venv/bin/python \
  self_host/agentkit_sandbox_mode/02_create_dispatcher.py
```

三项同时留空时，脚本从共享 `config.yaml` 及资源状态中读取连接信息。
`environment.env_api_key.id` 是 API Key ID；EnvironmentId 从资源状态读取。
实际部署前，脚本验证目标为 Active SelfHosted，并通过环境 Key 查询该环境的 Session。

`01_create_self_host_sandbox.py` 创建并等待 Tool Ready，随后
`02_create_dispatcher.py` 复用同一 ToolId，创建并等待 Runtime Ready。
直接运行 `02` 时也会自动准备工具模板，因此可以一条命令完成后端部署。

为了方便观测，创建 Tool 和 Dispatcher Runtime 时默认显式设置
`ApmplusEnable: true` 和 `TlsConfiguration.EnableLog: true`，申请平台开启应用监控及
stdout/stderr 日志采集。共享配置 `self_host.agentkit_sandbox.apmplus_enable`、
`enable_log` 均默认为 `true`；可分别设置为 `false` 关闭对应功能。
创建输出与 `--dry-run` 会提示默认开启观测，资源 Ready 或复用模板时显示
查询到的实际开关状态；接口未返回的字段显示为“未返回”。

本示例仅配置 AgentKit 的观测开关，日志资源配置与实际采集由平台负责。
仅开关模式需要平台支持自动配置日志资源；
当前示例不调用 TLS API 创建、查询日志资源或读取日志。

默认镜像及配置：

| 组件 | 镜像 tag | 入口 / 端口 |
| --- | --- | --- |
| Dispatcher | `runtime-anthropic-sdk-20261103-a28aa9d7-59ee0972` | `/opt/application/dispatcher` / 8000 |
| 工具 Sandbox | `tool-1.0.0` | `/opt/gem/run.sh` / 8080 |

两者仓库均为
`enterprise-public-cn-beijing.cr.volces.com/vefaas-public/agentkit-selfhostsandbox`，
架构为 `linux/amd64`。Runtime 使用镜像默认 ENTRYPOINT。

Dispatcher 注入 `MANAGED_AGENT_API_MODE=oma`、`MANAGED_AGENT_AUTH_HEADER=x-api-key`、
`ANTHROPIC_BASE_URL`、`MA_ENVIRONMENT_ID`、`MA_API_KEY`、`SANDBOX_PROVIDER=agentkit`、
`AGENTKIT_TOOL_ID` 和 `VOLCENGINE_REGION`。Environment Key 映射到 `MA_API_KEY`。
工具模板无需配置固定 WorkId、SessionId 或 Environment Key，Dispatcher 在创建
实际工具实例时注入执行参数。

执行角色默认为 `AgentKitDefaultRuntimeAccess`；需信任 `vefaas`，并允许对应工具
Session 的创建、查询、续期、删除和调用。脚本复用已有角色，缺失时使用资源教程
的 IAM 辅助函数创建并附加系统策略。公网配置要求能访问数据面及 AgentKit API。

## 示例提示词

后端 Ready 后，在 `08-agentkit-infra` 执行：

```bash
resource_to_chat_http/.venv/bin/python resource_to_chat_http/02_invoke_session_http.py \
  --prompt "请只回复 SELFHOST TEXT OK" --expected-substring "SELFHOST TEXT OK"
resource_to_chat_http/.venv/bin/python resource_to_chat_http/02_invoke_session_http.py
```

第二条命令发送配置中的工具验证问题。设置
`session.verify_sandbox_tools: true` 和
`session.expected_substring: "TOOL USE VERIFIED 391"`，可校验六个工具
`write/edit/read/grep/glob/bash` 的真实成功结果及最终回复。
可以继续用 `--prompt` 在同一 Session 中读文件，验证续聊与实例复用。

## 效果展示

成功时输出 `Tool Ready`、`Runtime Ready`、六种成功工具结果及
`HTTP 对话校验通过`，最终回复包含 `TOOL USE VERIFIED 391`。
真实 `read/grep` 结果应包含本次文件标记，续聊读取同一文件。

通过资源 ID 检查 Dispatcher `/health`、Tool Session 状态及日志；
工具结果包含本次文件内容后才视为工具验收成功。
默认工具 TTL 为 3600 秒、Session idle 回收时间为 180 秒，可通过共享配置调整。
idle 回收后的续聊可能创建新实例，需要长期保留的文件请写入持久化存储。

## 状态与重跑

部署状态保存在本目录 `.sandbox_agentkit_backend.json`，只保存公开资源 ID、
配置摘要及创建 token，权限为 `0600`，被仓库忽略。每次创建返回 ID 后立即保存，
异步等待失败可重跑恢复，已就绪资源只查询。请求发生变化时拒绝复用旧资源。
新增观测默认值也会改变创建请求；旧状态不会自动更新已有资源，使用新状态
创建时才应用新默认值。显式复用的 Tool 保持原有观测配置，输出其实际状态。

`HARNESS_INFRA_CONFIG`、`HARNESS_INFRA_STATE` 分别指定共享配置和资源状态；
`HARNESS_INFRA_BACKEND_STATE` 指定独立后端状态。路径的父目录应预先创建。
不同账号、入口、项目或 Environment 使用独立状态文件。
`--dry-run` 不访问网络、不写文件，输出中的 Environment Key 已脱敏。

资源教程 `03_cleanup_resources.py` 只清理其管理的资源。结束使用后，先在控制台停止
本状态记录的 Dispatcher Runtime 并清理工具实例与 Tool 模板，再清理资源教程。
发生 `QuotaExceeded.Tool` 时检查账号配额，保留状态后可重试。
已有同镜像、命令、端口和项目的 Ready Private 模板时，可显式设置
`self_host.agentkit_sandbox.existing_tool_id` 复用。脚本校验模板后只创建新的
Dispatcher 与工具实例，状态标记模板 `owned: false`；清理时保留复用模板。

## 常见问题

| 现象 | 检查方法 |
| --- | --- |
| `QuotaExceeded.Tool` | 确认配额已释放，或显式配置兼容的 `existing_tool_id` |
| 对话成功，工具没有结果 | 检查 Dispatcher Ready、EnvironmentId、ToolId 及执行角色权限 |
| 数据面验证失败 | 核对三项连接信息属于同一环境；验证使用 `/v1/sessions` |
| Runtime `/health` 返回 401 | 使用 Runtime 访问 Key；本次环境的网关通过 `Authorization` 头鉴权，该 Key 与 Environment Key 不同 |
| 续聊文件消失 | idle 回收后可能创建新实例，需要持久化的数据应写入外部存储 |
| `configuration changed` | 配置改变后使用新状态，或恢复首次请求参数 |
| `InvalidParameter.TlsConfiguration` | 确认平台支持仅设置 `EnableLog` 自动准备日志资源；本示例只发送观测开关 |

## 代码许可

本工程遵循仓库的 [Apache 2.0 License](../../../../../LICENSE)。
