# Harness Infra：从资源创建到真实对话

本案例使用纯 HTTP 完成 Harness Infra 的完整接入流程：

1. 使用账号 AK/SK 调用控制面 TOP。
2. 创建或复用 Endpoint。
3. 创建 Cloud Environment，并等待 Cloud Sandbox 就绪。
4. 创建 Harness。
5. 创建托管 `SERVERLESS_PG` SessionStore，并等待 `Ready`。
6. 创建 RuntimeTemplate，关联 SessionStore，并准备 `AgentKitDefaultRuntimeAccess` 角色。
7. 创建 Environment API Key，并将 ID 和明文写入 `config.yaml`。
8. 使用 Endpoint `BaseUrl` 和 Environment Key 创建 Session，并将其信息写入
   `config.yaml`。
9. 发送用户消息，读取真实模型回复。
10. 可重复执行对话；最后删除 Environment Key、RuntimeTemplate、SessionStore 和
    Environment，归档 Harness。

Endpoint 是账号级共享入口，清理脚本默认保留。

## 文件

| 文件 | 用途 |
| --- | --- |
| `01_create_resources.py` | 创建控制面资源、Environment API Key 和 Session |
| `02_invoke_session_http.py` | 从 YAML 读取 Session，通过 HTTP 调用 Event 数据面 |
| `02_invoke_session_ant_sdk.py` | 使用 Anthropic SDK 调用既有 Session |
| `02_invoke_session_ark_sdk.py` | 使用 Ark SDK 调用既有 Session |
| `02_invoke_session.sh` | 固定 curl 消息发送脚本，连接配置默认留空 |
| `02_sse_session.sh` | 固定 curl SSE 订阅脚本，连接配置默认留空 |
| `03_cleanup_resources.py` | 清理 Session 和控制面资源，保留 Endpoint |
| [`../config.yaml.example`](../config.yaml.example) | 两个示例共享的脱敏配置模板 |
| `../config.yaml` | 默认共享的 Environment、Harness、RuntimeTemplate 和账号配置 |
| `_clients.py` | TOP HMAC-SHA256 和数据面 REST Client |
| `_common.py` | 脱敏输出、状态文件和轮询 |
| `_workflow.py` | 确定性生命周期编排 |
| `tests/test_flow.py` | 无云资源的离线协议测试 |

## 控制面与数据面

| 分面 | 地址 | 认证 | 字段 |
| --- | --- | --- | --- |
| 控制面 | `https://open.volcengineapi.com/` | 账号 AK/SK，按目标 Service 和 Region 签名 | 固定字段 PascalCase；列表为 `Items/NextToken` |
| 数据面 | `ListEndpoints/CreateEndpoint` 返回的 `BaseUrl` | 首次 `CreateAPIKey` 返回的 Environment Key，通过 `x-api-key` 发送 | Session/Event REST 使用 snake_case |
| 模型 Key | 不由客户端传明文 | 创建 Session 时通过 `x-ark-key-name` 传方舟 API Key 的 **Name** | Runtime 按账号和 Name 查询唯一 Key |

账号 AK/SK、Environment Key 和方舟模型 Key 是三类不同凭据，不能互换。

## 前置条件

- 控制面账号已开通目标 Service。
- 账号拥有创建 Endpoint、Environment、Harness、SessionStore、RuntimeTemplate 和
  API Key 的权限，并已开通 Serverless PostgreSQL。
- 已存在一个方舟 API Key，并知道它的 **Name**。这里不是 Key 明文、SID 或内部 ID。
- 账号拥有 IAM Role 查询、创建和附加系统策略的权限。示例会复用或创建
  `AgentKitDefaultRuntimeAccess`，并在新建时附加
  `AgentKitDefaultRuntimeAccess`。
- 模型 ID 对该方舟 API Key 可用。

## 安装

使用 `uv`：

```bash
uv venv
uv pip install -r requirements.txt
source .venv/bin/activate
cp -n ../config.yaml.example ../config.yaml
```

所有脚本优先读取 `HARNESS_INFRA_CONFIG` 显式指定的文件，否则读取上一级
`08-harness-infra/config.yaml`；共享配置不存在时，兼容读取脚本目录原有的
`resource_to_chat_http/config.yaml`。默认路径按脚本位置解析，不受启动目录影响。
首次运行前请填写复制出的 `../config.yaml`；运行时字段会写回实际选中的配置文件，
不会写入模板。配置文件已被仓库忽略，不得提交或共享。

## 配置

