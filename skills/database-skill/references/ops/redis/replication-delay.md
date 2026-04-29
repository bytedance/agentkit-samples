# 复制延迟故障排查

## 概述

复制延迟是指 Redis 主从复制过程中，从节点的复制进度落后于主节点，导致读写分离失效、数据不一致等问题。

## 典型症状

- 从节点延迟持续增大
- 读写分离读到的数据过期
- `INFO replication` 显示 `master_link_status:down`
- 复制相关报错

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

| 优先级 | 数据来源 | 命令 | 目的 |
|--------|----------|------|------|
| P0 | `execute_sql` | `INFO replication` | 查看复制状态（role / master_link_status / master_repl_offset / slave_repl_offset） |
| P0 | `execute_sql` | `INFO server` | 查看 server 信息（uptime_in_seconds，判断是否刚重启触发全量同步） |
| P1 | `execute_sql` | `INFO memory` | 查看内存使用（用于评估全量同步 RDB 大小） |
| P1 | `execute_sql` | `INFO clients` | 查看客户端连接数（output_buffer 可能占用大量内存影响复制） |
| P2 | `execute_sql` | `INFO stats` | 查看整体统计（expired_keys / evicted_keys 等） |

`database` 参数填写需要查询的 Redis DB 编号（如 `"0"`），由 Agent 根据上下文决定。

## 关键分析维度

- **master_link_status**：`up` 表示复制链路正常，`down` 表示断开需要重连
- **offset 差值**：`master_repl_offset` - `slave_repl_offset` 的差值越大，延迟越严重
- **repl_backlog_size**：复制积压缓冲区大小，如果延迟超过缓冲区则需要全量同步
- **connected_slaves**：主节点连接的从节点数量，确认从节点是否在线

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|----------|----------|------------|
| master_link_status:down + offset 差值大 | 主从网络断开，复制链路中断 | 检查主从节点间网络连通性 |
| offset 差值持续增大 + 写入 QPS 高 | 写入压力大，从节点回放跟不上 | 检查主节点写入速率和从节点 CPU 使用率 |
| 从节点刚重启 + 正在全量同步 | 全量同步中，RDB 传输需要时间 | 检查 `master_sync_in_progress` 和 `master_sync_left_bytes` |
| output_buffer 内存占用大 | 客户端输出缓冲区消耗大量内存，影响复制 | 检查是否有 SUBSCRIBE / MONITOR 等长连接 |
| repl_backlog 满 + 频繁全量同步 | repl_backlog_size 过小，延迟超过缓冲区导致反复全量同步 | 评估是否需要增大 repl-backlog-size |

## 约束与边界

- `execute_sql` 仅用于查询类操作，`repl-backlog-size` 等参数修改需到**火山引擎控制台 → 参数管理**
- 全量同步期间延迟是正常现象，需等待同步完成

## 预防措施

1. 确保主从网络良好
2. 保持 key 大小合理，避免大 key
3. 优化从节点上的慢命令
4. 确保从节点有足够资源
5. 监控复制延迟（offset 差值）
6. 配置足够大的 repl-backlog-size

## 关联场景

- [集群故障](cluster-failure.md)
