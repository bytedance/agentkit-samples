# 沙箱实例 (Session) 生命周期 HTTP 示例（Go）

这个目录提供一套不依赖 AgentKit SDK 的 Go 示例，覆盖 Session 的创建、查询、调用、暂停、恢复和
删除。代码直接调用 AgentKit Tools OpenAPI，通过 `internal/lifecycle` 中的标准库 HTTP
client 完成请求、HMAC-SHA256 签名、错误解析、基础重试、状态文件读写和轮询等待。

这套示例与 Python 目录
`python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http` 并行存在，接口顺序和
状态文件语义保持一致。带签名的 endpoint 中如果包含 `Authorization` 查询参数，示例会在
输出或保存状态前自动脱敏。

`InvokeTool` 用于在已有 Session 中执行代码；`PauseSession` / `ResumeSession` 用于暂停和恢复同一个 Session。

英文说明请参阅 [README_en.md](README_en.md)。

## 环境要求

- Go 1.20+。
- 不需要安装 AgentKit SDK。
- 示例只使用 Go 标准库，因此没有额外依赖和 `go.sum`。

## 火山站点配置

火山站点是默认站点；也可以显式设置：

```bash
export AGENTKIT_CLOUD_PROVIDER=volcengine
export VOLCENGINE_ACCESS_KEY=<your-access-key>
export VOLCENGINE_SECRET_KEY=<your-secret-key>
export AGENTKIT_TOOL_ID=t-xxxxxxxx
```

兼容旧变量名：

- `VOLC_ACCESSKEY`
- `VOLC_SECRETKEY`
- `VOLC_SESSIONTOKEN`
- `VOLC_REGION`

可选配置：

- `VOLCENGINE_SESSION_TOKEN`：STS 临时凭证 token。
- `VOLCENGINE_AGENTKIT_REGION` 或 `AGENTKIT_REGION`：AgentKit OpenAPI 签名地域，
  默认 `cn-beijing`。
- `VOLCENGINE_AGENTKIT_HOST`：自定义 OpenAPI host，默认 `open.volcengineapi.com`。
- `VOLCENGINE_AGENTKIT_SERVICE`：签名 service，默认 `agentkit`。
- `VOLCENGINE_AGENTKIT_API_VERSION`：OpenAPI 版本，默认 `2025-10-30`。
- `VOLCENGINE_AGENTKIT_SCHEME`：请求协议，默认 `https`。

## BytePlus 站点配置

```bash
export AGENTKIT_CLOUD_PROVIDER=byteplus
export BYTEPLUS_ACCESS_KEY=<your-access-key>
export BYTEPLUS_SECRET_KEY=<your-secret-key>
export AGENTKIT_TOOL_ID=t-xxxxxxxx
```

可选配置：

- `BYTEPLUS_SESSION_TOKEN`：STS 临时凭证 token。
- `BYTEPLUS_AGENTKIT_REGION`、`AGENTKIT_REGION` 或 `BYTEPLUS_REGION`：AgentKit
  OpenAPI 签名地域，默认 `ap-southeast-1`。
- `BYTEPLUS_AGENTKIT_HOST`：自定义 OpenAPI host，默认
  `agentkit.<region>.byteplusapi.com`。
- `BYTEPLUS_AGENTKIT_SERVICE`：签名 service，默认 `agentkit`。
- `BYTEPLUS_AGENTKIT_API_VERSION`：OpenAPI 版本，默认 `2025-10-30`。
- `BYTEPLUS_AGENTKIT_SCHEME`：请求协议，默认 `https`。

## 生命周期参数

- `AGENTKIT_SESSION_TTL_SECONDS`：命令 01 创建 Session 时的生命周期，默认 `28800`
  秒（8 小时）；命令 03 调用和命令 05 恢复时不传入 TTL。
- `AGENTKIT_USER_SESSION_ID`：仅供命令 01 使用的逻辑会话 ID；未指定时自动生成。
- `AGENTKIT_SESSION_ID`：仅供命令 02 使用的实例 ID，优先于状态文件中的
  `instance_id`。
- `AGENTKIT_INVOKE_CODE`：命令 03 执行的 Python 代码，默认
  `print('Hello from AgentKit sandbox!')`。
- `AGENTKIT_INVOKE_TIMEOUT_SECONDS`：命令 03 的代码执行超时，默认 30 秒，必须为正整数。
- `AGENTKIT_INVOKE_KERNEL_NAME`：命令 03 使用的内核，默认 `python3`。
- `AGENTKIT_SANDBOX_TOOL_ID`：`AGENTKIT_TOOL_ID` 的兼容变量；同时设置时，两者必须一致。
- `AGENTKIT_LIFECYCLE_STATE`：共享状态文件路径；默认是本目录中的
  `.sandbox_state.json`，不是运行命令时所在的目录。查询命令只读取该文件。
- `AGENTKIT_WAIT_TIMEOUT_SECONDS`：创建、暂停和恢复时的状态等待超时，默认 600 秒；
  删除命令不轮询删除状态。
- `AGENTKIT_POLL_INTERVAL_SECONDS`：状态轮询间隔，默认 5 秒。
- `AGENTKIT_HTTP_TIMEOUT_SECONDS`：单次 HTTP 请求超时，默认 30 秒。
- `AGENTKIT_HTTP_RETRIES`：连接错误、HTTP 429 和 HTTP 503 的重试次数，默认 2。