在 `config.yaml` 中声明 Harness 的系统提示词、模型、AgentLoop、Tools、Skills、
MCP Servers，SessionStore、Environment 和 RuntimeTemplate 的资源规格，以及火山
账号 AK/SK 和 Region，以及 Session 的标题、Prompt 和回复校验规则。命令行模型参数和
`--agent-loop` 优先于 YAML。
模板中标为“必填”的字段必须由用户填写；标为“按环境确认”的字段应按目标账号和
地域调整；`environment.env_api_key` 及 `session` 下的 `id`、`name`、
`endpoint_base_url` 禁止手填，由 01 和 03 管理。
`harness.model.project_name` 保留用于方舟项目配置，默认项目通常填写 `default`。

`agent_loop` 属于 Harness。RuntimeTemplate 支持 `resources`、`image_url`、
`envs` 和 `runtime`；Environment 使用 `type: Cloud` 以及
`cpu_milli`/`memory_mb`。SessionStore 固定创建托管 `SERVERLESS_PG`；公网模式无需
额外网络参数，私网模式必须设置 `use_private_network: true`、`vpc_id` 和且仅一个
`subnet_ids`。这些层级与控制面 API 请求体一致。

真实执行前会一次性校验 AK/SK、模型 Key Name、模型 Agent Name 和 URL。缺失值、示例
占位符、含空白凭据或非法 Key Name 会在任何网络调用和状态写入前终止。

使用独立状态文件可以避免覆盖其他测试：

```bash
export HARNESS_INFRA_STATE="/tmp/harness-infra-chat-$(date +%s).json"
```

状态文件权限为 `0600`，只保存资源 ID、名称、状态和幂等 token。01 创建
Environment API Key 后，将 ID 和明文写入 `config.yaml` 的
`environment.env_api_key`，并将 Session ID、名称和数据面地址写入 `session`；
写入后配置文件权限为 `0600`。02 直接从 YAML 读取这些数据，可在同一 Session
中重复发起模型轮次，不调用控制面。03 删除 Session 和云端 Key，并清空 YAML
中的运行时字段。明文存在期间禁止提交或共享该文件。

## 1. 创建资源

```bash
python 01_create_resources.py \
  --prefix harness-chat \
  --agent-loop adk
```

脚本依次执行：

- `ListEndpoints`，账号没有 Endpoint 时调用 `CreateEndpoint`。
- `CreateEnvironment` 使用 `config.yaml` 的 Environment 规格。
- 等待 Cloud Environment 的 Sandbox 就绪。
- `CreateHarness` 使用 YAML 中的模型、AgentLoop、System、Tools、Skills 和 MCP。
- `CreateSessionStore` 创建托管 Serverless PostgreSQL，轮询 `GetSessionStore`
  直到 `Ready`。状态文件只保存其 ID 和公开元数据，不保存数据库凭据。
- 准备 RuntimeTemplate 时查询固定名称 Runtime Role，不存在时创建并附加 Runtime 系统策略。
  `CreateRuntimeTemplate` 使用 YAML 中的资源、镜像、环境变量和 Runtime 配置，
  传入 `SessionStoreId`，并等待状态从 `Building` 变为 `Ready`。AppO 在创建
  Runtime 时注入 `DATABASE_POSTGRESQL_*`，AgentLoop 据此持久化 Session。
- `CreateAPIKey` 创建绑定当前 Environment 和 Endpoint 的数据面 Key，并将 ID
  和只返回一次的明文写入 `config.yaml`。
- `POST /v1/sessions` 创建 Session，并将 ID、名称和 Endpoint `BaseUrl` 写入
  `config.yaml`。
- 回填仓库中的固定脚本 `02_invoke_session.sh` 和 `02_sse_session.sh` 顶部的
  `ENDPOINT`、`SESSION_ID`、`ENV_API_KEY`，使用实际 Endpoint、Session ID 和
  `environment.env_api_key.value`；只修改这三项，保留请求正文和其他脚本逻辑。
  仓库版本的三项配置默认留空；回填后文件权限为 `0700`，不要提交填入的凭据。

创建完成后可直接运行：

```bash
./02_invoke_session.sh
./02_sse_session.sh
```

如果资源已创建、`config.yaml` 已有 Session 和 Key，可以只回填连接配置，无需重新创建：

```bash
python -c "from _curl import configure_session_curl_scripts; configure_session_curl_scripts()"
```

发送脚本只返回消息接收确认；SSE 脚本使用 `curl -N` 输出原始事件流，默认从头回放
当前 Session 的历史事件，再继续订阅。也可执行 `./02_sse_session.sh 50`，只读取
sequence 大于 50 的事件，避免重复发送问题。Ctrl+C 会清理后台 curl 进程。
SSE 连接关闭不代表智能体完成；应查看 `session.status_idle` 的 `end_turn`，需要时
使用最后收到的 sequence 重新订阅。每次成功创建 Session 后更新脚本的连接配置，
不重新生成脚本。`--dry-run` 不修改脚本；配置未填写时脚本会在发请求前提示退出。

