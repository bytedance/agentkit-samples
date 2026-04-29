# 死锁故障排查

## 概述

死锁是指两个或多个事务相互持有对方需要的锁，导致所有事务都无法继续执行。MySQL 会自动检测并回滚其中一个事务，但会造成业务报错。

## 典型症状

- 应用报错: `Deadlock found when trying to get lock`
- 事务回滚
- 特定业务操作失败
- 死锁错误日志

> 函数参数详见 [api/ops.md](../../api/ops.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|:---|:---|:---|:---|
| P0 | `describe_deadlock` | — | 实时触发死锁分析。**仅能检测当前正在发生的死锁**，已被引擎处理的死锁不会出现 |
| P0 | `describe_trx_and_locks` | `lock_status="LockHold"` | 查看当前持锁事务，确认是否仍有异常事务 |
| P1 | `describe_lock_wait` | — | 查看完整锁等待关系（阻塞方 b_ 和等待方 r_） |
| P1 | `list_connections` | — | 查看当前活跃会话，定位长事务 |
| P2 | `describe_err_logs` | `keyword="Deadlock"` | 查看错误日志。注意：MySQL 默认不记录死锁到错误日志（需 `innodb_print_all_deadlocks=ON`），该参数未开启时此查询返回空 |

## 诊断路径

1. **获取死锁详情** → `describe_deadlock` — 查看等待链、涉及 SQL、锁类型
   - 如果有结果 → 分析等待链和涉及 SQL
   - **如果返回空** → 死锁已被 MySQL 引擎自动处理（InnoDB 秒级检测并回滚），无法回溯历史死锁链。继续下一步
2. **检查当前锁状态** → `describe_trx_and_locks(LockHold)` — 确认是否仍有异常长事务持锁
   - 如果有长事务 → 可能是死锁的诱因（长事务更容易卷入死锁）
   - 如果无异常 → 聚焦预防
3. **查慢查询** → `describe_aggregate_slow_logs` — 死锁涉及的 SQL 通常也是慢查询，通过慢查询聚合找到高频问题 SQL 模板
4. **评估频率** → `describe_err_logs(keyword="Deadlock")` — 注意：需实例开启 `innodb_print_all_deadlocks=ON` 才能在错误日志中看到死锁记录；未开启时此查询返回空，建议在控制台参数管理中开启

## 关键分析维度

- **死锁等待链**：哪两个事务互相持锁？它们的 SQL 分别是什么？
- **锁类型**：行锁（Record Lock）、间隙锁（Gap Lock）、还是 Next-Key Lock？间隙锁死锁通常与索引范围有关
- **涉及表和索引**：死锁发生在哪些表的哪些索引上？
- **事务执行时长**：长事务更容易卷入死锁
- **频率**：偶发死锁可以容忍（应用重试即可），频繁死锁需要优化

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| 两个事务以不同顺序更新相同的行 | 乱序访问 | 检查 SQL 的 WHERE 条件和事务中的操作顺序 |
| 间隙锁（Gap Lock）互相阻塞，涉及范围查询 | 间隙锁冲突 | 检查是否使用 RR 隔离级别，考虑降为 RC |
| 死锁事务的 `trx_exec_time` 很长 | 长事务持锁 | 转到「慢查询排查」确认事务中是否有慢 SQL |
| 大量并发 INSERT/UPDATE 同一索引范围 | 热点行竞争 | 检查是否可以分散写入（如随机 ID 代替自增） |
| 死锁 SQL 缺少索引，锁定了大量行 | 缺少索引导致锁范围扩大 | `execute_sql("EXPLAIN <sql>")` 检查扫描范围 |
| 死锁频繁发生在同一对 SQL | 应用逻辑问题 | 检查应用代码中的事务操作顺序 |

## 约束与边界

- `describe_deadlock` 是实时触发分析，**仅能检测当前正在发生的死锁**。MySQL 死锁由 InnoDB 秒级检测并自动回滚，因此绝大多数情况下调用时死锁已消失，返回空是正常的
- MySQL 默认不将死锁记录到错误日志，需在控制台参数管理中开启 `innodb_print_all_deadlocks=ON` 后 `describe_err_logs` 才能查到历史死锁
- `SHOW ENGINE INNODB STATUS` 不被 `execute_sql` 支持（SQL parser 限制）
- `execute_sql` 仅支持只读操作，无法执行 `SET GLOBAL`。隔离级别调整需到**火山引擎控制台 → 参数管理**修改 `transaction_isolation`
- VeDB 支持 `describe_deadlock`，但可能需要指定 `node_id`（通过 `describe_instance_nodes` 获取）

## ⚠️ 应急处置（需确认后执行）

### 终止阻塞事务

> **警告**：终止事务会导致当前事务失败，请在确认后执行！

```python
# 终止指定事务
kill_process(client,
    process_ids=["12345"],
    node_id="node-1",
    instance_id="mysql-xxx",
)
```

### 调整事务隔离级别

> `execute_sql` 仅支持只读操作，无法执行 `SET GLOBAL`。如需将隔离级别改为 `READ-COMMITTED`，需到**火山引擎控制台 → 参数管理**修改 `transaction_isolation`。

## 预防措施

1. 按一致顺序访问表
2. 保持事务简短
3. 添加适当索引以缩小锁范围
4. 适当情况下使用较低隔离级别
5. 避免在高峰期进行批量更新
6. 监控死锁日志并优化问题查询

## 关联场景

- [锁等待](lock-wait.md)
- [慢查询](slow-query.md)
