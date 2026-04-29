# WAL 积压故障排查

## 概述

WAL 积压是指 Write-Ahead Logging (WAL) 写入速度跟不上产生速度，导致 WAL 目录空间增长、复制延迟等问题。

## 典型症状

- WAL 目录空间持续增长
- 复制延迟增大
- Checkpoint 耗时增加
- 写入性能下降

> 函数参数详见 [api/ops.md](../../api/ops.md) 和 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|:---|:---|:---|:---|
| P0 | `execute_sql` | `sql="SELECT pg_current_wal_lsn(), pg_walfile_name(...), pg_wal_lsn_diff(...);"` | 查看当前 WAL 位置和累积量 |
| P0 | `execute_sql` | `sql="SELECT ... FROM pg_replication_slots;"` | 查看复制槽（非活跃槽会阻止 WAL 回收） |
| P1 | `execute_sql` | `sql="SELECT ... FROM pg_stat_replication;"` | 查看复制状态，确认从库是否消费 WAL 正常 |
| P1 | `execute_sql` | `sql="SELECT ... FROM pg_stat_bgwriter;"` | Checkpoint 和后台写入统计（buffers_checkpoint、buffers_backend） |
| P2 | `describe_table_space` | — | 磁盘空间使用情况，确认 WAL 占用占比 |

## 诊断路径

1. **检查 WAL 位置** → `execute_sql("SELECT pg_current_wal_lsn(), ...")` — 确认 WAL 累积量
2. **检查复制槽** → `execute_sql("SELECT ... FROM pg_replication_slots")` — 非活跃槽是 WAL 无法回收的最常见原因
   - active=false 且 restart_lsn 远落后 → 考虑删除该槽（需到控制台操作）
3. **检查复制状态** → `execute_sql("SELECT ... FROM pg_stat_replication")` — 从库是否正常消费 WAL
   - replay_lag 大 → 从库回放慢，转到[复制延迟](replication-delay.md)排查
4. **检查空间** → `describe_table_space` — 确认 WAL 占比，判断是否需要紧急清理

## 关键分析维度

- **WAL 增长速度**：通过多次查询 `pg_current_wal_lsn()` 的差值估算 WAL 产生速率
- **复制槽阻塞**：非活跃复制槽（active=false）的 restart_lsn 远落后于当前 LSN — 这是 WAL 无法回收的最常见原因
- **Checkpoint 效率**：`buffers_backend` 高说明后台写入来不及，数据页绕过 Checkpoint 直接写
- **归档状态**：WAL 归档是否正常运行，失败的归档会阻止 WAL 文件清理

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| 复制槽 active=false + restart_lsn 远落后 | 非活跃复制槽阻止 WAL 回收 | 确认该槽是否还需要，考虑删除 |
| WAL 快速增长 + 大量 DML 操作 | 高写入负载产生大量 WAL | 检查是否有批量写入任务在运行 |
| buffers_backend 高 + Checkpoint 间隔长 | Checkpoint 间隔过长，WAL 积累过多 | 检查 `checkpoint_timeout` 和 `max_wal_size` 配置 |
| 从库 replay_lag 大 + WAL 堆积 | 从库回放慢导致 WAL 无法清理 | 转到[复制延迟](replication-delay.md)排查 |
| WAL 归档失败 + pg_wal 目录膨胀 | 归档进程失败，WAL 文件无法清理 | 检查归档日志和归档目标存储 |

## 约束与边界

- PostgreSQL 不支持 `get_metric_data` / `get_metric_items`，需通过系统视图查询
- `execute_sql` 仅支持只读操作
- 复制槽管理（创建/删除）、Checkpoint 参数调整需到**火山引擎控制台**操作
- **kill_process**：必须经过用户明确确认后才能执行

## ⚠️ 应急处置（需确认后执行）

### 强制 Checkpoint

> **警告**：`CHECKPOINT` 需要 superuser 权限，火山引擎托管实例通常无此权限，需到**控制台**手动触发或联系支持。
### 终止长时间运行的事务

> **警告**：终止进程会导致当前事务失败，请在确认后执行！

```python
kill_process(client,
    process_ids=["12345"],
    node_id="node-1",
    instance_id="pg-xxx",
)
```

## 预防措施

1. 调优 checkpoint 参数（`checkpoint_timeout`、`max_wal_size`）
2. 使用适当的 `wal_level`
3. 确保归档正常工作
4. 监控 WAL 增长
5. 定期清理不再使用的复制槽
6. 监控磁盘 IO 性能

## 关联场景

- [磁盘空间不足](disk-full.md)
- [复制延迟](replication-delay.md)
