# CPU 打满故障排查

## 概述

CPU 打满是指 MySQL 实例的 CPU 使用率持续接近或达到 100%，导致数据库响应变慢或完全无响应。这是生产环境中常见的高优先级故障。

## 典型症状

- CPU 使用率持续 100% 或接近 100%
- 数据库响应变慢，查询超时
- 连接堆积，新请求排队等待
- `top` 或监控显示 MySQL 进程 CPU 占用高

> 函数参数详见 [api/ops.md](../../api/ops.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|--------|------|----------|------|
| P0 | `list_connections` | — | 查看活跃会话，定位长时间运行的 SQL |
| P0 | `describe_slow_logs` | `order_by="QueryTime"`, `sort_by="DESC"` | 找出最慢的 SQL，判断是否全表扫描 |
| P1 | `get_metric_data` | `metric_name="CpuUtil"` | 确认 CPU 打满的时间区间和趋势 |
| P1 | `get_metric_data` | `metric_name="QPS"` / `"TPS"` | 判断是否为流量激增导致 |
| P1 | `describe_trx_and_locks` | `lock_status="LockHold"` | 查看持有锁的事务，判断锁竞争 |
| P2 | `describe_lock_wait` | — | 查看阻塞链，分析锁等待是否导致线程堆积 |
| P2 | `get_metric_items` | — | 获取支持的监控指标列表，按需选取更多指标 |

## 诊断路径

1. **确认 CPU 高** — 用监控数据确认 CPU 确实处于高位，而非仅凭用户描述
   - **MySQL**：`get_metric_data(metric_name="CpuUtil")` 查看 CPU 使用率曲线
   - **VeDB**：不支持 `get_metric_data`，改用 `describe_health_summary` 查看 CPU 环比（`mom` 字段）
2. **看活跃会话** → `list_connections` — 找长时间运行的 SQL 和相同 SQL 模板的堆积
3. **定位慢 SQL** → `describe_slow_logs(order_by="QueryTime")` — 取 Top SQL
   - 如果大量相同 SQL 且无索引 → 全表扫描是根因
   - 如果多个会话在等锁 → 转查 `describe_trx_and_locks` / `describe_lock_wait`
4. **分析执行计划** → 对 Top 慢 SQL 执行 `execute_sql("EXPLAIN <SQL>")` — 确认是否全表扫描（`type=ALL`）、缺失索引（`key=NULL`），这是定位根因的关键步骤
5. **需要终止时** → 从 `list_connections` 获取目标会话的 `process_id` + `node_id` 传给 `kill_process`

## 关键分析维度

- **时间相关性**：CPU 飙升的起始时间是否与流量高峰/发布上线/定时任务重合
- **SQL 特征**：活跃会话中是否有大量相同 SQL 模板、是否存在全表扫描
- **并发度**：QPS/TPS 是否异常飙升，是否有突发流量
- **锁竞争**：是否有大量线程处于锁等待状态，导致 CPU 空转

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|----------|----------|------------|
| 活跃会话大量相同 SQL + 慢查询无索引 | 全表扫描 | 对目标 SQL 执行 EXPLAIN 检查是否 type=ALL |
| QPS/TPS 突然翻倍 + 会话数暴增 | 突发流量 | 确认是否有业务发布、营销活动 |
| 多个会话等待锁 + 持锁事务执行时间长 | 锁竞争导致线程堆积 | 检查 `describe_lock_wait` 的阻塞链 |
| 慢查询中大量排序/临时表操作 | 复杂查询消耗 CPU | 检查 SQL 是否含 ORDER BY、GROUP BY、子查询 |
| CPU 高 + IO 等待也高 | IO 瓶颈引发 CPU 空转 | 检查磁盘使用率和 IOPS 指标 |

## 约束与边界

- `execute_sql` 仅支持只读操作（SELECT/SHOW），无法执行 `SET GLOBAL` 修改参数
- 参数调整需到**火山引擎控制台 → 参数管理**修改（如 `max_connections`）
- Redis/MongoDB 不支持 `get_metric_items` / `get_metric_data`，本文仅适用于 MySQL

## ⚠️ 应急处置（需确认后执行）

### 终止长时间运行的查询

> **警告**：终止进程会导致当前查询失败，请在确认后执行！

```python
# 按条件终止：终止执行时间超过 60 秒的查询
kill_process(client,
    command_type="Query",
    min_time=60,
    instance_id="mysql-xxx",
)

# 精确终止：终止指定进程（从 list_connections 获取 process_id 和 node_id）
kill_process(client,
    process_ids=["12345"],
    node_id="node-1",
    instance_id="mysql-xxx",
)
```

## 预防措施

1. 优化慢查询，添加合适的索引
2. 正确配置连接池
3. 监控 CPU 使用率并设置告警
4. 定期审查 SQL 执行计划
5. 设置查询超时

## 关联场景

- [慢查询](slow-query.md)
- [锁等待](lock-wait.md)
- [会话堆积](session-pileup.md)
