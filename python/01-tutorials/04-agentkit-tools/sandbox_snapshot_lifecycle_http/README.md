# 沙箱 Session 与快照生命周期 HTTP 示例

这个目录提供一套不依赖 `agentkit.sdk` 的沙箱 Session 与快照生命周期脚本。脚本
直接调用 AgentKit Tools OpenAPI，通过本目录内的 `_http_client.py` 完成 HTTP 请求、
HMAC-SHA256 签名、错误解析和基础重试。

这套脚本与 `../sandbox_snapshot_lifecycle` 的 SDK 示例并行存在，运行顺序和状态文件
语义保持一致。带签名的 endpoint 中如果包含 `Authorization` 查询参数，脚本会在输出
或保存状态前自动脱敏。

`PauseSession` / `ResumeSession` 用于暂停和恢复同一个 Session；
`ResumeSessionFromSnapshot` 用于从快照恢复实例，两者不是同一个接口。

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

## 生命周期参数

- `AGENTKIT_SESSION_TTL_SECONDS`：Session 和恢复后实例的生命周期，默认 `28800`
  秒（8 小时）。
- `AGENTKIT_USER_SESSION_ID`：逻辑会话 ID；如果不指定，脚本 01 会自动生成。
- `AGENTKIT_LIFECYCLE_STATE`：八个脚本共享的状态文件路径；默认使用当前目录的
  `.sandbox_snapshot_state.json`。
- `AGENTKIT_WAIT_TIMEOUT_SECONDS`：等待资源就绪或删除完成的超时时间，默认 600 秒。
- `AGENTKIT_POLL_INTERVAL_SECONDS`：状态轮询间隔，默认 5 秒。
- `AGENTKIT_HTTP_TIMEOUT_SECONDS`：单次 HTTP 请求超时，默认 30 秒。
- `AGENTKIT_HTTP_RETRIES`：连接错误、HTTP 429 和 HTTP 503 的重试次数，默认 2。

## 按顺序运行

在仓库根目录依次执行：

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/01_create_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/02_create_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/03_list_and_get_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/04_delete_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/05_restore_from_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/06_delete_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/07_pause_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/08_resume_session.py
```

各脚本的作用：

1. `01_create_session.py`：检查 Tool 是否开启快照，创建 Session，并等待沙箱实例进入
   `Ready`。
2. `02_create_snapshot.py`：主动为 Session 对应的沙箱实例创建快照，并等待快照进入
   `Ready`。
3. `03_list_and_get_snapshot.py`：分页列出 Tool 下的全部快照，并单独获取刚创建的
   快照详情。
4. `04_delete_session.py`：删除 Session 对应的沙箱实例，但保留快照。
5. `05_restore_from_snapshot.py`：以 `CreateNewInstance=false` 从快照恢复原沙箱，并
   校验恢复后的 `SessionId` 必须与脚本 01 保存的实例 ID 一致。如果实例仍处于异步
   终止状态，脚本会自动等待并重试。
6. `06_delete_snapshot.py`：删除状态文件记录的快照，分页检查 Tool 下的快照列表，并
   等待目标快照彻底消失。该脚本不会删除脚本 05 恢复出来的沙箱实例。
7. `07_pause_session.py`：暂停状态文件中的 Session，轮询 `GetSession`，直到 Session
   进入 `Paused` 状态。该脚本也可以在脚本 01 之后直接运行。
8. `08_resume_session.py`：恢复同一个 Session，校验实例 ID 不变，并等待 Session
   重新进入 `Ready` 状态。

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

八个脚本通过 `.sandbox_snapshot_state.json` 传递 `tool_id`、逻辑会话 ID、沙箱实例
ID 和快照 ID。该文件已在本目录 `.gitignore` 中忽略，不会被提交到 Git。

重复运行脚本 01 且不指定 `AGENTKIT_USER_SESSION_ID` 时，会生成新的逻辑会话 ID、
创建新的沙箱实例并覆盖状态文件；之前创建的实例不会被自动删除。
