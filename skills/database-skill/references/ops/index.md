---
name: "database-skill-ops"
description: "数据库运维 SOP：基于标准化流程（SOP）进行数据库故障排查，涵盖资源基线确认、负载分析、会话分析、慢查询定位、空间分析及变更追溯。"
---

# 数据库故障排查 SOP

> 🔴 **本文件是路由中枢。** 根据 db_type + 症状匹配场景后，**必须同时阅读两个文件**：
> 1. 对应的 **SOP 文件**（场景知识卡片：必看数据、诊断路径、根因判断知识）
> 2. **[api/ops.md](../api/ops.md)**（函数完整参数、过滤条件、翻页方式、返回格式）
>
> SOP 中的函数调用是简化示例，不含全部参数。**不读 API 参考直接调用函数会导致参数缺失或用法错误。** 排查中途需要换方向时，回到本文件重新匹配。

---

## 诊断原理

以下原理适用于所有场景。SOP 知识卡片告诉你"看什么数据、什么是异常"，本节告诉你"为什么按这个顺序排查、不同引擎该怎么调整思路"。

### 性能瓶颈分层模型

数据库性能问题通常可归结为四个层次，排查时**自底向上确认瓶颈点，自顶向下定位根因**：

```
┌─ SQL 层 ─────── 低效查询（全表扫描、缺索引、统计信息过期）
├─ 锁/事务层 ──── 锁等待、死锁、长事务持锁、写冲突
├─ 连接层 ─────── 连接泄漏、连接池配置不当、重连风暴
└─ 资源层 ─────── CPU / IO / Memory / Disk 瓶颈
```

**层间因果关系**（排查时必须区分"原因"和"结果"）：
- SQL 层问题（全表扫描）→ 向上传导为 CPU 高、IO 高
- 锁等待 → 连接堆积 → 表现为"连接打满"
- 连接泄漏 → 内存被占满 → 表现为"OOM"
- 排查顺序：先看资源层确认瓶颈存在 → 再从 SQL 层开始逐层找根因

### DB 引擎核心差异

不同引擎的架构差异会**改变排查路径**，不能套用同一套步骤：

| 维度 | MySQL (InnoDB) | PostgreSQL | MongoDB (WiredTiger) | Redis |
|:---|:---|:---|:---|:---|
| **连接模型** | 线程/连接 | 进程/连接（更重，打满影响更大） | 线程池 | 单线程 + 多路复用 |
| **锁粒度** | 行锁 + 间隙锁 | 行锁（MVCC 实现不同） | 文档锁 + 意向锁 | 无锁（单线程） |
| **死锁处理** | 自动检测回滚 | 自动检测（`deadlock_timeout`） | 无死锁检测，靠写冲突重试 | N/A |
| **独有问题** | 间隙锁冲突、undo 膨胀 | vacuum 膨胀、dead tuple、序列锁 | WriteConflict 写冲突 | 阻塞命令（KEYS/SORT） |
| **执行计划** | `EXPLAIN` | `EXPLAIN (ANALYZE, BUFFERS)` — 多出 buffer 命中信息 | `.explain("executionStats")` | N/A |
| **慢查询补充源** | — | `pg_stat_statements`（历史累计统计） | `db.currentOp()` | `SLOWLOG GET` |

**对排查路径的关键影响**：
- **PG 进程模型**：每连接一个进程，连接打满时内存消耗远大于 MySQL，连接泄漏排查需同时关注内存
- **PG 的锁排查**：没有 MySQL 的 `innodb_lock_waits` 系统表，需要 `pg_locks` + `pg_stat_activity` 联合查；`idle in transaction` 状态是 PG 特有的常见锁持有根因
- **PG 的 vacuum**：dead tuple 膨胀是 PG 独有的慢查询根因（MySQL 没有对应场景），慢查询排查需额外检查 `pg_stat_user_tables` 的 `n_dead_tup`
- **MongoDB 无传统锁等待**：写冲突通过 WriteConflict 错误体现，不是"谁阻塞了谁"的模式，排查方向完全不同
- **Redis 单线程**：CPU 问题本质是"哪个命令阻塞了事件循环"（如 KEYS、大 key 操作），不是并发竞争

