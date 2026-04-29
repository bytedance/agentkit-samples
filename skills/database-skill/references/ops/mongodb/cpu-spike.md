# CPU 打满故障排查

## 概述

CPU 打满是指 MongoDB 实例的 CPU 使用率持续接近或达到 100%，导致数据库响应变慢或完全无响应。常见原因包括缺少索引的全集合扫描、高并发写入、复杂聚合操作等。

## 典型症状

- 数据库响应变慢，查询超时
- 连接堆积，新请求排队等待
- 大量慢查询

> 函数参数详见 [api/ops.md](../../api/ops.md) 和 [api/metadata-query.md](../../api/metadata-query.md)。
>
> ⚠️ MongoDB 不支持 `get_metric_data` / `get_metric_items`，无法直接查看 CPU 使用率趋势。排查依赖会话、慢查询和 `db.serverStatus()` 等原生命令。

## 必看数据

| 优先级 | 数据来源 | 命令/函数 | 目的 |
|--------|----------|-----------|------|
| P0 | `execute_sql` | `db.serverStatus().opcounters;` | 确认负载：看 query/insert/update/delete 计数是否异常高 |
| P0 | `list_connections` | — | 查看活跃会话，定位长时间运行的操作 |
| P0 | `describe_aggregate_slow_logs` | `order_by="TotalQueryTime"` | 按 SQL 模板聚合，找总耗时最高的操作 |
| P1 | `execute_sql` | `db.currentOp({secs_running: {$gt: 5}});` | 查看当前长时间运行的操作 |
| P1 | `describe_slow_logs` | `order_by="QueryTime"` | 单条慢查询明细，查看具体操作和执行时间 |
| P2 | `execute_sql` | `db.serverStatus().connections;` | 连接数是否异常高 |

## 诊断路径

1. **确认负载高** → MongoDB 无监控 API，需用原生命令间接确认：
   - `execute_sql("db.serverStatus().opcounters")` — 查看 query/insert/update/delete 的计数器值，高值说明负载重
   - `execute_sql("db.serverStatus().globalLock")` — `currentQueue.total > 0` 或 `activeClients` 高说明有排队
   - `execute_sql("db.currentOp({secs_running: {$gt: 5}})")` — 如有多个长时间操作，说明 CPU 被占满
   - 只要上述任一指标异常即可确认 CPU 压力，不必等用户提供监控截图
2. **看活跃会话** → `list_connections` — 找长时间运行的操作和相同操作模板的堆积
3. **定位慢操作** → `describe_aggregate_slow_logs(order_by="TotalQueryTime")` — 找总耗时最高的操作模板
   - 如果大量 COLLSCAN → 缺索引导致全集合扫描是根因
   - 如果大量聚合操作 → 检查 pipeline 复杂度
4. **查当前操作**（如步骤 1 未做） → `execute_sql("db.currentOp({secs_running: {$gt: 5}})")` — 查看正在执行的慢操作
   - 大量相同 ns（命名空间）→ 热点集合
   - `waitingForLock: true` → 锁竞争，转查 [锁等待](lock-wait.md)
5. **需要终止时** → 从 `list_connections` 获取 `process_id` + `node_id` 传给 `kill_process`

## 关键分析维度

- **操作类型**：是查询（find）、写入（insert/update）还是聚合（aggregate）消耗 CPU
- **扫描效率**：`docsExamined` 远大于 `nReturned` = 缺索引
- **并发度**：大量相同操作堆积说明并发压力
- **连接数**：连接数异常高可能是连接泄漏导致的间接 CPU 压力

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|----------|----------|------------|
| 慢查询大量 COLLSCAN + docsExamined 极大 | 缺少索引 | `execute_sql("db.collection.getIndexes()")` 检查索引，`explain('executionStats')` 确认 |
| 大量相同操作堆积 + 连接数高 | 突发流量 / 热点查询 | 确认业务侧是否有流量变化 |
| 聚合操作耗时长 + pipeline 多个 stage | 复杂聚合消耗 CPU | 优化 pipeline，尽早 `$match` 减少数据量 |
| currentOp 显示大量 `waitingForLock` | 锁竞争导致线程堆积 | 转查 [锁等待](lock-wait.md) |
| 大量写入 + WiredTiger cache 压力大 | 写入压力 | `execute_sql("db.serverStatus().wiredTiger.cache")` 查看脏页比例 |

## 约束与边界

- MongoDB **不支持** `get_metric_data` / `get_metric_items`，无法获取 CPU 使用率历史趋势
- `execute_sql` 仅用于查询类操作
- 索引创建需到**火山引擎控制台**操作（MongoDB 不支持变更工单）

## ⚠️ 应急处置（需确认后执行）

### 终止长时间运行的操作

> **警告**：终止操作会导致当前事务失败，请在确认后执行！

```python
# 从 list_connections 或 currentOp 获取 process_id + node_id
kill_process(client,
    process_ids=["12345"],
    node_id="node-1",
    instance_id="mongo-xxx",
)
```

## 预防措施

1. 为高频查询添加合适的索引
2. 优化聚合 pipeline（尽早过滤）
3. 监控慢查询并设置告警
4. 使用适当的读偏好（readPreference）分担主节点压力
5. 避免全集合扫描

## 关联场景

- [慢查询](slow-query.md)
- [锁等待](lock-wait.md)
- [连接数打满](connection-full.md)
