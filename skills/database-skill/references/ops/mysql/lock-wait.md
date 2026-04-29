# 锁等待故障排查

## 概述

锁等待是指事务由于无法获取所需的锁而处于等待状态，可能是由于行锁等待、表锁等待或元数据锁等待导致。

**诊断原则：被阻塞的 SQL 是受害者，不是根因。** 排查锁等待时，优先找到持锁事务（blocker），而不是分析被阻塞的 SQL 本身。

## 典型症状

- 查询执行变慢
- 特定操作被阻塞
- 锁等待时间增长
- `SHOW PROCESSLIST` 显示很多 State 为 "Waiting for ..."

> 函数参数详见 [api/ops.md](../../api/ops.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|:---|:---|:---|:---|
| P0 | `describe_trx_and_locks` | `lock_status="LockHold"` | 定位持锁事务（blocker），关注 `trx_exec_time`、`trx_rows_locked`、`lock_summary` |
| P0 | `describe_lock_wait` | — | 查看完整锁等待关系：阻塞方（b_）和等待方（r_），关注 `b_blocking_wait_secs` |
| P1 | `list_connections` | — | 查看活跃会话全貌，识别长事务和异常状态 |
| P1 | `describe_deadlock` | — | 排除是否同时存在死锁 |
| P2 | `describe_aggregate_slow_logs` | 最近 1h | 持锁事务是否包含慢 SQL |

## 诊断路径

1. **定位 blocker** → `describe_trx_and_locks(LockHold)` — 被阻塞的 SQL 是受害者，不要分析它
2. **分析阻塞链** → `describe_lock_wait` — 用 `b_trx_id` / `r_trx_id` 理解谁阻塞了谁
   - 如果锁类型是元数据锁（MDL）→ 找 DDL 操作，不是行锁问题
   - 如果无结果但步骤 1 找到了长持锁事务（`trx_exec_time` 长 + 持有 X 锁）→ 说明等待方已超时或重试成功，但阻塞风险仍然存在，应将该事务作为根因分析
   - 如果步骤 1 和 2 均无结果 → 锁已完全释放，转查 `describe_aggregate_slow_logs` 看历史慢查询中的 `lock_time`
3. **确认锁等待影响** → `list_connections` — 看是否有 State 为 `Waiting` 的会话，或大量相同 SQL 在排队
   - 即使当前无 Waiting 会话，步骤 1 找到的长持锁事务仍是潜在阻塞源
4. **需要终止时** → blocker 的 `process_id` + `node_id` 传给 `kill_process`（需用户确认）

## 关键分析维度

- **阻塞链**：谁阻塞了谁？`b_trx_id`（阻塞方）→ `r_trx_id`（等待方）的对应关系
- **持锁时长**：`trx_exec_time` 和 `b_blocking_wait_secs` — 长时间持锁说明事务有问题
- **锁类型和范围**：`lock_summary` 中的锁类型分布（行锁/表锁/元数据锁）
- **持锁 SQL**：`sql_blocked` 字段 — 持锁事务正在执行什么 SQL
- **影响范围**：有多少事务在等同一个锁？是单点阻塞还是链式阻塞

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| 单个事务 `trx_exec_time` 很长，阻塞多个等待方 | 长事务未提交 | 检查应用代码是否有未及时 commit 的事务 |
| 锁类型为元数据锁（MDL），被阻塞 SQL 是 SELECT | DDL 操作持有 MDL | 检查是否有 ALTER TABLE 等 DDL 在执行 |
| 多个事务互相等待 | 死锁（但未被检测到） | 查 `describe_deadlock` |
| 持锁 SQL 扫描大量行（`trx_rows_locked` 高） | 缺少索引导致锁范围大 | `execute_sql("EXPLAIN <sql>")` 检查索引使用 |
| 批量 UPDATE/DELETE 持锁，等待方也在同范围操作 | 热点范围竞争 | 拆分批量操作为小批次 |
| 锁等待周期性出现，与定时任务时间吻合 | 定时批处理任务冲突 | 检查 cron job / 批处理调度 |

## 约束与边界

- `describe_trx_and_locks` 和 `describe_lock_wait` 是实时触发分析，返回的是当前时刻的锁状态
- `lock_list` 超过 5 条时自动裁剪：保留前 5 条 + `lock_summary`（按类型/模式/状态聚合计数）
- `execute_sql` 仅支持只读操作，隔离级别调整需到**火山引擎控制台 → 参数管理**修改
- **kill_process**：必须经过用户明确确认后才能执行

## ⚠️ 应急处置（需确认后执行）

### 终止阻塞事务

> **警告**：终止事务会导致当前事务失败，请在确认后执行！

```python
# 终止阻塞进程（从 describe_trx_and_locks 获取 process_id 和 node_id）
kill_process(client,
    process_ids=["12345"],
    node_id="node-1",
    instance_id="mysql-xxx",
)
```

### 调整事务隔离级别

> `execute_sql` 仅支持只读操作，无法执行 `SET GLOBAL`。如需将隔离级别改为 `READ-COMMITTED`，需到**火山引擎控制台 → 参数管理**修改 `transaction_isolation`。

## 预防措施

1. 保持事务简短
2. 按一致顺序访问数据
3. 添加适当索引
4. 避免在高峰期进行长时间 DDL
5. 监控锁等待时间
6. 使用适当的隔离级别

## 关联场景

- [死锁](deadlock.md)
- [慢查询](slow-query.md)
- [会话堆积](session-pileup.md)
