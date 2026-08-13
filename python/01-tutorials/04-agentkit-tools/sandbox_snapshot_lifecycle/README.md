# 沙箱快照生命周期脚本

这六个脚本按顺序演示完整的沙箱快照生命周期。脚本使用仓库中的
`agentkit.sdk.tools` 客户端，不会保存 AK/SK。带签名的 endpoint 中如果包含
`Authorization` 查询参数，脚本会在输出或保存状态前自动脱敏。

英文说明请参阅 [README_en.md](README_en.md)。

## 环境变量

SDK 默认从 `VOLCENGINE_ACCESS_KEY` 和 `VOLCENGINE_SECRET_KEY` 读取火山引擎
凭证，也兼容旧变量名 `VOLC_ACCESSKEY` 和 `VOLC_SECRETKEY`。

必须指定沙箱 Tool ID：

```bash
export AGENTKIT_TOOL_ID=t-xxxxxxxx
```

可选配置：

- `AGENTKIT_SESSION_TTL_SECONDS`：Session 和恢复后实例的生命周期，默认
  `28800` 秒（8 小时）。
- `AGENTKIT_USER_SESSION_ID`：逻辑会话 ID；如果不指定，脚本 01 会自动生成。
- `AGENTKIT_LIFECYCLE_STATE`：六个脚本共享的状态文件路径；默认使用当前目录的
  `.sandbox_snapshot_state.json`。
- `AGENTKIT_WAIT_TIMEOUT_SECONDS`：等待资源就绪或删除完成的超时时间，默认 600 秒。
- `AGENTKIT_POLL_INTERVAL_SECONDS`：状态轮询间隔，默认 5 秒。
- `VOLCENGINE_AGENTKIT_REGION` 或 `AGENTKIT_REGION`：显式指定区域；未设置时
  使用 SDK 的默认区域解析逻辑。

## 按顺序运行

在仓库根目录依次执行：

```bash
python scripts/sandbox_snapshot_lifecycle/01_create_session.py
python scripts/sandbox_snapshot_lifecycle/02_create_snapshot.py
python scripts/sandbox_snapshot_lifecycle/03_list_and_get_snapshot.py
python scripts/sandbox_snapshot_lifecycle/04_delete_session.py
python scripts/sandbox_snapshot_lifecycle/05_restore_from_snapshot.py
python scripts/sandbox_snapshot_lifecycle/06_delete_snapshot.py
```

各脚本的作用：

1. `01_create_session.py`：创建 Session，默认生命周期为 8 小时，并等待沙箱
   实例进入 `Ready`。
2. `02_create_snapshot.py`：主动为 Session 对应的沙箱实例创建快照，并等待快照
   进入 `Ready`。
3. `03_list_and_get_snapshot.py`：分页列出 Tool 下的全部快照，并单独获取刚创建的
   快照详情。
4. `04_delete_session.py`：删除 Session 对应的沙箱实例，但保留快照。
5. `05_restore_from_snapshot.py`：以 `CreateNewInstance=false` 从快照恢复原沙箱，
   并校验恢复后的 `SessionId` 必须与脚本 01 保存的实例 ID 一致。如果实例仍处于
   异步终止状态，脚本会自动等待并重试。
6. `06_delete_snapshot.py`：删除状态文件记录的快照，分页检查 Tool 下的快照列表，
   并等待目标快照彻底消失。该脚本不会删除脚本 05 恢复出来的沙箱实例。

## 状态文件

六个脚本通过 `.sandbox_snapshot_state.json` 传递 `tool_id`、逻辑会话 ID、沙箱
实例 ID 和快照 ID。该文件已加入 `.gitignore`，不会被提交到 Git。

重复运行脚本 01 且不指定 `AGENTKIT_USER_SESSION_ID` 时，会生成新的逻辑会话 ID、
创建新的沙箱实例并覆盖状态文件；之前创建的实例不会被自动删除。