火山引擎的 `InvokeTool` 使用独立的数据面地址
`https://agentkit.<region>.volces.com`。命令 03 会自动选择该地址；如通过
`VOLCENGINE_AGENTKIT_HOST` 覆盖服务域名，所填地址也必须支持 `InvokeTool`。

切换云平台或区域时，请同步更换 Tool ID，并通过 `AGENTKIT_LIFECYCLE_STATE` 指定
不同的状态文件。生命周期操作从命令 01 开始；查询已有 Session 无需创建新实例。

## 查询 Session 列表与详情

`02_list_and_get_session` 分页调用 `ListSessions`，输出当前 Tool 下的全部 Session，
再调用 `GetSession` 查询指定实例的详情。命令只读取云端资源和本地状态，不修改状态文件。

也可以通过环境变量指定查询目标，无需先运行创建命令：

```bash
export AGENTKIT_TOOL_ID=t-xxxxxxxx
export AGENTKIT_SESSION_ID="<SessionId>"
go run ./cmd/02_list_and_get_session
```

`AGENTKIT_SESSION_ID` 优先于状态文件中的 `instance_id`，填写 API 返回的实例
`SessionId`，不是逻辑会话 `UserSessionId`。Tool ID 沿用环境变量与状态文件的一致性检查。
如果没有指定实例 ID，且状态文件中也没有 `instance_id`，则只列出 Session，输出中的
`session` 为 `null`。

## 调用 Session 执行代码

`03_invoke_session` 调用 `InvokeTool`，在状态文件记录的沙箱实例中执行 Python 代码。
请先运行命令 01 创建实例，并确保实例已就绪；暂停后应先运行命令 05 恢复，再调用命令
03。沙箱镜像需要支持 `RunCode` 对应的 `/v1/jupyter/execute` 接口和所选 Python 内核。

请求传入 `ToolId`、状态中的 `instance_id`（作为 `SessionId`）、
`OperationType="RunCode"`，以及 JSON 字符串形式的 `OperationPayload`，其中包含
`code`、`timeout` 和 `kernel_name`。本示例显式传入已有 `SessionId`，并校验返回的
实例 ID 一致；不通过 `UserSessionId` 查找或创建新实例。

在本目录运行，也可以自定义要执行的代码：

```bash
export AGENTKIT_INVOKE_CODE="print(sum([1, 2, 3]))"
go run ./cmd/03_invoke_session
```

命令保存 `invoked_at`、`invoke_response` 和 `invoke_result`，并将返回的 `Result`
JSON 字符串解析为可读结果；标准输出通常位于 `invoke_result.data.outputs`。API 错误
直接报告；代码执行结果中的 `success: false` 或 `data.status: error` 会在保存和打印
结果后报错退出。

## 脚本与运行顺序

六个命令的作用如下：

| 命令 | 作用 |
| --- | --- |
| `01_create_session` | 创建 Session，默认 TTL 为 8 小时；等待就绪并保存实例 ID。 |
| `02_list_and_get_session` | 分页列出 Session，查询指定实例详情；只读操作。 |
| `03_invoke_session` | 通过 `InvokeTool` 在已有 Session 中执行 Python 代码，校验实例 ID 并保存执行结果。 |
| `04_pause_session` | 暂停状态文件中的 Session，等待 `Paused` 并记录 `paused_at`。 |
| `05_resume_session` | 要求状态文件中有 `paused_at`，恢复同一个 Session，校验实例 ID 不变并等待就绪。 |
| `06_delete_session` | 根据 Tool ID 和状态中的 `instance_id` 调用 `DeleteSession` 并保存响应，不等待后台删除完成。 |

验证调用、暂停和恢复时，按 **01 -> 02 -> 03 -> 04 -> 05 -> 02 -> 03** 执行。
命令 06 是删除操作，放在完成验证后清理资源时使用。

在本目录执行：

```bash
go run ./cmd/01_create_session
go run ./cmd/02_list_and_get_session
go run ./cmd/03_invoke_session
go run ./cmd/04_pause_session
go run ./cmd/05_resume_session
go run ./cmd/02_list_and_get_session
go run ./cmd/03_invoke_session
```

执行以下命令清理状态文件记录的实例：

```bash
go run ./cmd/06_delete_session
```

## HTTP 请求形态

所有接口都使用 `POST /?Action=<Action>&Version=2025-10-30`，请求 body 使用
PascalCase JSON 字段，例如：

```json
{
  "ToolId": "t-xxxxxxxx",
  "Ttl": 28800,
  "TtlUnit": "second",
  "UserSessionId": "session-demo-xxxx"
}
```

业务数据来自响应的 `Result` 字段；如果 `ResponseMetadata.Error` 存在，HTTP client
会返回包含 action、错误码和错误信息的错误。

## 状态文件

默认状态文件是本目录下的 `.sandbox_state.json`，保存 `tool_id`、`user_session_id`、
`instance_id`、生命周期时间和 API 响应。命令 01、03、04、05、06 会写入状态，命令 02
只读取。该文件已在本目录 `.gitignore` 中忽略，不会被提交到 Git。

命令 03、04、05、06 根据状态文件中的 `instance_id` 操作实例，不读取
`AGENTKIT_USER_SESSION_ID` 或 `AGENTKIT_SESSION_ID` 来选择目标。

重复运行命令 01 且不指定 `AGENTKIT_USER_SESSION_ID` 时，会生成新的逻辑会话 ID、
创建新的沙箱实例并覆盖状态文件；之前创建的实例不会被自动删除。

## 本地验证

```bash
go test ./...
```
