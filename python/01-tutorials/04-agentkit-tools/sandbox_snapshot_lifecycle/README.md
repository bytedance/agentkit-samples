# 沙箱 Session 与快照生命周期脚本

这七个脚本按顺序演示沙箱 Session 与快照生命周期。脚本使用 `agentkit-sdk-python` 的
`agentkit.sdk.tools` 客户端，不会保存 AK/SK。带签名的 endpoint 中如果包含
`Authorization` 查询参数，脚本会在输出或保存状态前自动脱敏。

流程为：**创建 Session → 调用 Session → 创建快照 → 列出并获取快照 → 等待 Session
生命周期结束后从快照恢复 → 再次调用 Session → 删除快照 → 删除 Session**。
恢复后的调用复用脚本 02。

**从快照恢复必须在原 Session 生命周期结束之后进行。** 本示例等待 TTL 到期、
实例终止后，使用 `ResumeSessionFromSnapshot` 恢复原实例。
**主动调用 `DeleteSession` 也会删除该 Session 对应的快照，因此删除 Session 必须放在最后，
不能用它作为恢复前结束生命周期的手段。**

英文说明请参阅 [README_en.md](README_en.md)。

## 安装依赖

本示例使用 `agentkit-sdk-python==0.8.7`。在仓库根目录安装依赖：

```bash
pip install -r python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/requirements.txt
```

## 环境变量

根据沙箱所在云平台，选择下面一组配置。七个脚本共用同一套凭证和区域配置。

**火山引擎：**

```bash
export AGENTKIT_CLOUD_PROVIDER=volcengine
export VOLCENGINE_ACCESS_KEY="<Your Access Key>"
export VOLCENGINE_SECRET_KEY="<Your Secret Key>"
export VOLCENGINE_REGION=cn-beijing
export AGENTKIT_TOOL_ID=t-xxxxxxxx
```

**BytePlus：**

```bash
export AGENTKIT_CLOUD_PROVIDER=byteplus
export BYTEPLUS_ACCESS_KEY="<Your Access Key>"
export BYTEPLUS_SECRET_KEY="<Your Secret Key>"
export BYTEPLUS_REGION=ap-southeast-1
export AGENTKIT_TOOL_ID=t-xxxxxxxx
```

Tool ID 必须属于所选云平台、账号和区域，且已开启快照功能（`EnableSnapshot=true`）。
SDK 会按云平台自动选择管理接口地址；BytePlus 新加坡区域默认为
`https://agentkit.ap-southeast-1.byteplusapi.com`。

