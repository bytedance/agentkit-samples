# 沙箱 Session 与快照生命周期脚本

这六个脚本按顺序演示沙箱 Session 与快照生命周期。脚本使用 `agentkit-sdk-python` 的
`agentkit.sdk.tools` 客户端，不会保存 AK/SK。带签名的 endpoint 中如果包含
`Authorization` 查询参数，脚本会在输出或保存状态前自动脱敏。

流程为：**创建 Session → 创建快照 → 列出并获取快照 → 等待 Session 生命周期结束后
从快照恢复 → 删除快照 → 删除 Session**。

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

根据沙箱所在云平台，选择下面一组配置。六个脚本共用同一个客户端配置。

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
SDK 会按云平台自动选择服务地址；BytePlus 新加坡区域默认为
`https://agentkit.ap-southeast-1.byteplusapi.com`。

`AGENTKIT_CLOUD_PROVIDER` 优先于兼容变量 `CLOUD_PROVIDER`；均未设置时沿用 SDK
全局配置中的云平台，未配置则使用火山引擎。火山引擎凭证兼容旧变量名
`VOLC_ACCESSKEY` / `VOLC_SECRETKEY`，BytePlus 使用独立的 `BYTEPLUS_*` 凭证。
使用临时凭证时，还需设置对应的 `VOLCENGINE_SESSION_TOKEN` 或 `BYTEPLUS_SESSION_TOKEN`。

可选配置：

- `AGENTKIT_SESSION_TTL_SECONDS`：Session 和恢复后实例的生命周期，默认
  `28800` 秒（8 小时）。
- `AGENTKIT_USER_SESSION_ID`：逻辑会话 ID；如果不指定，脚本 01 会自动生成。
- `AGENTKIT_LIFECYCLE_STATE`：六个脚本共享的状态文件路径；默认使用本示例目录的
  `.sandbox_snapshot_state.json`。
- `AGENTKIT_WAIT_TIMEOUT_SECONDS`：每次等待资源就绪、恢复条件满足或快照删除完成的
  超时时间，默认 600 秒；不会改变 Session 的 TTL。
- `AGENTKIT_POLL_INTERVAL_SECONDS`：状态轮询间隔，默认 5 秒。
- `BYTEPLUS_AGENTKIT_REGION`（BytePlus）或 `VOLCENGINE_AGENTKIT_REGION`（火山引擎）：
  当前云平台的 AgentKit 区域，优先于通用覆盖变量 `AGENTKIT_REGION`；均未设置时，
  由 SDK 按 `BYTEPLUS_REGION` / `VOLCENGINE_REGION`、全局配置及默认区域解析。
- `BYTEPLUS_AGENTKIT_HOST` 或 `VOLCENGINE_AGENTKIT_HOST`：可选的当前云平台服务域名
  覆盖，仅填写主机名，不含 `https://`；通常无需设置。

切换云平台或区域时，请同步更换 Tool ID，并通过 `AGENTKIT_LIFECYCLE_STATE` 指定
不同的状态文件，从脚本 01 开始运行。

## 按顺序运行

默认 TTL 为 8 小时。如需缩短演示等待时间，可在运行脚本 01 **之前**设置较短的
TTL，例如：

```bash
export AGENTKIT_SESSION_TTL_SECONDS=600
```

请为步骤 01–03 留出足够时间。创建后再修改此环境变量不会改变原 Session 的到期时间，
只会影响后续创建或恢复时使用的 TTL。

在仓库根目录执行步骤 01–03，创建 Session 和快照，并查询快照：

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/01_create_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/02_create_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/03_list_and_get_snapshot.py
```

等待原 Session 的 TTL 到期，生命周期结束后，再运行步骤 04。脚本 01 输出的
`session.ExpireAt` 可用于查看到期时间（若服务返回该字段）：

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/04_restore_from_snapshot.py
```

若过早运行步骤 04，后端返回 `InvalidSnapshot.InstanceAlreadyExists`（实例仍在使用）
或 `InvalidSnapshot.InstanceTerminating`（实例正在终止）时，脚本会按轮询间隔重试，
直到允许恢复或达到等待超时。超时后可等 Session 生命周期结束再重跑步骤 04，
或增加 `AGENTKIT_WAIT_TIMEOUT_SECONDS`。其他 API 错误会直接抛出。

步骤 04 成功后，按顺序清理快照和恢复后的 Session：

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/05_delete_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/06_delete_session.py
```

| 步骤 | 脚本 | 行为 |
| --- | --- | --- |
| 01 | `01_create_session.py` | 创建 Session，记录实例 ID，并等待实例就绪。 |
| 02 | `02_create_snapshot.py` | 为该实例创建快照，记录快照 ID，并等待快照就绪。 |
| 03 | `03_list_and_get_snapshot.py` | 分页列出 Tool 下全部快照，再获取本次快照详情。 |
| 04 | `04_restore_from_snapshot.py` | 等原 Session 生命周期结束，以 `CreateNewInstance=false` 恢复，校验 `SessionId` 与步骤 01 一致，并等待实例就绪。 |
| 05 | `05_delete_snapshot.py` | 删除本次快照，并轮询列表确认其消失；恢复后的 Session 继续保留。 |
| 06 | `06_delete_session.py` | 最后删除 Session；服务端也会删除该 Session 对应的其他剩余快照。 |

步骤 05 单独演示删除快照；步骤 06 完成 Session 的最终清理。暂停和恢复运行中的
Session 请参阅相邻的 [sandbox_lifecycle](../sandbox_lifecycle/README.md) 示例。

## 状态文件

六个脚本通过 `.sandbox_snapshot_state.json` 传递 `tool_id`、逻辑会话 ID、沙箱
实例 ID 和快照 ID。默认状态文件及其临时文件已加入本目录的 `.gitignore`。
若自定义状态文件路径，请自行确保该文件不会被提交到 Git。

如果状态文件已记录步骤 05 或 06 的删除操作，步骤 04 会提示从步骤 01 开始新一轮流程。
清理后会保留本地状态文件，便于查看执行记录。

重复运行脚本 01 且不指定 `AGENTKIT_USER_SESSION_ID` 时，会生成新的逻辑会话 ID、
创建新的沙箱实例并覆盖状态文件；之前创建的实例不会被自动删除。
