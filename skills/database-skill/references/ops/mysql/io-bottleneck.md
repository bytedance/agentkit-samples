# IO 瓶颈故障排查

## 概述

IO 瓶颈是指磁盘 IOPS 或吞吐量达到上限，导致数据库请求等待 IO 完成，表现为 IO 使用率高、IO 等待时间长的现象。

## 典型症状

- IOPS 达到上限
- IO 使用率 100%
- 磁盘响应时间变长
- 查询执行时间变长

> 函数参数详见 [api/ops.md](../../api/ops.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|:---|:---|:---|:---|
| P0 | `get_metric_data` | `metric_name="InnodbDataReadCounts"`, `period=60` | InnoDB 读 IO 次数趋势（无直接 IOPS 指标，此为近似） |
| P0 | `get_metric_data` | `metric_name="InnodbDataReadBytes"`, `period=60` | InnoDB 读吞吐量趋势 |
| P0 | `get_metric_data` | `metric_name="DiskUtil"`, `period=60` | 磁盘使用率趋势 |
| P1 | — | ~~`SHOW ENGINE INNODB STATUS`~~ 被平台拦截 | InnoDB IO 详情不可直接查询，用 `get_metric_data` 指标替代 |
| P1 | `describe_slow_logs` | `order_by="QueryTime"` | 定位可能造成大量 IO 的慢查询 |
| P2 | `get_metric_items` | — | 获取支持的监控指标列表，按需选取更多指标 |

## 关键分析维度

- **IO 类型**：读 IO 为主还是写 IO 为主 — 读多考虑缓存命中率，写多考虑刷脏频率
- **时间相关性**：IO 高峰是否与业务高峰/备份/Checkpoint 时间重合
- **热点表**：哪些表产生的 IO 最多 — 结合慢查询中 rows_examined 大的 SQL
- **缓冲池命中率**：InnoDB Buffer Pool Hit Rate 低说明内存不足，大量读需要落盘

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| 读 IO 高 + 慢查询含全表扫描 | 缺少索引导致大量随机读 | `execute_sql("EXPLAIN <sql>")` 检查执行计划 |
| 写 IO 高 + DML 频繁 | 大量 DML 产生 Binlog 写入 | 检查 `DiskUsageBytes` 指标趋势和 `describe_slow_logs` 中写操作比例 |
| IO 周期性飙升 | Checkpoint 或备份任务 | 检查飙升时间是否与 Checkpoint 间隔吻合 |
| 读 IO 高 + Buffer Pool Hit Rate 低 | 内存不足导致频繁磁盘读 | 检查 `InnodbBufferPoolReadRequests` vs `InnodbBufferPoolReads` |
| 随机写入多 + 磁盘延迟高 | 存储性能不足 | 考虑升级到更高 IOPS 的存储规格 |

## 约束与边界

- `get_metric_data` / `get_metric_items` 仅 MySQL 支持，Redis/MongoDB 不可用
- `execute_sql` 仅支持只读操作，无法执行 `SET GLOBAL` 修改参数
- IO 相关参数调整（如 `innodb_flush_log_at_trx_commit`、`sync_binlog`）需到**火山引擎控制台 → 参数管理**修改

## ⚠️ 应急处置（需确认后执行）

### 调整 IO 相关参数

> `execute_sql` 仅支持只读操作，无法执行 `SET GLOBAL`。如需调整以下参数，需到**火山引擎控制台 → 参数管理**修改：
> - `innodb_flush_log_at_trx_commit`（改为 2 可提升性能但降低持久性）
> - `sync_binlog`（改为 0 可减少 IO 但降低数据安全性）

## 预防措施

1. 使用 SSD 或高性能存储
2. 优化查询以减少 IO
3. 正确索引以减少随机 IO
4. 分离数据和日志文件
5. 监控 IO 指标并设置告警
6. 使用读写分离

## 关联场景

- [慢查询](slow-query.md)
- [磁盘空间不足](disk-full.md)