### 通用决策原则

- **先全局后局部**：先 `describe_health_summary` 看整体，再深入具体维度
- **先确认后诊断**：确认问题正在发生（而非历史残留），再分析根因
- **被阻塞的是受害者**：分析锁/连接问题时，找阻塞源头，不分析被阻塞的 SQL
- **区分原因和结果**：CPU 高可能是慢查询的结果而非原因，连接打满可能是锁等待的结果
- **数据不足时扩大范围**：慢查询没结果不代表没问题——可能阈值不匹配，换 `describe_full_sql_detail` 或扩大时间范围
- **函数不支持时找替代**：某些函数不支持特定 DB（如 PG 不支持 `describe_deadlock`），用 `execute_sql` 查系统视图替代

---

## 通用场景

- [巡检](health-inspection.md) - 健康检查，产出概览报告（适用所有 db_type，不支持的项自动跳过）

## 症状速查

用户表述模糊时，参考此表选择最可能的场景。按概率排序，排查后根据结果决定是否跳转到其他场景。

| 用户表述 | 可能场景（按概率排序） |
|:---|:---|
| "很慢" / "查询慢" / "响应时间长" | MySQL/PG/Mongo: [慢查询] > [锁等待] > [CPU 打满] > [IO 瓶颈]；Redis: [慢查询 / 大 Key](redis/slow-query.md) > [阻塞命令](redis/blocking-command.md) |
| "业务指标异常" / "指标波动" | 用 `list_databases` + `execute_sql` 查业务数据确认异常，再按症状匹配上方场景排查数据库是否相关 |
| "连不上" / "连接报错" / "too many connections" | [连接打满] > [网络抖动] > 认证问题 |
| "CPU 很高" / "CPU 打满" | [CPU 打满] > [慢查询] > [锁等待] |
| "内存不够" / "OOM" | [内存压力] > [连接堆积] > 缓存配置 |
| "磁盘满了" / "空间不够" | [磁盘空间] > [Binlog 堆积] > [临时表溢出] > [WAL 积压] |
| "主从延迟" / "数据不一致" / "同步慢" | [复制延迟] > [网络抖动] > 大事务 |
| "死锁" / "事务报错" | MySQL: [死锁] > [锁等待]；PG: [锁等待 / 死锁](postgresql/lock-wait.md)（PG 死锁自动处理，排查方式不同） |
| "写冲突" / "WriteConflict" / "写操作失败" | MongoDB: [写冲突](mongodb/write-conflict.md)；MySQL/PG: [锁等待] |
| "卡住了" / "hang" / "没响应" | [锁等待] > [会话堆积] > [CPU 打满] > [IO 瓶颈] |
| "帮我看看" / "巡检" / "健康检查" | [巡检](health-inspection.md) |

---

## 运维函数支持范围

> SQL Server、Redis、External 实例**不支持运维诊断函数和工单**，仅支持元数据探查和数据查询。
> 不支持的函数调用时会被代码自动拦截，无需 Agent 判断。

| 能力 | MySQL | VeDB-MySQL | Postgres | MongoDB |
|:---|:---:|:---:|:---:|:---:|
| 慢查询（明细/聚合/趋势） | ✓ | ✓ | ✓ | ✓ |
| 全量 SQL | ✓ | ✓ | ✓ | ✗ |
| 死锁 | ✓ | ✓ | ✗ | ✗ |
| 事务和锁 | ✓ | ✓ | ✓ | ✗ |
| 锁等待分析 | ✓ | ✓ | ✓ | ✗ |
| 错误日志 | ✓ | ✓ | ✓ | ✗ |
| 表空间 | ✓ | ✓ | ✓ | ✗ |
| 健康概览 | ✓ | ✓ | ✓ | ✗ |
| 监控指标（metric_items/data） | ✓ | ✗ | ✗ | ✗ |
| 表级监控（table_metric） | ✓ | ✓ | ✓ | ✗ |
| 活跃会话列表 | ✓ | ✓ | ✓ | ✓ |
| 历史连接快照 | ✓ | ✓ | ✓ | ✓ |