无论使用共享配置、旧目录配置还是 `HARNESS_INFRA_CONFIG` 自定义配置，均回填
`resource_to_chat_http` 目录中的两个固定脚本；创建步骤会打印完整路径。

账号存在多个 Endpoint 时必须显式选择：

```bash
python 01_create_resources.py --endpoint-id ep_example
```

`--dry-run` 只显示计划，不访问网络或写状态。

## 2. 发起真实对话

默认问题会要求模型依次真实调用 `write`、`edit`、`read`、`grep`、`glob` 和
`bash`，在沙箱文件中计算 `17 × 23`。脚本会按事件顺序实时输出每个工具的
成功/失败状态及结果摘要。默认不绑定固定答案或工具集合，因此可以直接修改
`session.prompt` 运行不同场景：

```bash
python 02_invoke_session_http.py
```

自定义问题和验收文本：

```bash
python 02_invoke_session_http.py \
  --prompt '只回复：HARNESS_CHAT_OK' \
  --expected-substring 'HARNESS_CHAT_OK'
```

`--expected-substring` 是可选的单次调用断言，不需要写入 YAML。若需要固定 E2E
验收，也可在本地配置中增加可选的 `expected_substring` 和
`verify_sandbox_tools`；普通教程调用无需配置这两个字段。

脚本执行：

1. 从 `config.yaml` 读取 01 创建的 Session、Endpoint `BaseUrl`、Prompt 和
   Environment API Key。
2. `POST /v1/sessions/{id}/events` 使用本次随机事件 ID 发送 `user.message`。
3. `GET /v1/sessions/{id}/events` 按 sequence 增量读取事件。
4. 将每个 `agent.tool_use` 与其 `tool_result` 按调用 ID 关联并逐步输出；步骤标题下
   优先突出展示最多 500 字符的单行工具输出，下方独立边框展示脱敏后的完整原始事件 JSON。
   `--json` 在 `raw_result` 中保留完整结果事件。
5. 收到本轮 `agent.message`，随后收到
   `session.status_idle` 且 `stop_reason.type=end_turn` 才判定成功。

任意 `idle`、HTTP 200 或 Event 发送成功都不等于模型回复完成。
只要未运行 03，可连续多次执行任一 02 脚本；每次调用复用 YAML 中的 Session，
并使用新的 Event ID。

也可以使用官方 Anthropic SDK 完成同一条 Harness 数据面链路：

```bash
python 02_invoke_session_ant_sdk.py
```

也可以使用 Ark SDK 的通用请求接口完成同一条 Harness Session/Event 数据面链路。
脚本使用 Endpoint `BaseUrl` 和 Environment API Key，不使用账号 AK/SK 直连
方舟 Responses：

```bash
python 02_invoke_session_ark_sdk.py
```

如果 01 在 `CreateAPIKey` 返回后、写入 YAML 前被强制终止，明文无法恢复。
运行 03 按状态中的 `ApiKeyId` 删除旧 Key，再开始新一轮。

## 3. 清理控制面资源

```bash
python 03_cleanup_resources.py
```

清理顺序：

1. 删除残留 Session，再删除 Environment API Key。
2. 删除 RuntimeTemplate，并等待 Get 返回 404。
3. 删除 SessionStore，并等待 Get 返回 404。
4. 在内部清理 Cloud Sandbox，再删除 Environment。
5. 归档 Harness，保留账号级 Endpoint。
6. 无论清理成功与否，退出前清空 YAML 中的 API Key 和 Session 运行时字段，以及两个 `02_*.sh` 中的 `ENDPOINT`、`SESSION_ID`、`ENV_API_KEY`；保留脚本其他内容。`--dry-run` 不修改文件。

存在残留 Session 时，脚本使用 YAML 中保存的 Key 完成删除。

## 常见停点

| 现象 | 处理 |
| --- | --- |
| `CreateEndpoint` 返回 409 | 运行 `ListEndpoints` 并复用已有 Endpoint；本案例已自动处理单 Endpoint 场景 |
| `CreateAPIKey` 报 `The number of the APIKey has exceeded the quota` | 提升 APIG 的 `api_key-per-consumer` 配额，或由资源所有者删除确认不再使用的 Key；不得删除其他环境的未知 Key |
| RuntimeTemplate 长时间 `Building` | 用状态文件中的原 ID 继续调用 `GetRuntimeTemplate`，不要换 token 重建 |
| SessionStore 长时间 `Creating` | 用状态文件中的原 ID 调用 `GetSessionStore`；确认 Serverless PG 配额、欠费状态及 VPC/子网配置 |
| `x-ark-key-name` 对应零条或多条 Ark Key | 使用当前账号、地域和项目内唯一的完整 Name，不使用明文、SID 或前缀 |
| Session 返回 `requires_action` | 当前基础案例不处理客户端工具确认；改用无工具 Harness，或实现对应确认/工具结果协议 |
| Environment 删除冲突 | 先删除 Session，并等待脚本完成 Cloud Sandbox 清理 |

