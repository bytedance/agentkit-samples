# 锁等待 / 死锁故障排查

## 概述

锁等待是指事务由于无法获取所需的锁而处于等待状态，可能是由于行锁等待、表锁等待或元数据锁等待导致。

**PG 死锁说明**：PostgreSQL 内置死锁检测器（由 `deadlock_timeout` 控制，默认 1s），会自动终止其中一个事务。因此 PG 死锁排查重点不是"检测死锁"，而是**分析死锁为什么反复发生**以及如何预防。死锁信息通过错误日志获取，不通过 `describe_deadlock`（PG 不支持）。

**诊断原则：被阻塞的 SQL 是受害者，不是根因。** 排查锁等待时，优先找到持锁事务（blocker），而不是分析被阻塞的 SQL 本身。

## 典型症状

- 查询执行变慢
- 特定操作被阻塞
- 锁等待时间增长
- `pg_stat_activity` 显示很多进程在等待

> 函数参数详见 [api/ops.md](../../api/ops.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|:---|:---|:---|:---|
| P0 | `describe_trx_and_locks` | `lock_status="LockHold"` | 定位持锁事务，关注 `trx_exec_time`、`lock_summary` |
| P0 | `describe_lock_wait` | — | 查看完整锁等待关系（阻塞方 b_ 和等待方 r_） |
| P1 | `list_connections` | — | 查看活跃会话全貌，识别 `idle in transaction` 状态 |
| P1 | `describe_err_logs` | `keyword="deadlock"` | **死锁场景必看**：PG 死锁信息记录在错误日志中 |
| P2 | `describe_aggregate_slow_logs` | 最近 1h | 持锁事务是否包含慢 SQL |
| 备选 | `execute_sql` | 见下方 fallback SQL | API 数据不足时，直接查 PG 系统视图 |

## 诊断路径

### 锁等待排查

1. **定位 blocker** → `describe_trx_and_locks(LockHold)` — 被阻塞的 SQL 是受害者，不要分析它
2. **分析阻塞链** → `describe_lock_wait` — 用 `b_trx_id` / `r_trx_id` 理解谁阻塞了谁
   - 如果 blocker 状态是 `idle in transaction` → 事务未提交，检查应用自动提交配置
   - 如果锁类型是 AccessExclusiveLock → DDL 操作，不是行锁问题
   - 如果无结果但步骤 1 找到了长持锁事务 → 等待方已超时或重试成功，但阻塞风险仍在，将该事务作为根因分析
   - 如果步骤 1 和 2 均无结果 → 锁已完全释放，转查 `describe_aggregate_slow_logs` 看历史
   - **如果 API 返回数据不足** → 用 fallback SQL 直接查 PG 系统视图（见下方）
3. **确认锁等待影响** → `list_connections` — 看是否有等待状态的会话，或大量相同 SQL 在排队
   - 即使当前无等待会话，步骤 1 找到的长持锁事务仍是潜在阻塞源
4. **需要终止时** → blocker 的 `process_id` + `node_id` 传给 `kill_process`（需用户确认）

### 死锁排查（PG 特有流程）

PG 死锁由引擎自动检测和处理（`deadlock_timeout` 默认 1s），排查重点是**分析原因和预防**：

1. **查错误日志** → `describe_err_logs(keyword="deadlock")` — 获取死锁发生时间、涉及的 SQL、被终止的事务
2. **分析死锁 SQL** → 从错误日志中提取涉及的 SQL，分析它们的访问顺序和锁竞争模式
3. **检查当前锁状态** → `describe_trx_and_locks(LockHold)` — 确认是否仍有长事务持锁（可能是死锁的诱因）
4. **评估频率** → 偶发死锁可忽略（应用重试即可），频繁死锁需优化事务顺序和索引

### Fallback SQL（API 数据不足时使用）

当 `describe_trx_and_locks` 或 `describe_lock_wait` 返回的数据不足以定位问题时，用 `execute_sql` 直接查 PG 系统视图：

```sql
-- 查看当前锁等待关系（blocker → waiter）
SELECT
  blocked.pid AS waiter_pid,
  blocked.query AS waiter_query,
  blocking.pid AS blocker_pid,
  blocking.query AS blocker_query,
  blocking.state AS blocker_state,
  blocking.xact_start AS blocker_xact_start
FROM pg_stat_activity blocked
JOIN pg_locks bl ON bl.pid = blocked.pid AND NOT bl.granted
JOIN pg_locks gl ON gl.locktype = bl.locktype
  AND gl.database IS NOT DISTINCT FROM bl.database
  AND gl.relation IS NOT DISTINCT FROM bl.relation
  AND gl.page IS NOT DISTINCT FROM bl.page
  AND gl.tuple IS NOT DISTINCT FROM bl.tuple
  AND gl.pid != bl.pid AND gl.granted
JOIN pg_stat_activity blocking ON blocking.pid = gl.pid
WHERE blocked.state = 'active'
ORDER BY blocked.query_start;
```

```sql
-- 查看所有锁及持有者状态
SELECT l.pid, l.locktype, l.mode, l.granted, a.state, a.query, a.xact_start
FROM pg_locks l
JOIN pg_stat_activity a ON a.pid = l.pid
WHERE l.locktype = 'relation'
ORDER BY l.granted, a.xact_start;
```

## 关键分析维度

- **阻塞链**：`b_trx_id` → `r_trx_id` 的对应关系，有多少事务在等同一个锁
- **持锁时长**：`trx_exec_time` 和 `b_blocking_wait_secs`
- **事务状态**：特别关注 `idle in transaction` 状态 — 事务已打开但未提交，可能长时间持锁
- **锁类型**：行锁（RowExclusiveLock）、表锁（AccessExclusiveLock）、Advisory Lock

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| 事务状态为 `idle in transaction`，持锁时间长 | 应用未及时 commit/rollback | 检查应用连接池的自动提交配置 |
| 锁类型为 AccessExclusiveLock，被阻塞 SQL 是 SELECT | DDL 操作（ALTER TABLE）持有排他锁 | 检查是否有 DDL 在执行 |
| 持锁 SQL 扫描大量行 | 缺少索引导致锁范围大 | `execute_sql("EXPLAIN <sql>")` 检查索引 |
| 多个事务互相等待 | 死锁 | PG 自动检测并终止一方；`describe_err_logs(keyword="deadlock")` 查死锁详情和频率 |
| 错误日志中频繁出现 deadlock detected | 应用事务顺序不一致 | 分析死锁 SQL 的表访问顺序，统一事务中的操作顺序 |
| 死锁涉及索引操作，并发 INSERT 密集 | 索引页分裂锁冲突 | 检查是否大量并发 INSERT 同一索引范围，考虑 FILLFACTOR 调优 |
| VACUUM 被阻塞或阻塞其他事务 | VACUUM 与 DML 冲突 | 转到「VACUUM 阻塞」SOP |

## 约束与边界

- PostgreSQL **不支持** `describe_deadlock` — 死锁信息通过 `describe_err_logs(keyword="deadlock")` 获取
- `describe_trx_and_locks` 和 `describe_lock_wait` 是实时触发分析，如果返回数据不足，使用上方 fallback SQL
- `execute_sql` 仅支持只读操作
- **kill_process**：必须经过用户明确确认后才能执行

## ⚠️ 应急处置（需确认后执行）

### 终止阻塞事务

> **警告**：终止进程会导致当前事务失败，请在确认后执行！

```python
# 终止阻塞进程（从排查步骤获取 blocking_pid）
kill_process(client,
    process_ids=["12345"],
    node_id="node-1",
    instance_id="pg-xxx",
)
```

## 预防措施

1. 保持事务简短
2. 按一致顺序访问数据
3. 添加适当索引
4. 避免在高峰期进行长时间 DDL
5. 监控锁等待时间
6. 使用适当的锁模式
7. 配置 `idle_in_transaction_session_timeout` 自动终止空闲事务
8. 配置 `deadlock_timeout`（默认 1s，高并发场景可适当调大以减少死锁检测开销）

## 关联场景

- [慢查询](slow-query.md) — 持锁事务可能包含慢 SQL
- [VACUUM 阻塞](vacuum-blocking.md) — VACUUM 和 DML 的锁冲突
