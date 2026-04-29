# VACUUM 阻塞故障排查

## 概述

VACUUM 阻塞是指 VACUUM 或 ANALYZE 操作在执行过程中被阻塞，或者阻塞了其他操作。VACUUM 用于回收死元组占用的空间。

## 典型症状

- VACUUM 操作执行时间长
- 表被锁定，无法进行 DML 操作
- `pg_stat_progress_vacuum` 显示进度缓慢
- 磁盘空间未回收（死元组持续增长）

> 函数参数详见 [api/ops.md](../../api/ops.md) 和 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|:---|:---|:---|:---|
| P0 | `execute_sql` | `sql="SELECT ... FROM pg_stat_progress_vacuum;"` | 查看运行中的 VACUUM 进度（phase、heap_blks_total/scanned） |
| P0 | `execute_sql` | `sql="SELECT ... FROM pg_stat_user_tables WHERE n_dead_tup > 10000;"` | 查看表膨胀情况（死元组数量、last_vacuum、last_autovacuum） |
| P1 | `list_connections` | — | 查看活跃会话，识别阻塞 VACUUM 的长事务 |
| P1 | `describe_trx_and_locks` | `lock_status="LockHold"` | 查看锁持有情况，判断 VACUUM 与 DML 的冲突 |
| P2 | `describe_table_space` | — | 表空间使用情况，确认是否有膨胀严重的表 |

## 诊断路径

1. **检查 VACUUM 进度** → `execute_sql("SELECT ... FROM pg_stat_progress_vacuum")` — 确认是否有 VACUUM 在运行
   - 有且进度缓慢 → 大表正常现象，或被其他事务阻塞
   - 没有 VACUUM 运行 → autovacuum 可能未触发，检查配置
2. **检查膨胀** → `execute_sql("SELECT ... FROM pg_stat_user_tables WHERE n_dead_tup > 10000")` — 确认哪些表需要 VACUUM
3. **查阻塞源** → `list_connections` + `describe_trx_and_locks(LockHold)` — 找 `idle in transaction` 长事务
   - 有 `idle in transaction` 且 xmin 很旧 → 这个事务阻止了 VACUUM 回收死元组，考虑终止它
4. **需要终止时** → 长事务的 `process_id` + `node_id` 传给 `kill_process`（需用户确认）

## 关键分析维度

- **VACUUM 进度**：`heap_blks_scanned / heap_blks_total` — 进度比例和速度
- **死元组趋势**：`n_dead_tup` 大且 `last_autovacuum` 为空或很久之前 — 说明 autovacuum 未运行
- **阻塞关系**：是 VACUUM 被其他事务阻塞，还是 VACUUM 阻塞了其他操作
- **长事务影响**：`idle in transaction` 状态的旧事务会阻止 VACUUM 回收比该事务更新的死元组

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| n_dead_tup 很大 + last_autovacuum 为 NULL | autovacuum 未触发或被关闭 | 检查 `autovacuum` 参数是否为 on |
| VACUUM 进度缓慢 + 表数据量巨大 | 大表 VACUUM 耗时长 | 正常现象，但可在低峰期安排 |
| VACUUM 被阻塞 + 有长事务持有 AccessShareLock | 长事务阻止 VACUUM（VACUUM FULL 需要 AccessExclusiveLock） | 终止长事务或等待其完成 |
| 多个会话等待 AccessExclusiveLock | VACUUM FULL 阻塞了 DML 操作 | 考虑改用普通 VACUUM（不阻塞 DML） |
| 死元组持续增长 + 有 `idle in transaction` 会话 | 旧事务 snapshot 阻止 VACUUM 回收 | 终止空闲事务，配置 `idle_in_transaction_session_timeout` |

## 约束与边界

- PostgreSQL 不支持 `get_metric_data` / `get_metric_items`
- `execute_sql` 仅支持只读操作
- `VACUUM (VERBOSE, ANALYZE)` 需要有表的写权限，普通 VACUUM 不阻塞 DML，VACUUM FULL 会阻塞
- **kill_process**：必须经过用户明确确认后才能执行

## ⚠️ 应急处置（需确认后执行）

### 取消 VACUUM

> **警告**：取消 VACUUM 可能导致空间无法回收，请在确认后执行！

```python
# 终止 VACUUM 进程
kill_process(client,
    process_ids=["12345"],
    node_id="node-1",
    instance_id="pg-xxx",
)
```

### 手动运行 VACUUM

> **警告**：VACUUM FULL 会锁定表阻塞读写，普通 VACUUM 不阻塞。优先使用普通 VACUUM。需通过**变更工单**（`create_ddl_sql_change_ticket`）或到**火山引擎控制台**执行。

## 预防措施

1. 启用并调优 autovacuum
2. 保持事务简短（避免长时间 `idle in transaction`）
3. 监控表膨胀（n_dead_tup）
4. 在低峰期安排 VACUUM FULL
5. 谨慎使用 VACUUM FULL（优先用普通 VACUUM）
6. 配置 `idle_in_transaction_session_timeout` 自动终止空闲事务

## 关联场景

- [锁等待](lock-wait.md)
- [磁盘空间不足](disk-full.md)
