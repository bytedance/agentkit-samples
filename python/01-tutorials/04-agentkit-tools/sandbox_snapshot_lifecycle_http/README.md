# 沙箱 Session 与快照生命周期 HTTP 示例

这个目录提供一套不依赖 `agentkit.sdk` 的沙箱 Session 与快照生命周期脚本。脚本
直接调用 AgentKit Tools OpenAPI，通过本目录内的 `_http_client.py` 完成 HTTP 请求、
HMAC-SHA256 签名、错误解析和基础重试。

这套脚本与 `../sandbox_snapshot_lifecycle` 的 SDK 示例并行存在，运行顺序和状态文件
语义保持一致。带签名的 endpoint 中如果包含 `Authorization` 查询参数，脚本会在输出
或保存状态前自动脱敏。

流程为：**创建 Session → 调用 Session → 创建快照 → 列出并获取快照 → 等待 Session
生命周期结束后从快照恢复 → 再次调用 Session → 删除快照 → 删除 Session**。
恢复后的调用复用脚本 02。

**从快照恢复必须在原 Session 生命周期结束之后进行。** 本示例等待 TTL 到期、
实例终止后，使用 `ResumeSessionFromSnapshot` 恢复原实例。
**主动调用 `DeleteSession` 也会删除该 Session 对应的快照，因此删除 Session 必须放在最后，
不能用它作为恢复前结束生命周期的手段。**

英文说明请参阅 [README_en.md](README_en.md)。

## 安装依赖

```bash
pip install -r python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/requirements.txt
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

- `AGENTKIT_SESSION_TTL_SECONDS`：Session 和恢复后实例的生命周期，默认 `28800`
  秒（8 小时）；脚本 02 调用时不传入 TTL。
- `AGENTKIT_USER_SESSION_ID`：逻辑会话 ID；如果不指定，脚本 01 会自动生成。
- `AGENTKIT_INVOKE_CODE`：脚本 02 执行的 Python 代码，默认
  `print('Hello from AgentKit sandbox!')`。
- `AGENTKIT_INVOKE_TIMEOUT_SECONDS`：脚本 02 的代码执行超时，默认 30 秒，必须为正整数。
- `AGENTKIT_INVOKE_KERNEL_NAME`：脚本 02 使用的内核，默认 `python3`。
- `AGENTKIT_LIFECYCLE_STATE`：七个脚本共享的状态文件路径；默认使用本示例目录的
  `.sandbox_snapshot_state.json`。
- `AGENTKIT_WAIT_TIMEOUT_SECONDS`：等待资源就绪或删除完成的超时时间，默认 600 秒。
- `AGENTKIT_POLL_INTERVAL_SECONDS`：状态轮询间隔，默认 5 秒。
- `AGENTKIT_HTTP_TIMEOUT_SECONDS`：单次 HTTP 请求超时，默认 30 秒。
- `AGENTKIT_HTTP_RETRIES`：连接错误、HTTP 429 和 HTTP 503 的重试次数，默认 2。

火山引擎的 `InvokeTool` 使用独立的数据面地址
`https://agentkit.<region>.volces.com`。脚本 02 会自动选择该地址；如通过
`VOLCENGINE_AGENTKIT_HOST` 覆盖服务域名，所填地址也必须支持 `InvokeTool`。

## 调用 Session 执行代码

`02_invoke_session.py` 调用 `InvokeTool`，在状态文件记录的沙箱实例中执行 Python 代码。
请在脚本 01 创建实例并等待就绪后调用，或在脚本 05 从快照恢复并等待就绪后再次调用。
沙箱镜像需要支持 `RunCode` 对应的 `/v1/jupyter/execute` 接口和所选 Python 内核。

请求传入 `ToolId`、状态中的 `instance_id`（作为 `SessionId`）、
`OperationType="RunCode"`，以及 JSON 字符串形式的 `OperationPayload`，
其中包含 `code`、`timeout` 和 `kernel_name`。脚本显式调用已有 `SessionId`，
并校验返回的实例 ID 一致；不通过 `UserSessionId` 查找或创建新实例。

在仓库根目录运行，也可以自定义要执行的代码：

```bash
export AGENTKIT_INVOKE_CODE="print(sum([1, 2, 3]))"
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/02_invoke_session.py
```

脚本保存 `invoked_at`、`invoke_response` 和 `invoke_result`，并将返回的 `Result`
JSON 字符串解析为可读结果；标准输出通常位于 `invoke_result.data.outputs`。API 错误
直接报告；代码执行结果中的 `success: false` 或 `data.status: error` 会在保存和打印
结果后报错退出。

