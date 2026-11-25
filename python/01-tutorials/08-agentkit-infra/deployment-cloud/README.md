# Deployment Cloud 模式

本案例按资源依赖顺序演示创建 Cloud Deployment、触发运行、读取 Session、验证真实工具
调用、在同一 Session 中继续对话，以及清理资源。当前目录可单独复制运行，不依赖其他项目代码。

```text
Endpoint（路由与逻辑 Session 清理入口）
Cloud Environment → Sandbox ToolId
SessionStore + 已授权的执行角色 → Runtime
Environment + Runtime → Harness
Harness 的固定版本 + 初始消息 + 模型 Key 名称 → Deployment
RunDeployment / 定时调度 → Run + Session → 读取结果 / 同一 Session 继续对话
```

## 1. 安装依赖

需要 Python 3.12+、uv，以及具备资源创建、读取和清理权限的账号 AK/SK。

```bash
cd python/01-tutorials/08-agentkit-infra/deployment-cloud
cp config.yaml.example config.yaml
chmod 600 config.yaml
uv sync --index-url https://mirrors.aliyun.com/pypi/simple
source .venv/bin/activate
```

后续命令中的 `python` 均指这个虚拟环境的解释器。每次新开终端都需要重新激活；
也可将 `python run.py ...` 替换为 `uv run --no-sync python run.py ...`。

## 2. 填写必填配置

**执行创建命令前，必须提供账号 AK/SK；创建 Runtime、Harness、Deployment 前，还必须
提供真实的方舟模型 Key 名称。新建 Runtime 所用执行角色必须提前存在且具备相应权限。**

账号凭据可通过环境变量提供：

```bash
export VOLCENGINE_ACCESS_KEY=
export VOLCENGINE_SECRET_KEY=
```

在等号后分别填写账号 AK 和 SK。

也可以填写 `config.yaml` 中的 `control.access_key` 和 `control.secret_key`。
环境变量优先；同一凭据无需在两处重复填写。

### 必填与条件必填

| 配置 | 必填条件 | 如何填写 |
|---|---|---|
| `control.access_key` / `secret_key` | **所有操作必填**，也可由上述环境变量提供 | 使用具备 AgentKit 权限的账号或 IAM 用户 AK/SK |
| `model.ark_api_key_name` | **创建 Runtime、Harness、Deployment 时必填** | 已创建的方舟模型 Key **名称**，不是明文 Key，也不是 Environment API Key |
| `model.id` | **创建 Runtime、Harness 时必填** | 账号可用的模型 ID；模板默认 `doubao-seed-evolving`，请确认可用 |
| `model.base_url` | **创建 Runtime、Harness 时必填** | 可保留默认 `https://ark.cn-beijing.volces.com/api/v3` |
| `runtime.role_name` | **新建 Runtime 时必填** | 已存在并授权的执行角色；模板名称不表示脚本会自动创建该角色 |
| `control.workspace_id` | **开启 Workspace 隔离且无默认 Workspace 时必填** | 当前账号可见、状态为 ACTIVE 的目标 Workspace；开启隔离时建议始终显式填写 |
| `route.apig_gateway_id` | **账号没有 Endpoint、需要创建路由时必填** | 目标账号的 APIG Gateway ID；已有 Endpoint 时可留空 |
| `route.endpoint_id` | **账号有多个 Endpoint 时必填** | 明确指定本次复用的 Ready Endpoint；只有一个时可留空 |
| `runtime.user_id` | **新建 Harness 未返回 creator 元数据时必填** | Deployment 触发者的 Runtime 用户标识；IAM 用户填 IAM UserId，主账号填 AccountId |
| `deployment.user_prompt` | **创建 Deployment 时必填** | 首轮用户任务，模板提供默认验收提示词 |
| `verification.second_round_prompt` | **执行 `invoke-session` / `second-round` / `all` 时必填** | 同一 Session 的第二轮用户消息，模板提供默认上下文验收提示词 |

配置按命令检查：`create-route`、`create-environment` 和 `create-session-store` 不要求先填模型 Key。
缺少前置资源时，脚本会提示先执行哪条命令。

### 可选配置与自动生成的 ID

