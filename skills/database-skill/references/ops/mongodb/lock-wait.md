# 锁等待故障排查

## 概述

锁等待是指 MongoDB 操作由于无法获取数据库/集合/元数据锁而处于等待状态（`waitingForLock: true`）。注意与 [写冲突](write-conflict.md) 区分——WriteConflict 是 WiredTiger 乐观并发控制机制，冲突方立即收到错误而非排队等待。

## 典型症状

- 查询执行变慢
- 特定操作被阻塞
- 锁等待时间增长
- `db.serverStatus()` 显示锁等待增加

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

> **注意**：MongoDB 不支持 `describe_trx_and_locks`、`describe_lock_wait`、`describe_deadlock`。锁排查主要通过 `execute_sql` 执行原生命令。

| 优先级 | 数据来源 | 命令 | 目的 |
|:---|:---|:---|:---|
| P0 | `execute_sql` | `db.serverStatus().locks` | 全局锁统计（按数据库/集合的锁获取和等待次数） |
| P0 | `execute_sql` | `$currentOp`（见下方） | 当前操作和锁状态，定位长时间持锁的操作 |
| P1 | `execute_sql` | `db.serverStatus().globalLock` | 全局锁队列（`currentQueue.readers` / `writers`） |
| P1 | `list_connections` | — | 查看活跃连接，辅助判断是否有连接堆积 |

**$currentOp 查询示例**：
```javascript
db.getSiblingDB('admin').aggregate([
    { $currentOp: { allUsers: true, idleConnections: false } },
    { $match: { waitingForLock: true } },
    { $project: { op: 1, ns: 1, secs_running: 1, locks: 1, waitingForLock: 1 } }
])
```

## 诊断路径

1. **检查全局锁队列** → `db.serverStatus().globalLock` — 看 `currentQueue.readers` / `writers`
   - 队列 > 0 → 有操作在等待锁，继续步骤 2
   - 队列 = 0 且用户描述的是写冲突 → 转 [写冲突](write-conflict.md)
2. **定位等待操作** → `$currentOp` 过滤 `waitingForLock: true` — 看哪些操作在等锁、等的是什么类型的锁
3. **定位持锁操作** → `$currentOp` 不过滤 waitingForLock，按 `secs_running` 排序 — 长时间操作通常是锁的持有者
4. **需要终止时** → `kill_process` 终止持锁操作

## 关键分析维度

- **锁等待队列**：`globalLock.currentQueue.readers` / `writers` — 队列长说明争用严重
- **锁等待操作类型**：`$currentOp` 中 `waitingForLock: true` 的操作是什么类型（find/update/insert）
- **命名空间（ns）**：锁争用集中在哪个集合
- **操作时长**：`secs_running` — 长时间运行的操作更可能是锁的根因

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| `currentQueue.writers` 长，`$currentOp` 有长时间写操作 | 大量写操作竞争 | 检查是否有批量写入或不带索引的 update |
| 锁争用集中在单个集合 | 热点集合 | 考虑拆分集合或优化写入模式 |
| `$currentOp` 显示 `createIndexes` 操作 | 前台索引构建 | 使用 `{background: true}` 后台构建 |
| 锁争用伴随 `compact` 或 `repairDatabase` | 维护操作持有全局/库级锁 | 等待完成或在低峰期执行 |
| 大量 update 缺少索引，扫描全集合 | 缺少索引导致写锁范围大 | 检查 update 的 filter 字段是否有索引 |

## 约束与边界

- MongoDB 不支持 `describe_trx_and_locks`、`describe_lock_wait`、`describe_deadlock`
- `execute_sql` 可执行 MongoDB 原生命令但有 3000 行返回限制
- MongoDB 4.0+ 使用 WiredTiger 引擎，已支持文档级锁，但某些操作仍需库级/全局锁

## ⚠️ 应急处置（需确认后执行）

### 终止阻塞操作

> **警告**：终止操作会导致当前任务失败，请在确认后执行！

```python
# 通过 kill_process 终止阻塞操作（从 list_connections 或 $currentOp 获取 process_id + node_id）
kill_process(client,
    process_ids=["<process_id>"],
    node_id="<node_id>",
    instance_id="mongo-xxx",
)
```

## 预防措施

1. 保持操作简短
2. 在低峰期构建索引（使用后台模式）
3. 为 update/delete 的 filter 字段添加索引
4. 监控锁等待时间
5. 避免前台执行维护操作
6. 考虑使用 `maxTimeMS` 限制操作执行时间

## 关联场景

- [写冲突](write-conflict.md)
- [慢查询](slow-query.md)
- [连接数打满](connection-full.md)