## 按顺序运行主流程

默认 TTL 为 8 小时。如需缩短演示等待时间，可在运行脚本 01 **之前**设置较短的
TTL，例如：

```bash
export AGENTKIT_SESSION_TTL_SECONDS=60
export AGENTKIT_WAIT_TIMEOUT_SECONDS=900
```

请为步骤 01-04 留出足够时间。创建后再修改此环境变量不会改变原 Session 的到期时间，
只会影响后续创建或恢复时使用的 TTL。

在仓库根目录执行步骤 01-04，创建并调用 Session，然后创建和查询快照：

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/01_create_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/02_invoke_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/03_create_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/04_list_and_get_snapshot.py
```

等待原 Session 的 TTL 到期，生命周期结束后，再运行步骤 05。脚本 01 输出的
`session.ExpireAt` 可用于查看到期时间（若服务返回该字段）：

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/05_restore_from_snapshot.py
```

若过早运行步骤 05，后端返回 `InvalidSnapshot.InstanceAlreadyExists`（实例仍在使用）
或 `InvalidSnapshot.InstanceTerminating`（实例正在终止）时，脚本会按轮询间隔重试，
直到允许恢复或达到等待超时。超时后可等 Session 生命周期结束再重跑步骤 05，
或增加 `AGENTKIT_WAIT_TIMEOUT_SECONDS`。其他 API 错误会直接抛出。

步骤 05 成功后，可再次运行脚本 02，确认恢复后的实例可以执行代码：

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/02_invoke_session.py
```

完成验证后，按顺序清理快照和恢复后的 Session：

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/06_delete_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/07_delete_session.py
```

各脚本的作用：

1. `01_create_session.py`：检查 Tool 是否开启快照，创建 Session，并等待沙箱实例进入
   `Ready`。
2. `02_invoke_session.py`：通过 `InvokeTool` 在已有 Session 中执行 Python 代码，
   校验实例 ID 并保存执行结果；恢复后可再次运行。
3. `03_create_snapshot.py`：主动为 Session 对应的沙箱实例创建快照，并等待快照进入
   `Ready`。
4. `04_list_and_get_snapshot.py`：分页列出 Tool 下的全部快照，并单独获取刚创建的
   快照详情。
5. `05_restore_from_snapshot.py`：等待原 Session 生命周期结束后，以
   `CreateNewInstance=false` 从快照恢复原沙箱，并校验恢复后的 `SessionId` 必须与
   脚本 01 保存的实例 ID 一致。如果实例仍在使用或处于异步终止状态，脚本会自动等待并
   重试。
6. `06_delete_snapshot.py`：删除状态文件记录的快照，分页检查 Tool 下的快照列表，并
   等待目标快照彻底消失。该脚本不会删除步骤 05 恢复出来的沙箱实例。
7. `07_delete_session.py`：最后删除 Session。主动调用 `DeleteSession` 也会删除该
   Session 对应的其他剩余快照，因此不能用它作为步骤 05 恢复前结束生命周期的手段。

暂停和恢复运行中的 Session 请参阅相邻的
[sandbox_lifecycle_http](../sandbox_lifecycle_http/README.md) 示例。

## HTTP 请求形态

所有接口都使用 `POST /?Action=<Action>&Version=2025-10-30`，请求 body 使用
PascalCase JSON 字段，例如：

```json
{
  "ToolId": "t-xxxxxxxx",
  "Ttl": 28800,
  "TtlUnit": "second",
  "UserSessionId": "snapshot-demo-xxxx"
}
```

响应中的业务数据来自 `Result` 字段；如果 `ResponseMetadata.Error` 存在，HTTP client
会抛出异常并包含 action、错误码和错误信息。

## 状态文件

七个脚本通过 `.sandbox_snapshot_state.json` 传递 `tool_id`、逻辑会话 ID、沙箱实例
ID 和快照 ID。脚本 02 还保存 `invoked_at`、`invoke_response` 和 `invoke_result`，
再次调用会更新这些字段。该文件已在本目录 `.gitignore` 中忽略，不会被提交到 Git。

重复运行脚本 01 且不指定 `AGENTKIT_USER_SESSION_ID` 时，会生成新的逻辑会话 ID、
创建新的沙箱实例并覆盖状态文件；之前创建的实例不会被自动删除。