---

## MySQL（包括 VeDBMySQL、ByteRDS 等 MySQL 兼容引擎）

MySQL 及 MySQL 兼容数据库引擎的故障排查指南。

**常见场景：**
- [CPU 打满](mysql/cpu-spike.md) - CPU 使用率过高
- [连接数打满](mysql/connection-full.md) - 连接数达到上限
- [磁盘空间不足](mysql/disk-full.md) - 磁盘空间耗尽
- [内存压力](mysql/memory-pressure.md) - 内存使用率过高
- [死锁](mysql/deadlock.md) - 事务死锁
- [慢查询](mysql/slow-query.md) - 查询性能问题
- [IO 瓶颈](mysql/io-bottleneck.md) - 磁盘 IO 瓶颈
- [锁等待](mysql/lock-wait.md) - 锁竞争
- [会话堆积](mysql/session-pileup.md) - 活跃会话堆积
- [临时表溢出](mysql/temp-table-overflow.md) - 磁盘临时表溢出
- [网络抖动](mysql/network-jitter.md) - 网络延迟问题


---

## Postgres（包括所有 Postgres 兼容引擎）

Postgres 及所有 Postgres 兼容数据库引擎的故障排查指南。

**常见场景：**
- [CPU 打满](postgresql/cpu-spike.md) - CPU 使用率过高
- [连接数打满](postgresql/connection-full.md) - 连接数达到上限
- [磁盘空间不足](postgresql/disk-full.md) - 磁盘空间耗尽
- [慢查询](postgresql/slow-query.md) - 查询性能问题
- [锁等待 / 死锁](postgresql/lock-wait.md) - 锁竞争和死锁（PG 死锁自动处理，排查合并在锁等待中）
- [内存压力](postgresql/memory-pressure.md) - 内存使用率过高
- [VACUUM 阻塞](postgresql/vacuum-blocking.md) - VACUUM 操作阻塞
- [WAL 积压](postgresql/wal-backlog.md) - WAL 累积
- [复制延迟](postgresql/replication-delay.md) - 流复制延迟


---

## MongoDB

MongoDB 数据库故障排查指南。可用运维函数：慢查询（明细/聚合/趋势）、实例节点列表。不支持：全量 SQL、死锁、事务/锁、错误日志、表空间、健康概览、监控指标。

**常见场景：**
- [CPU 打满](mongodb/cpu-spike.md) - CPU 使用率过高
- [连接数打满](mongodb/connection-full.md) - 连接数达到上限
- [磁盘空间不足](mongodb/disk-full.md) - 磁盘空间耗尽
- [慢查询](mongodb/slow-query.md) - 查询性能问题
- [内存压力](mongodb/memory-pressure.md) - WiredTiger 缓存压力
- [复制延迟](mongodb/replication-delay.md) - 副本集延迟
- [锁等待](mongodb/lock-wait.md) - 数据库/集合锁
- [写冲突](mongodb/write-conflict.md) - WiredTiger WriteConflict（乐观并发冲突）
- [连接泄漏](mongodb/connection-leak.md) - 连接泄漏


---

## Redis

Redis 内存数据库故障排查指南。**Redis 不支持任何运维诊断 API**，以下 SOP 主要通过 `execute_sql`（Redis 命令）进行排查。

**常见场景：**
- [慢查询 / 大 Key](redis/slow-query.md) - 响应变慢、大 Key 操作阻塞
- [内存打满](redis/memory-full.md) - 内存耗尽 (OOM)
- [连接数打满](redis/connection-full.md) - 连接数达到上限
- [持久化阻塞](redis/persistence-block.md) - AOF/RDB 阻塞
- [集群故障](redis/cluster-failure.md) - 集群节点故障
- [阻塞命令](redis/blocking-command.md) - 阻塞命令
- [复制延迟](redis/replication-delay.md) - 主从延迟
- [CPU 打满](redis/cpu-spike.md) - CPU 使用率过高