`InvokeTool` 使用独立的数据面地址：火山引擎为
`https://agentkit.<region>.volces.com`；[BytePlus 官方文档](https://docs.byteplus.com/en/docs/AgentKit/InvokeTool_-_Executes_command_in_a_tool)
指定新加坡地址为 `https://agentkit.ap-southeast-1.bytepluses.com`，
与管理接口的 `agentkit.ap-southeast-1.byteplusapi.com` 不同。
脚本 02 会按云平台和区域自动选择调用地址，API 版本仍为 `2025-10-30`。
通常无需设置 host 覆盖；如果设置了 `BYTEPLUS_AGENTKIT_HOST` 或
`VOLCENGINE_AGENTKIT_HOST`，该地址必须支持 `InvokeTool`。

`AGENTKIT_CLOUD_PROVIDER` 优先于兼容变量 `CLOUD_PROVIDER`；均未设置时沿用 SDK
全局配置中的云平台，未配置则使用火山引擎。火山引擎凭证兼容旧变量名
`VOLC_ACCESSKEY` / `VOLC_SECRETKEY`，BytePlus 使用独立的 `BYTEPLUS_*` 凭证。
使用临时凭证时，还需设置对应的 `VOLCENGINE_SESSION_TOKEN` 或 `BYTEPLUS_SESSION_TOKEN`。

可选配置：

- `AGENTKIT_SESSION_TTL_SECONDS`：脚本 01 创建 Session 和脚本 05 恢复实例时的生命周期，
  默认 `28800` 秒（8 小时）；脚本 02 调用时不传入 TTL。
- `AGENTKIT_USER_SESSION_ID`：逻辑会话 ID；如果不指定，脚本 01 会自动生成。
- `AGENTKIT_INVOKE_CODE`：脚本 02 执行的 Python 代码，默认
  `print('Hello from AgentKit sandbox!')`。
- `AGENTKIT_INVOKE_TIMEOUT_SECONDS`：脚本 02 的代码执行超时，默认 30 秒，必须为正整数。
- `AGENTKIT_INVOKE_KERNEL_NAME`：脚本 02 使用的内核，默认 `python3`。
- `AGENTKIT_LIFECYCLE_STATE`：七个脚本共享的状态文件路径；默认使用本示例目录的
  `.sandbox_snapshot_state.json`。
- `AGENTKIT_WAIT_TIMEOUT_SECONDS`：每次等待资源就绪、恢复条件满足或快照删除完成的
  超时时间，默认 600 秒；不会改变 Session 的 TTL。
- `AGENTKIT_POLL_INTERVAL_SECONDS`：状态轮询间隔，默认 5 秒。
- `BYTEPLUS_AGENTKIT_REGION`（BytePlus）或 `VOLCENGINE_AGENTKIT_REGION`（火山引擎）：
  当前云平台的 AgentKit 区域，优先于通用覆盖变量 `AGENTKIT_REGION`；均未设置时，
  由 SDK 按 `BYTEPLUS_REGION` / `VOLCENGINE_REGION`、全局配置及默认区域解析。
- `BYTEPLUS_AGENTKIT_HOST` 或 `VOLCENGINE_AGENTKIT_HOST`：可选的当前云平台服务域名
  覆盖，仅填写主机名，不含 `https://`；通常无需设置。脚本 02 也会遵循该覆盖，
  所填地址必须支持 `InvokeTool`，不能为其配置火山引擎通用 OpenAPI 或 BytePlus 管理接口域名。

切换云平台或区域时，请同步更换 Tool ID，并通过 `AGENTKIT_LIFECYCLE_STATE` 指定
不同的状态文件，从脚本 01 开始运行。

## 调用 Session 执行代码

`02_invoke_session.py` 通过 [InvokeTool](https://docs.volcengine.com/docs/AgentKit/InvokeTool-Executescommandinatool?lang=zh)
在状态文件记录的沙箱实例中执行 Python 代码。请在脚本 01 创建实例并等待就绪后调用，
或在脚本 05 从快照恢复并等待就绪后再次调用。
沙箱镜像需要支持 `RunCode` 对应的 `/v1/jupyter/execute` 接口和所选 Python 内核。

请求传入 `ToolId`、状态中的 `instance_id`（作为 `SessionId`）、
`OperationType="RunCode"`，以及 JSON 字符串形式的 `OperationPayload`，
其中包含 `code`、`timeout` 和 `kernel_name`。脚本显式调用已有 `SessionId`，
并校验返回的实例 ID 一致；不通过 `UserSessionId` 查找或创建新实例。
`AGENTKIT_USER_SESSION_ID` 或 `AGENTKIT_SESSION_ID` 不会改变调用目标。

在仓库根目录运行，也可以自定义要执行的代码：

```bash
export AGENTKIT_INVOKE_CODE="print(sum([1, 2, 3]))"
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/02_invoke_session.py
```

脚本保存 `invoked_at`、`invoke_response` 和 `invoke_result`，并将返回的 `Result`
JSON 字符串解析为可读结果；标准输出通常位于 `invoke_result.data.outputs`。
API 错误直接报告；代码执行结果中的 `success: false` 或 `data.status: error`
会在保存和打印结果后报错退出。

SDK 0.8.7 尚未提供 `InvokeTool` 专用方法，因此脚本补充该 Action 的注册，
复用 SDK 的签名、凭证刷新和 API 错误处理，无需升级依赖。

## 按顺序运行

默认 TTL 为 8 小时。如需缩短演示等待时间，可在运行脚本 01 **之前**设置较短的
TTL，例如：

```bash
export AGENTKIT_SESSION_TTL_SECONDS=600
```

请为步骤 01–04 留出足够时间。创建后再修改此环境变量不会改变原 Session 的到期时间，
只会影响后续创建或恢复时使用的 TTL。

在仓库根目录执行步骤 01–04，创建并调用 Session，然后创建和查询快照：

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/01_create_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/02_invoke_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/03_create_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/04_list_and_get_snapshot.py
```

等待原 Session 的 TTL 到期，生命周期结束后，再运行步骤 05。脚本 01 输出的
`session.ExpireAt` 可用于查看到期时间（若服务返回该字段）：

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/05_restore_from_snapshot.py
```

若过早运行步骤 05，后端返回 `InvalidSnapshot.InstanceAlreadyExists`（实例仍在使用）
或 `InvalidSnapshot.InstanceTerminating`（实例正在终止）时，脚本会按轮询间隔重试，
直到允许恢复或达到等待超时。超时后可等 Session 生命周期结束再重跑步骤 05，
或增加 `AGENTKIT_WAIT_TIMEOUT_SECONDS`。其他 API 错误会直接抛出。

步骤 05 成功后，可再次运行脚本 02，确认恢复后的实例可以执行代码：

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/02_invoke_session.py
```

完成验证后，按顺序清理快照和恢复后的 Session：

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/06_delete_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/07_delete_session.py
```

| 步骤 | 脚本 | 行为 |
| --- | --- | --- |
| 01 | `01_create_session.py` | 创建 Session，记录实例 ID，并等待实例就绪。 |
| 02 | `02_invoke_session.py` | 通过 `InvokeTool` 在已有 Session 中执行 Python 代码，校验实例 ID 并保存执行结果；恢复后可再次运行。 |
| 03 | `03_create_snapshot.py` | 为该实例创建快照，记录快照 ID，并等待快照就绪。 |
| 04 | `04_list_and_get_snapshot.py` | 分页列出 Tool 下全部快照，再获取本次快照详情。 |
| 05 | `05_restore_from_snapshot.py` | 等原 Session 生命周期结束，以 `CreateNewInstance=false` 恢复，校验 `SessionId` 与步骤 01 一致，并等待实例就绪。 |
| 06 | `06_delete_snapshot.py` | 删除本次快照，并轮询列表确认其消失；恢复后的 Session 继续保留。 |
| 07 | `07_delete_session.py` | 最后删除 Session；服务端也会删除该 Session 对应的其他剩余快照。 |

步骤 06 单独演示删除快照；步骤 07 完成 Session 的最终清理。暂停和恢复运行中的
Session 请参阅相邻的 [sandbox_lifecycle](../sandbox_lifecycle/README.md) 示例。

## 状态文件

七个脚本通过 `.sandbox_snapshot_state.json` 传递 `tool_id`、逻辑会话 ID、沙箱
实例 ID 和快照 ID。脚本 02 还保存 `invoked_at`、`invoke_response` 和 `invoke_result`，
再次调用会更新这些字段。默认状态文件及其临时文件已加入本目录的 `.gitignore`。
若自定义状态文件路径，请自行确保该文件不会被提交到 Git。

如果状态文件已记录步骤 06 或 07 的删除操作，步骤 05 会提示从步骤 01 开始新一轮流程。
清理后会保留本地状态文件，便于查看执行记录。

重复运行脚本 01 且不指定 `AGENTKIT_USER_SESSION_ID` 时，会生成新的逻辑会话 ID、
创建新的沙箱实例并覆盖状态文件；之前创建的实例不会被自动删除。
