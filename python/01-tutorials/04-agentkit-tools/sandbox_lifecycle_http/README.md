# 沙箱实例 (Session) 生命周期 HTTP 示例

本目录包含七个不依赖 `agentkit.sdk` 的脚本，覆盖 Session 的创建、查询、调用、暂停、恢复和
删除。其中 `02_list_and_get_session.py` 是只读查询脚本。脚本直接调用 AgentKit Tools
OpenAPI，通过本目录内的 `_http_client.py` 完成 HTTP 请求、HMAC-SHA256 签名、错误解析和
基础重试。带签名的 endpoint 中如果包含 `Authorization` 查询参数，脚本会在输出或保存
状态前自动脱敏。

这套脚本与 `../sandbox_lifecycle` 的 SDK 示例并行存在，运行顺序和状态文件语义保持
一致。

`InvokeTool` 用于在已有 Session 中执行代码；`PauseSession` / `ResumeSession` 用于暂停和恢复同一个 Session。

英文说明请参阅 [README_en.md](README_en.md)。

## 安装依赖

需要 Python 3.10 或更高版本。在仓库根目录安装：

```bash
pip install -r python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/requirements.txt
```

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

- `AGENTKIT_SESSION_TTL_SECONDS`：脚本 01 创建 Session 时的生命周期，默认 `28800`
  秒（8 小时）；脚本 03 调用和脚本 05 恢复时不传入 TTL。
- `AGENTKIT_USER_SESSION_ID`：仅供脚本 01 使用的逻辑会话 ID；未指定时自动生成。
- `AGENTKIT_SESSION_ID`：仅供脚本 02 使用的实例 ID，优先于状态文件中的
  `instance_id`。
- `AGENTKIT_INVOKE_CODE`：脚本 03 执行的 Python 代码，默认
  `print('Hello from AgentKit sandbox!')`。
- `AGENTKIT_INVOKE_TIMEOUT_SECONDS`：脚本 03 的代码执行超时，默认 30 秒，必须为正整数。
- `AGENTKIT_INVOKE_KERNEL_NAME`：脚本 03 使用的内核，默认 `python3`。
- `AGENTKIT_SANDBOX_TOOL_ID`：`AGENTKIT_TOOL_ID` 的兼容变量；同时设置时，两者必须一致。
- `AGENTKIT_LIFECYCLE_STATE`：共享状态文件路径；默认是脚本所在目录中的
  `.sandbox_state.json`，不是运行命令时所在的目录。查询脚本只读取该文件。
- `AGENTKIT_WAIT_TIMEOUT_SECONDS`：创建、暂停和恢复时的状态等待超时，默认 600 秒；
  删除脚本不轮询删除状态。
- `AGENTKIT_POLL_INTERVAL_SECONDS`：状态轮询间隔，默认 5 秒。
- `AGENTKIT_HTTP_TIMEOUT_SECONDS`：单次 HTTP 请求超时，默认 30 秒。
- `AGENTKIT_HTTP_RETRIES`：连接错误、HTTP 429 和 HTTP 503 的重试次数，默认 2。

切换云平台或区域时，请同步更换 Tool ID，并通过 `AGENTKIT_LIFECYCLE_STATE` 指定
不同的状态文件。生命周期操作从脚本 01 开始；查询已有 Session 无需创建新实例。

## 查询 Session 列表与详情

`02_list_and_get_session.py` 分页调用 `ListSessions`，输出当前 Tool 下的全部 Session，
再调用 `GetSession` 查询指定实例的详情。脚本只读取云端资源和本地状态，不修改状态文件。

在仓库根目录运行：

```bash
pip install -r python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/requirements.txt
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/02_list_and_get_session.py
```

默认读取本目录状态文件中的 `tool_id` 和 `instance_id`，也支持
`AGENTKIT_LIFECYCLE_STATE` 指定状态文件。可以在创建、暂停或恢复 Session 后执行。

也可以通过环境变量指定查询目标，无需先运行创建脚本：

```bash
export AGENTKIT_TOOL_ID=t-xxxxxxxx
export AGENTKIT_SESSION_ID="<SessionId>"
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/02_list_and_get_session.py
```

