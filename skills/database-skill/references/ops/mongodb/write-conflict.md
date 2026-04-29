# 写冲突（WriteConflict）故障排查

## 概述

MongoDB WiredTiger 引擎使用乐观并发控制：两个事务修改同一文档时，一方立即收到 WriteConflict 错误并需重试。与传统 [锁等待](lock-wait.md) 不同——没有排队等待状态，`waitingForLock` 和 `currentQueue` 为空属正常现象。

## 典型症状

- 写操作频繁失败或超时
- 应用日志出现 WriteConflict 错误
- 写锁获取次数异常高
- 特定集合上的写操作变慢

> 函数参数详见 [api/ops.md](../../api/ops.md) 和 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

> **注意**：MongoDB 不支持 `describe_trx_and_locks`、`describe_lock_wait`。写冲突排查主要通过 `execute_sql` 执行原生命令 + 慢查询分析。

| 优先级 | 数据来源 | 命令 | 目的 |
|:---|:---|:---|:---|
| P0 | `execute_sql` | `db.serverStatus().locks` | 写锁获取和等待次数，定位热点库 |
| P0 | `execute_sql` | `db.serverStatus().wiredTiger.concurrentTransactions` | 读写 ticket 使用情况，判断写并发是否饱和 |
| P0 | `describe_aggregate_slow_logs` | — | 慢查询中写操作是否集中在特定集合 |
| P1 | `execute_sql` | `db.serverStatus().globalLock` | 全局锁队列（写冲突场景通常为 0，用于排除传统锁等待） |
| P1 | `execute_sql` | `db.serverStatus().opcounters` | 操作计数器，高 update/delete 说明写压力大 |
| P1 | `execute_sql` | `$currentOp`（不过滤 waitingForLock） | 当前活跃写操作，看是否有多个写同一集合 |

## 诊断路径

1. **检查写锁统计** → `db.serverStatus().locks` — 看各数据库的 `acquireCount.w` 和 `acquireWaitCount.w`
   - `acquireCount.w` 高 → 写操作频繁
   - `acquireWaitCount.w` > 0 → 有写争用
   - 对比各数据库，定位热点库
2. **检查写并发饱和度** → `db.serverStatus().wiredTiger.concurrentTransactions` — 看 `write.out` 和 `write.available`
   - `write.out` 接近 `write.totalTickets` → 写并发已饱和
3. **查慢查询定位热点集合** → `describe_aggregate_slow_logs` — 看写操作（update/insert）是否集中在特定集合
   - 集中在某集合 → 热点集合写冲突
4. **查当前活跃操作** → `$currentOp`（不过滤 waitingForLock）— 看是否有多个写操作同时作用于同一集合
5. **确认写压力** → `db.serverStatus().opcounters` — 高 `update` / `delete` 计数印证写压力
6. **需要终止时** → `kill_process` 终止长时间运行的写操作

## 关键分析维度

- **写锁获取量**：`locks.<db>.acquireCount.w` — 高值说明写操作频繁
- **WiredTiger 写 ticket**：`wiredTiger.concurrentTransactions.write.out` — 接近上限说明写并发饱和
- **命名空间（ns）**：慢写操作集中在哪个集合
- **opcounters**：`update` / `delete` 计数 — 量化写压力

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| `acquireCount.w` 高 + 慢查询集中在同一集合的写操作 | 热点文档并发更新 | 检查该集合是否有高并发 update 同一文档的模式 |
| `wiredTiger.concurrentTransactions.write.out` 接近上限 | 写并发饱和 | 减少事务范围，优化写入模式 |
| 大量 update 缺少索引，扫描全集合 | 缺索引导致写操作慢，加剧冲突概率 | 检查 update 的 filter 字段是否有索引 |
| opcounters.update 极高 + 慢查询中 update 占比大 | 写入热点（如计数器、状态字段） | 考虑拆分文档或使用原子操作 |

## 约束与边界

- MongoDB 不支持 `describe_trx_and_locks`、`describe_lock_wait`、`describe_deadlock`
- WriteConflict 是瞬时的：冲突方立即收到错误，不产生持续的等待状态
- `waitingForLock` 和 `currentQueue` 为空属正常现象，不代表没有写冲突
- `execute_sql` 可执行 MongoDB 原生命令但有 3000 行返回限制

## ⚠️ 应急处置（需确认后执行）

### 终止问题操作

> **警告**：终止操作会导致当前事务失败，请在确认后执行！

```python
kill_process(client,
    process_ids=["<process_id>"],
    node_id="<node_id>",
    instance_id="mongo-xxx",
)
```

## 预防措施

1. 避免高并发更新同一文档（拆分热点文档）
2. 缩短事务范围，减少冲突窗口
3. 为 update/delete 的 filter 字段添加索引
4. 应用层实现 WriteConflict 重试机制
5. 考虑使用 `maxTimeMS` 限制操作执行时间

## 关联场景

- [锁等待](lock-wait.md)
- [慢查询](slow-query.md)
- [连接数打满](connection-full.md)