| 配置 | 留空时的行为 |
|---|---|
| `environment.id` | `create-environment` 创建新 Cloud Environment；填值则复用 |
| `session_store.id` | `create-session-store` 创建新托管 PG SessionStore；填值则复用 |
| `runtime.id` | `create-runtime` 使用前一步 SessionStore 创建 Runtime；填值则复用 Ready Runtime |
| `runtime.user_id` | 从本案例新建 Harness 的 creator 元数据读取触发者标识 |
| `deployment.cron` | 只支持手动触发；填写后启用定时，Schedule 创建后不可修改 |
| `cleanup.endpoint_id` | 兼容旧配置；推荐使用 `route.endpoint_id`，清理使用已登记的 Endpoint |

其他字段可保留模板默认值：`control.host`、`region`、`session_store.project_name`、
资源规格、镜像、轮询参数等。`runtime.app_name` 保持 `harness_agent`。

**各步骤返回的 EnvironmentId、ToolId、SessionStoreId、RuntimeId、HarnessId、
DeploymentId 和 SessionId 自动保存，后续步骤直接使用，不需要手工复制回配置。**
`runtime.session_store_id` 仅兼容旧配置，新用户使用 `session_store.id` 或前一步创建结果即可。

### 配置用户提示词

用户提示词在 `config.yaml` 中配置：

```yaml
deployment:
  user_prompt: >-
    请记住本次验收标识 {nonce}。必须调用 bash 执行 printf '{marker}\n'，
    等待工具结果，然后只回复实际输出。不得模拟工具调用。
verification:
  second_round_prompt: >-
    请从首轮上下文取回我要求记住的验收标识。必须调用 bash，
    用 printf 输出 CONTEXT_OK_ 后接该标识并换行；等待工具结果后只回复实际输出。
    本轮不会再次提供标识。不得猜测或模拟工具调用。
```

首轮 `deployment.user_prompt` 中，`{nonce}` 替换为本次随机标识，
`{marker}` 替换为 `DEPLOYMENT_CLOUD_OK_<随机标识>`，其他花括号保持原样。
提示词通过 `InitialEvents` 保存到 Deployment，手动及定时 Run 均使用这份首轮任务；
修改本地提示词后需要重新创建 Deployment，已有 Deployment 不会自动更新。

`verification.second_round_prompt` 在调用 `invoke-session` 时原样发送，
不自动插入首轮随机标识。修改后的消息只对尚未发送的第二轮生效。
系统提示词仍在 `run.py` 的 `create_harness()` 中。

内置 `verify-session` 和第二轮验收要求真实 shell 调用及固定前缀的预期标识。
保留模板任务可直接验收；换成其他业务任务时，需要同步调整 `run.py` 中的验收条件。

## 3. 按顺序创建资源

```bash
python run.py create-route
python run.py create-environment
python run.py create-session-store
python run.py create-runtime
python run.py create-harness
python run.py create-deployment
```

| 命令 | 做什么 | 完成后得到 |
|---|---|---|
| `create-route` | 复用已有 Ready Endpoint；没有时创建路由 | EndpointId、BaseUrl |
| `create-environment` | 创建或复用 Cloud Environment，等待自动 Sandbox Ready | EnvironmentId、实际 ToolId |
| `create-session-store` | 创建或复用 SERVERLESS_PG SessionStore，等待 Ready | SessionStoreId |
| `create-runtime` | 使用执行角色、SessionStore 和 Cloud ToolId 创建 Runtime，等待 Ready | RuntimeId |
| `create-harness` | 配置模型和工具，绑定 Environment/Runtime | HarnessId、固定版本、触发者标识 |
| `create-deployment` | 固定 Harness 版本、目标资源和首轮任务 | DeploymentId |

复用 Runtime 时可跳过 `create-session-store`。该 Runtime 必须已经配置实际 Cloud 工具
后端并发布 `harness_agent`；仅有 Ready 状态不能保证工具可用。

新建 Runtime 时，脚本自动注入 Cloud `HARNESS_SANDBOX_TOOL_ID` 和模型配置，
使用镜像默认入口。无需填写 `Runtime.Port` 或旧 Worker 的启动命令。

## 4. 查看定时任务对应的 Session 并验证执行

**在第 3 节创建 Deployment 前**，在 `config.yaml` 中填写定时配置。例如每 5 分钟执行一次：

```yaml
deployment:
  name_prefix: deployment-cloud-sample
  cron: "*/5 * * * *"
  timezone: Asia/Shanghai
```

`cron` 使用 5 段表达式：分、时、日、月、星期；`timezone` 指定调度时区。
Schedule 创建后不可修改；对已创建的 Deployment 修改本地配置不会改变线上调度。

完成第 3 节后，等待计划触发时间，再查看运行历史：

```bash
python run.py list-deployment-runs
```

