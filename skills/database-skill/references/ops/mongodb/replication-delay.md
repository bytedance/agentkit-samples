# 复制延迟故障排查

## 概述

复制延迟是指 MongoDB 副本集（Replica Set）中从节点的复制进度落后于主节点，导致读写分离失效、数据不一致等问题。

## 典型症状

- 从节点延迟持续增大
- 读写分离读到的数据过期
- `rs.status()` 中 `optimeDate` 差距大
- 复制相关报错

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

| 优先级 | 数据来源 | 命令 | 目的 |
|--------|----------|------|------|
| P0 | `execute_sql` | `rs.status();` | 查看副本集状态（各成员 stateStr / optimeDate / lastHeartbeat） |
| P0 | `execute_sql` | `db.getReplicationInfo();` | 查看 oplog 大小和时间窗口（logSizeMB / usedMB / timeDiff） |
| P1 | `execute_sql` | `db.serverStatus().opcounters;` | 查看读写操作计数（判断写入压力） |
| P2 | `execute_sql` | `db.currentOp({secs_running: {$gt: 10}});` | 查看长时间运行操作 |

所有命令的 `database` 参数使用 `"admin"`。

## 诊断路径

1. **查复制状态** → `execute_sql("rs.status()")` — 对比 PRIMARY 和 SECONDARY 的 `optimeDate` 差值
   - 某个 SECONDARY 延迟大但其他正常 → 该节点资源不足或网络问题
   - 所有 SECONDARY 延迟大 → 主节点写入压力大
2. **检查 oplog** → `execute_sql("db.getReplicationInfo()")` — 确认 oplog 时间窗口（timeDiff 秒）
   - 延迟超过 oplog 窗口 → 从节点需要全量同步，紧急扩大 oplog
3. **检查写入压力** → `execute_sql("db.serverStatus().opcounters")` — 写操作速率是否异常

## 关键分析维度

- **复制延迟大小**：`rs.status()` 中 PRIMARY 和 SECONDARY 的 `optimeDate` 差值，秒级延迟通常可接受，分钟级需关注
- **oplog 时间窗口**：oplog 覆盖的时间范围，如果延迟超过 oplog 窗口则从节点需要全量同步
- **写入压力**：`opcounters` 中 insert/update/delete 的速率，高写入是复制延迟的常见原因
- **从节点负载**：从节点是否承担了大量读查询或后台任务

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|----------|----------|------------|
| 延迟持续增大 + 写入 QPS 高 | 写入压力大，从节点回放跟不上 | 检查 `opcounters` 中写操作速率 |
| 延迟突然增大 + 有大批量操作 | 大批量写入导致 oplog 堆积 | 检查是否有 bulk insert / update 操作 |
| 从节点延迟 + 从节点 CPU/IO 高 | 从节点资源不足 | 检查从节点的系统资源使用情况 |
| oplog 时间窗口很短 + 延迟大 | oplog 太小，从节点可能需要全量同步 | 检查 oplog 大小配置是否合理 |
| 延迟波动 + lastHeartbeat 间隔大 | 网络延迟或不稳定 | 检查主从节点间网络延迟 |

## 约束与边界

- `execute_sql` 仅用于查询类操作，无法调整 oplog 大小或修改副本集配置
- oplog 大小调整和副本集配置变更需到火山引擎控制台操作

## 预防措施

1. 使用适当的 oplog 大小
2. 保持写入操作简短，避免大批量操作
3. 优化从节点上的查询
4. 确保从节点有足够资源
5. 监控复制延迟
6. 使用合适的网络基础设施

## 关联场景

- [慢查询](slow-query.md)