## 输出与超时

- 01 创建脚本固定为 7 步：准备 Endpoint → 创建 Environment 并等待 Cloud Sandbox 就绪 → 创建 Harness → 创建 SessionStore 并等待就绪 → 创建 RuntimeTemplate（包含 IAM Role 准备）→ 创建 API Key → 创建 Session。状态文件静默初始化；最后单独汇总资源并提示调用命令，不再编号为创建步骤。`--dry-run` 使用相同顺序。
- 默认按 `1、2、3…` 编号展示创建、调用和清理步骤。每步在同一标题下列出资源的 name（有则展示）、id、核心配置/参数及状态，不再拆分“创建 / 已创建”标题；对话内容以“问 / 答”打印。汇总保留各资源的名称、ID 和状态，避免重复配置。
- 删除、复用和跳过也展示资源标识；Session 另列 title。旧状态文件优先复用已保存的名称，未记录的信息不补造。API Key 仅展示名称、ID 和绑定关系，不展示明文。`--dry-run` 只列编号计划，并说明尚未获取名称和 ID。
- 创建请求（含 Endpoint、Environment、Harness、RuntimeTemplate、API Key、Session）、模型对话和删除等待均在终端单行转圈，达到 Ready 等目标状态后打印结果并继续；重定向输出和 `--json` 模式只记录状态变化，不重复刷屏。`--json` 保留脱敏 JSON 事件，步骤编号放在 `step` 字段中。
- Cloud Sandbox 的内部资源 ID、版本和收敛代数不再打印，也不进入汇总。
- 三个 `02_` 脚本（HTTP、Anthropic SDK、Ark SDK）均在执行前展示问题，结尾用结果卡片展示 Session、本轮结束状态、成功工具、启用的校验和原始智能体回复，暂不展示本轮耗时。每个工具步骤下用“↳ 工具输出”突出显示可读摘要，再用浅色边框单独展示“原始事件 · JSON”；摘要中的换行显示为 `\n`，仅在终端宽度不足时自然折行。未启用的工具覆盖或回复文本校验会明确标注，`TOOL USE VERIFIED 391` 仍保留为智能体原始回复。
- 03 清理脚本展示 Session / API Key 检查、RuntimeTemplate 删除、Environment 删除、Harness 归档和完成汇总；不存在或已清理的资源会显示跳过，Endpoint 保留。
- `HARNESS_INFRA_HTTP_TIMEOUT_SECONDS`：控制面单请求超时，默认 60 秒。
- `HARNESS_INFRA_DATA_TIMEOUT_SECONDS`：数据面单请求超时，默认 60 秒。
- `HARNESS_INFRA_WAIT_TIMEOUT_SECONDS`：异步资源轮询超时，默认 900 秒。
- `HARNESS_INFRA_POLL_INTERVAL_SECONDS`：控制面轮询间隔，默认 5 秒。
- `HARNESS_INFRA_HTTP_RETRIES`：429/503 自动重试次数，默认 2。

自动重试复用完全相同的请求体和幂等 token。手动重试时也必须保持原 token 和参数。

输出示例（名称和 ID 为示意值）：

```text
03  创建 Harness ─────────────────────────────────────────

  Harness  ✓ 可用
  名称              harness-chat-demo-harness
  ID                agent_demo

  核心配置
  Agent Loop        adk
  模型              model-demo
  模型地址          https://ark.example.com/api/v3
  版本              1
```


## 离线测试

```bash
uv run --with-requirements requirements.txt \
  python -m unittest discover -s tests -v

uv run --with 'ruff==0.11.12' ruff check .
uv run --with 'ruff==0.11.12' ruff format --check .
```

离线测试使用本机 HTTP Server，不访问云资源，覆盖：

- TOP PascalCase 请求、签名和 `Result` 解包。
- Cloud 自动资源与 RuntimeTemplate 轮询。
- Endpoint 路径前缀、`x-api-key` 和 `x-ark-key-name`。
- Anthropic SDK 生成的真实 Session/Event 请求路径与认证头。
- `agent.message + end_turn` 完成判定。
- Session/Key 即时清理和控制面资源清理顺序。
- Environment Key 不进入 stdout、stderr 或状态文件。

## 契约依据

- Harness Infra API 使用指南：从创建资源到对话
- akx `docs/harness-infra/api/`
- akx `docs/harness-infra/control-data-plane.md`
- API Version：`2025-10-30`

文档契约、本地测试和真实发布是三个独立证据。目标入口是否发布对应 Action、默认镜像、
Runtime Role 和模型权限，必须通过实际环境验证。