输出中的 `trigger_context.type` 为 `schedule` 表示定时触发，`manual` 表示手动触发；
`trigger_context.scheduled_at` 是计划触发时间，`created_at` 是 Run 创建时间。
时间按服务端返回的 UTC 显示，可与配置时区换算后核对。每次定时触发产生独立的 Run 和 Session。

找到要检查的定时 Run，将其 `run_id` 填入以下命令：

```bash
python run.py get-session --run-id '替换为定时任务的 RunId'
python run.py verify-session --run-id '替换为定时任务的 RunId'
```

`get-session` 展示该 Run 对应的 SessionId、用户标识和持久化事件数。
`verify-session` 等待执行完成，检查 Run.Error、真实 `bash` / `Execute` 调用、
配对的工具结果，以及包含本案例预期标识的最终回答；成功后输出对应 RunId、SessionId
和 `first_round` 验收摘要，其中 `read_only: true` 表示检查期间未发送执行消息。
工具结果必须无显式错误，实际工具输出和最终回答都必须包含预期标识。

**定时验收从 `list-deployment-runs` 开始，无需执行 `create-session` 或 `run-deployment`。**
上述查看和验收命令只读取已有 Run 和 Runtime Session，不会额外触发任务。
指定的 Run 必须属于本案例当前 Deployment；选择后，不带 `--run-id` 的查看和验收会继续使用该 Run。

历史为空说明尚未观察到调度 Run，可在计划时间后再次查询；Run 存在、SessionId
存在或 `error_type` 为空都不能单独证明任务完成。出现错误时，按原 RunId 核对；
等待超时后可以重复同一条验收命令继续读取，无需新建 Run。

首轮检查完全只读，不额外发送消息。工具调用必须和唯一、同名的结果按 ID 配对；
工具实际输出和最终回答都必须包含预期标识。当前 Runtime 的 shell 名称可能是
`Execute` 或 `bash`，检查保留实际名称。

Run HTTP 200、SessionId 存在或 SSE HTTP 200 均不能单独证明执行成功。

## 5. 在同一 Session 中继续对话

```bash
python run.py invoke-session
python run.py get-session
```

`invoke-session` 先检查首轮，再向同一 Session 发送第二轮消息。第二轮要求模型从首轮
上下文取回随机标识并执行真实 shell 命令；提示词不重复提供该标识。通过新增持久化
事件检查上下文和工具结果。

需要切换到另一个定时 Run 时，先执行 `get-session --run-id <RunId>` 或
`verify-session --run-id <RunId>` 选择对应 Session，再执行 `invoke-session`。
第二轮已完成时，重复 `invoke-session` 只读检查已有结果，不再次发送消息。

第二轮发送前先保存状态。连接中断后再次执行 `invoke-session` 只读取已有事件，
不自动重发；若请求发送前即中断，需要先核对该 Session 的持久化事件。

## 6. 清理

```bash
python run.py cleanup
```

清理会先暂停 Deployment，分页登记其全部 Run（包括尚未查看的定时 Run），再归档
Deployment、删除 Runtime 执行 Session，并通过已登记的 Endpoint
和临时 Environment Key 删除 AKX 逻辑 Session、撤销临时 Key；之后归档 Harness，
删除自建 Runtime、SessionStore、Sandbox 和 Environment。

账号级 Endpoint、执行角色及复用资源保留。Runtime 执行 Session 和 AKX 逻辑 Session
都需要清理，否则 Sandbox 可能因引用未释放而返回 `ResourceInUse`。

Cloud 执行事件使用 `GetRuntime.Endpoint` 和 Runtime `KeyAuth` 读取：
`/apps/{app_name}/users/{user_id}/sessions/{session_id}`。APIG `/v1/sessions/{id}` 仅用于
本案例的逻辑记录清理，不能替代 Cloud 运行验收。

## 恢复和快捷命令

`--config` 可指定其他本地配置文件。账号配置中的明文 Key 不写入状态或报告。
创建结果未知时保留状态并核对资源：支持 ClientToken 的创建操作恢复时沿用原 token，
平台重放窗口为 24 小时。SessionStore 创建不发送 ClientToken；若结果未知，脚本会停止
再次创建，核对后填写真实 `session_store.id` 恢复。

定时模式按资源创建、等待调度、选择 Run、只读验收和清理的顺序执行。
旧命令 `prepare`、`run`、`verify`、`second-round` 继续兼容，但不是定时验收的必需步骤。

本案例代码只有 `run.py`、`clients.py`；运行检查内置于 `run.py`。
