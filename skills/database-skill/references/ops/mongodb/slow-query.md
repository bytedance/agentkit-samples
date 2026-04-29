# MongoDB 慢查询排查

## 概述

慢查询是指执行时间较长的 MongoDB 操作，可能是由于缺少索引、数据量过大、内存不足等原因导致。

## 典型症状

- 查询响应时间变长
- 慢查询日志增加
- 监控显示 QueryTime 增大
- 特定页面加载变慢

> 函数参数详见 [api/ops.md](../../api/ops.md) 和 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|:---|:---|:---|:---|
| P0 | `describe_aggregate_slow_logs` | `order_by="TotalQueryTime"` | 按操作模板聚合，定位 Top 耗时操作（推荐首选） |
| P0 | `describe_slow_logs` | `order_by="QueryTime"` | 单条慢查询明细，查看具体操作和执行时间 |
| P1 | `describe_slow_log_time_series_stats` | `interval=300` | 慢查询时间趋势，定位高峰时段 |
| P1 | `execute_sql` | `sql="db.getSiblingDB('admin').aggregate([{$currentOp: ...}])"` | 查看当前运行中的慢操作 |

> MongoDB 不支持 `describe_full_sql_detail` 和 `describe_health_summary`。

## 关键分析维度

拿到慢查询数据后，按以下维度分析：

- **by Operation Template**：哪个操作模板总耗时最多 -- aggregate_slow_logs 的 `query_time_stats.total` 排序
- **by Execute Count**：高频 + 慢 = 优化优先级最高
- **by Collection**：慢操作集中在哪些集合
- **by time**：慢查询是持续发生还是集中在某个时段 -- 用 time_series_stats 判断
- **by Operation Type**：find / update / aggregate / mapReduce 各占多少

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| COLLSCAN（全集合扫描），查询无索引 | 缺少索引 | `execute_sql("db.collection.getIndexes()")` 查看现有索引 |
| 有索引但查询未命中 | 索引选择错误 | `execute_sql("db.collection.find(<query>).explain('executionStats')")` 查看执行计划 |
| 大量文档扫描，返回少量文档 | 索引覆盖不足 | 检查查询条件是否与索引字段匹配 |
| 慢查询集中在某个时段，其他时段正常 | 业务高峰 / 批处理任务 | 查 time_series_stats 对应时段 |
| aggregate 管道操作耗时高 | 管道未优化 | 检查是否有 $match 前置、是否利用索引 |
| 操作被阻塞，secs_running 很长 | 锁等待 | 转到[锁等待排查](lock-wait.md) |
| 内存使用率高，WiredTiger 缓存命中率下降 | 内存压力 | 转到[内存压力排查](memory-pressure.md) |

## 深入分析方法

- **explain 分析**：对慢操作执行 explain 查看执行计划

```javascript
db.collection.find(<query>).explain("executionStats")
```

关注 `totalDocsExamined` vs `nReturned`（扫描文档数远大于返回数 = 需要索引）、`stage`（COLLSCAN = 全集合扫描）、`executionTimeMillis`

- **$currentOp 查看当前操作**：

```javascript
db.getSiblingDB('admin').aggregate([
    { $currentOp: { allUsers: true, idleConnections: false } },
    { $match: { secs_running: { $gt: 5 } } },
    { $sort: { secs_running: -1 } },
    { $limit: 20 }
])
```

- **索引查看**：`execute_sql("db.collection.getIndexes()")` 查看现有索引。创建索引需到**火山引擎控制台**操作（MongoDB 不支持变更工单）

## 约束与边界

- MongoDB 不支持 `describe_full_sql_detail`（全量 SQL），排查慢查询依赖 `describe_slow_logs` + `execute_sql` 查 explain
- `execute_sql` 仅用于查询类操作，创建索引等写操作需到**火山引擎控制台**操作（MongoDB 不支持变更工单）

## 应急处置（需确认后执行）

> **终止操作会导致当前任务失败，请在确认后执行！**

- **终止指定操作**：

```python
kill_process(client,
    process_ids=["<process_id>"],
    node_id="<node_id>",
    instance_id="mongo-xxx",
)
```

## 预防措施

1. 定期审查慢查询日志
2. 根据查询模式添加适当索引
3. 使用 explain() 分析查询
4. 监控 WiredTiger 缓存命中率
5. 设置慢查询告警
6. 优化 aggregate 管道（$match 前置、减少 $lookup）

## 关联场景

- [内存压力](memory-pressure.md)
- [锁等待](lock-wait.md)
