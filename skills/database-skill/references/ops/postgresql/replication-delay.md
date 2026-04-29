# 复制延迟故障排查

## 概述

复制延迟是指 PostgreSQL 主从复制过程中，从库的复制进度落后于主库，导致读写分离失效、数据不一致等问题。

## 典型症状

- 从库延迟持续增大
- 读写分离读到的数据过期
- `pg_stat_replication` 显示延迟
- 复制相关报错

> 函数参数详见 [api/ops.md](../../api/ops.md) 和 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|:---|:---|:---|:---|
| P0 | `execute_sql` | `sql="SELECT ... FROM pg_stat_replication;"` | 查看复制状态（write_lag、flush_lag、replay_lag、sync_state） |
| P0 | `execute_sql` | `sql="SELECT ... FROM pg_replication_slots;"` | 查看复制槽（是否 active、restart_lsn 距当前 LSN 的差距） |
| P1 | `list_connections` | — | 查看活跃会话，识别从库上的长事务或慢查询 |
| P1 | `describe_slow_logs` | `order_by="QueryTime"` | 从库慢查询是否阻塞 WAL 回放 |
| P2 | `describe_health_summary` | — | 整体健康概览 |

## 诊断路径

1. **查复制状态** → `execute_sql("SELECT ... FROM pg_stat_replication")` — 区分延迟发生在哪个环节
   - write_lag 大 → 网络传输瓶颈
   - replay_lag 大但 write/flush 正常 → 从库回放慢
2. **查复制槽** → `execute_sql("SELECT ... FROM pg_replication_slots")` — 非活跃槽阻止 WAL 回收
   - active=false + restart_lsn 远落后 → 考虑删除（需到控制台操作）
3. **从库原因分析** → `list_connections` + `describe_slow_logs` — 从库长事务或慢查询阻塞回放
   - 有 `idle in transaction` 长事务 → 终止它以恢复回放

## 关键分析维度

- **延迟类型**：write_lag（写入延迟）vs flush_lag（落盘延迟）vs replay_lag（回放延迟）— 定位瓶颈环节
- **复制槽状态**：非活跃的复制槽会阻止 WAL 回收，导致 WAL 积压
- **从库负载**：从库是否有长时间运行的查询阻塞了 WAL 回放
- **同步模式**：sync_state 是 async / sync / quorum — 同步复制对网络延迟更敏感

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| replay_lag 大 + write_lag/flush_lag 小 | 从库回放慢（CPU/IO 瓶颈或慢查询阻塞） | 检查从库活跃会话和慢查询 |
| write_lag 大 + 网络流量异常 | 网络延迟导致 WAL 传输慢 | 检查主从网络连通性 |
| 复制槽 active=false + restart_lsn 远落后 | 非活跃复制槽阻止 WAL 回收 | 确认该槽是否还需要，考虑删除 |
| 从库有 `idle in transaction` 长事务 | 长事务阻止 HOT cleanup 和 WAL 回放 | `list_connections` 找到并终止长事务 |
| sync_state=sync + 延迟随网络波动 | 同步复制受网络影响 | 考虑改为异步复制或优化网络 |

## 约束与边界

- PostgreSQL 不支持 `get_metric_data` / `get_metric_items`，需通过系统视图查询
- `execute_sql` 仅支持只读操作
- 复制槽管理（创建/删除）需到**火山引擎控制台**操作
- **kill_process**：必须经过用户明确确认后才能执行

## ⚠️ 应急处置（需确认后执行）

### 终止从库长查询

> **警告**：终止进程会导致当前事务失败，请在确认后执行！

```python
kill_process(client,
    process_ids=["12345"],
    node_id="node-1",
    instance_id="pg-xxx",
)
```

## 预防措施

1. 使用流复制
2. 保持事务简短
3. 优化从库慢查询
4. 确保从库有足够资源
5. 监控复制延迟
6. 对关键数据使用同步复制
7. 定期清理不再使用的复制槽

## 关联场景

- [WAL 积压](wal-backlog.md)