`AGENTKIT_SESSION_ID` 优先于状态文件中的 `instance_id`，填写 API 返回的实例
`SessionId`，不是逻辑会话 `UserSessionId`。Tool ID 沿用环境变量与状态文件的一致性检查。
如果没有指定实例 ID，且状态文件中也没有 `instance_id`，则只列出 Session，输出中的
`session` 为 `null`。空列表正常输出，`GetSession` 返回的 API 错误会直接报告。列表和
详情中的带签名 endpoint 都会自动脱敏。

## 调用 Session 执行代码

`InvokeTool`、`AsyncExecCommand` 和 `ViewAsyncCommand` 使用独立的数据面地址：火山引擎为
`https://agentkit.<region>.volces.com`；[BytePlus 官方文档](https://docs.byteplus.com/en/docs/AgentKit/InvokeTool_-_Executes_command_in_a_tool)
指定新加坡地址为 `https://agentkit.ap-southeast-1.bytepluses.com`，
与管理接口的 `agentkit.ap-southeast-1.byteplusapi.com` 不同。
两个脚本 03 会按云平台和区域自动选择调用地址，API 版本仍为 `2025-10-30`。
通常无需设置 host 覆盖；如果设置了 `BYTEPLUS_AGENTKIT_HOST` 或
`VOLCENGINE_AGENTKIT_HOST`，该地址必须支持对应的数据面 Action。

`03_invoke_session.py` 调用 `InvokeTool`，在状态文件记录的沙箱实例中执行 Python 代码。
请先运行脚本 01 创建实例，并确保实例已就绪；暂停后应先运行脚本 05 恢复，再调用脚本
03。沙箱镜像需要支持 `RunCode` 对应的 `/v1/jupyter/execute` 接口和所选 Python 内核。

请求传入 `ToolId`、状态中的 `instance_id`（作为 `SessionId`）、
`OperationType="RunCode"`，以及 JSON 字符串形式的 `OperationPayload`，其中包含
`code`、`timeout` 和 `kernel_name`。本示例显式传入已有 `SessionId`，并校验返回的
实例 ID 一致；不通过 `UserSessionId` 查找或创建新实例。

在仓库根目录运行，也可以自定义要执行的代码：

```bash
export AGENTKIT_INVOKE_CODE="print(sum([1, 2, 3]))"
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/03_invoke_session.py
```

脚本保存 `invoked_at`、`invoke_response` 和 `invoke_result`，并将返回的 `Result`
JSON 字符串解析为可读结果；标准输出通常位于 `invoke_result.data.outputs`。API 错误
直接报告；代码执行结果中的 `success: false` 或 `data.status: error` 会在保存和打印
结果后报错退出。

## 异步执行 Shell 命令

`03_async_invoke_session.py` 先调用 [AsyncExecCommand](https://docs.volcengine.com/docs/agentkit/AsyncExecCommand_-_Asynchronously_executes_a_Shell_command_in_a_tool?lang=zh)
提交命令，再使用返回的 `TaskId` 循环调用
[ViewAsyncCommand](https://docs.volcengine.com/docs/agentkit/ViewAsyncCommand_-_Queries_the_execution_result_of_an_asynchronous_command?lang=zh)，直到任务结束或本地等待超时。
请先运行步骤 01 创建并等待 Session 就绪；暂停后先通过步骤 05 恢复。
沙箱镜像需要支持这两个 API 对应的异步 Shell 执行能力。复用本目录 `_http_client.py` 的签名、错误处理和数据面地址选择，无需 AgentKit SDK。

提交请求的顶层字段为 `ToolId`、状态中的 `instance_id`（作为 `SessionId`）、
`Command` 和可选的 `ExecDir`；查询使用同一个 `ToolId`、`SessionId` 和返回的 `TaskId`。
不传 `UserSessionId` 或 `Ttl`，并校验响应中的工具、实例和任务 ID。
火山引擎和 BytePlus 均沿用本目录的凭证、区域与 host 配置。

可选环境变量：

- `AGENTKIT_ASYNC_COMMAND`：Shell 命令，默认 `sleep 20 && echo 'Hello from AgentKit sandbox!'`，不能为空。
- `AGENTKIT_ASYNC_EXEC_DIR`：沙箱内已存在的起始目录；未设置时使用沙箱默认目录。
- `AGENTKIT_ASYNC_WAIT_TIMEOUT_SECONDS`：本地轮询等待超时，默认 600 秒。
- `AGENTKIT_ASYNC_POLL_INTERVAL_SECONDS`：查询间隔，默认 2 秒。
  两个时间配置必须为正整数；它们不控制远端命令执行时间或 Session TTL。

在仓库根目录执行，可替换或补充主流程中每次 `03_invoke_session.py` 调用：

```bash
export AGENTKIT_ASYNC_COMMAND="sleep 20 && echo 'Hello from AgentKit sandbox!'"
export AGENTKIT_ASYNC_EXEC_DIR=/tmp
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/03_async_invoke_session.py
```

终端用 `*` 分隔提交（或读取已有任务）、轮询和结束三个阶段；每次查询打印
次数、状态和已等待时间，最后用 `-` 分隔合并的 stdout/stderr 输出与状态文件路径。
状态判断不区分大小写：`running` 继续查询并忽略退出码；`succeeded` 或 `completed`
只有同时满足 `ExitCode=0` 才成功退出。`failed`、`unknown`、未识别状态或完成时
缺失/非零退出码会在保存并打印结果后报错。API 错误直接报告。

提交成功立即保存 `async_task_id`、`async_invoked_at` 和 `async_invoke_response`；
每次查询保存 `async_viewed_at` 与 `async_view_response`。完整响应保留在本目录现有
状态文件（或 `AGENTKIT_LIFECYCLE_STATE` 指定的文件）中，输出位于 `async_view_response.Output`。
等待超时或中断不会取消远端任务；可继续查询已保存的任务：

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/03_async_invoke_session.py --view-only
```

`--view-only` 不提交新命令，忽略命令和目录配置，但仍更新查询结果；不带此参数
重复运行会提交新任务并覆盖本地任务记录，不会取消之前的远端任务。

请在异步命令结束后再暂停或删除 Session。

## 脚本与运行顺序

七个脚本的作用如下：

| 脚本 | 作用 |
| --- | --- |
| `01_create_session.py` | 创建 Session，默认 TTL 为 8 小时；等待就绪并保存实例 ID。 |
| `02_list_and_get_session.py` | 分页列出 Session，查询指定实例详情；只读操作。 |
| `03_invoke_session.py` | 通过 `InvokeTool` 在已有 Session 中执行 Python 代码，校验实例 ID 并保存执行结果。 |
| `03_async_invoke_session.py` | 异步提交 Shell 命令并轮询结果；`--view-only` 继续查询已有任务。 |
| `04_pause_session.py` | 暂停状态文件中的 Session，等待 `Paused` 并记录 `paused_at`。 |
| `05_resume_session.py` | 要求状态文件中有 `paused_at`，恢复同一个 Session，校验实例 ID 不变并等待就绪。 |
| `06_delete_session.py` | 根据 Tool ID 和状态中的 `instance_id` 调用 `DeleteSession` 并保存响应，不等待后台删除完成。 |

验证调用、暂停和恢复时，按 **01 → 02 → 03 → 04 → 05 → 02 → 03** 执行：先创建、
查询和调用，再暂停、恢复，最后查询并再次调用恢复后的实例。脚本 06 是删除操作，
放在完成验证后清理资源时使用。

在仓库根目录执行：

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/01_create_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/02_list_and_get_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/03_invoke_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/04_pause_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/05_resume_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/02_list_and_get_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/03_invoke_session.py
```

执行以下命令清理状态文件记录的实例：

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/06_delete_session.py
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

响应中的业务数据来自 `Result` 字段；如果 `ResponseMetadata.Error` 存在，HTTP client
会抛出异常并包含 action、错误码和错误信息。

## 状态文件

默认状态文件是本目录下的 `.sandbox_state.json`，保存 `tool_id`、`user_session_id`、
`instance_id`、生命周期时间和 API 响应。脚本 01、两个 03、04、05、06 会写入状态，脚本 02
只读取。该文件已在本目录 `.gitignore` 中忽略，不会被提交到 Git。

两个脚本 03 及脚本 04、05、06 根据状态文件中的 `instance_id` 操作实例，不读取
`AGENTKIT_USER_SESSION_ID` 或 `AGENTKIT_SESSION_ID` 来选择目标。

重复运行脚本 01 且不指定 `AGENTKIT_USER_SESSION_ID` 时，会生成新的逻辑会话 ID、
创建新的沙箱实例并覆盖状态文件；之前创建的实例不会被自动删除。
