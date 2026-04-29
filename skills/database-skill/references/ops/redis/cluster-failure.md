# 集群故障排查

## 概述

集群故障是指 Redis 集群（Cluster）中的某个节点出现问题，如主节点宕机、从节点故障、slot 分配不均，导致整个集群或部分数据不可用。

## 典型症状

- 部分 key 无法访问
- 读写操作报错
- 集群状态异常（cluster_state:fail）
- 某个主节点不可用
- MOVED / ASK 错误增多

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。
>
> ⚠️ `CLUSTER INFO` / `CLUSTER NODES` 仅在集群模式实例上可用，单机/主从实例会报错 `ERR This instance has cluster support disabled`。先确认实例是否为集群架构。

| 优先级 | 数据来源 | 命令 | 目的 |
|--------|----------|------|------|
| P0 | `execute_sql` | `CLUSTER INFO` | 查看集群状态（cluster_state / cluster_slots_ok / cluster_known_nodes） |
| P0 | `execute_sql` | `CLUSTER NODES` | 查看所有节点状态（master/slave / 连接状态 / slot 分配） |
| P1 | `execute_sql` | `INFO server` | 查看当前节点的 server 信息（uptime / 版本） |
| P1 | `execute_sql` | `INFO replication` | 查看主从复制状态（role / connected_slaves） |
| P2 | `execute_sql` | `INFO memory` | 查看节点内存使用情况 |

`database` 参数填写需要查询的 Redis DB 编号（如 `"0"`），由 Agent 根据上下文决定。

## 诊断路径

1. **检查集群状态** → `CLUSTER INFO` — cluster_state 为 fail 则集群不可用
   - cluster_slots_ok < 16384 → 有 slot 未覆盖，找到对应节点
2. **检查节点** → `CLUSTER NODES` — 找到标记为 fail/pfail 的节点
   - master 节点 fail + 有 slave → 应自动故障转移，确认 slave 是否接管
   - master 节点 fail + 无 slave → 该 slot 范围不可用，需到控制台处理
3. **检查复制** → `INFO replication` — 确认主从关系是否正常

## 关键分析维度

- **cluster_state**：`ok` 表示正常，`fail` 表示集群不可用
- **cluster_slots_ok vs cluster_slots_pfail/fail**：是否有 slot 处于故障状态
- **节点连接状态**：`CLUSTER NODES` 中各节点是否标记为 `fail` 或 `pfail`
- **slot 覆盖**：16384 个 slot 是否全部被分配且对应节点正常

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|----------|----------|------------|
| cluster_state:fail + 某节点标记 fail | 主节点宕机且无从节点可切换 | 检查该主节点是否有从节点（CLUSTER NODES 中的 slave 关系） |
| cluster_slots_pfail > 0 + 间歇性超时 | 节点疑似故障（pfail），正在投票确认 | 等待几秒后再次检查，pfail 可能转为 fail 或恢复 |
| MOVED 错误增多 + 客户端报错 | 客户端 slot 路由表过期 | 检查是否有 slot 迁移操作进行中 |
| 某些 key 范围不可访问 + 其他正常 | 特定 slot 所在节点故障 | 用 `CLUSTER NODES` 确认对应 slot 的节点状态 |
| 连接数激增 + 部分节点无响应 | 网络分区或资源耗尽 | 检查各节点的连接数和内存使用 |

## 约束与边界

- `execute_sql` 仅用于查询类操作，`CLUSTER FAILOVER`、`CLUSTER RESET` 等集群管理命令需到**火山引擎控制台**执行
- 集群拓扑变更（添加/移除节点、slot 迁移）需到火山引擎控制台操作

## 预防措施

1. 监控集群健康状态
2. 使用适当的副本数量（至少 1 个从节点）
3. 合适的网络基础设施
4. 定期备份和恢复测试
5. 监控 slot 分布均衡性
6. 设置集群状态告警

## 关联场景

- [复制延迟](replication-delay.md)
