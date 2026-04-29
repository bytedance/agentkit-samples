# CPU 打满故障排查

## 概述

CPU 打满是指 PostgreSQL 实例的 CPU 使用率持续接近或达到 100%，导致数据库响应变慢或完全无响应。

## 典型症状

- CPU 使用率持续 100% 或接近 100%
- 数据库响应变慢，查询超时
- 连接堆积，新请求排队等待
- 系统负载高

> 函数参数详见 [api/ops.md](../../api/ops.md) 和 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|--------|------|----------|------|
| P0 | `list_connections` | — | 查看活跃会话，定位长时间运行的查询 |
| P0 | `describe_health_summary` | — | 获取最近一小时整体健康状态（CPU/内存/连接数/QPS/TPS，含环比同比） |
| P1 | `execute_sql` | `sql="SELECT ... FROM pg_locks ... WHERE NOT granted"` | 检查锁等待情况 |

## 诊断路径

1. **看活跃会话** → `list_connections` — 找长时间运行的查询和相同 SQL 模板的堆积
2. **整体健康** → `describe_health_summary` — 确认 CPU/QPS/TPS 的环比变化
   - 如果 QPS/TPS 翻倍 → 突发流量，确认业务侧
   - 如果 QPS 正常但 CPU 高 → 单条 SQL 消耗大，转查慢查询
3. **定位慢 SQL** → 对活跃会话中长时间运行的 SQL 执行 EXPLAIN ANALYZE
   - 如果多个会话在等锁 → 转查 `describe_trx_and_locks` / `describe_lock_wait`
4. **需要终止时** → 从 `list_connections` 获取 `process_id` + `node_id` 传给 `kill_process`

## 关键分析维度

- **时间相关性**：CPU 飙升的起始时间是否与流量高峰/发布上线/定时任务重合
- **会话特征**：活跃会话中是否有长时间运行的查询（time > 300s）、大量活跃连接
- **查询计划**：高频 SQL 是否缺少索引导致 Seq Scan
- **锁竞争**：是否有未授予的锁（`NOT granted`），导致连接堆积

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|----------|----------|------------|
| 活跃会话大量相同 SQL + 无索引 | 全表扫描（Seq Scan） | 对目标 SQL 执行 EXPLAIN ANALYZE 检查 |
| QPS/TPS 突然翻倍 + 连接数暴增 | 突发流量 | 确认业务发布、活动等 |
| 多会话等待锁 + granted=false | 锁竞争 | 用 `pg_locks` + `pg_stat_activity` 关联分析阻塞源 |
| 长时间运行的 PL/pgSQL 函数 | 自定义函数消耗 CPU | 检查函数内部逻辑复杂度 |
| 大数据量 JOIN/SORT | 复杂查询 | 检查 SQL 是否含多表 JOIN、ORDER BY、子查询 |

## 约束与边界

- PostgreSQL 不支持 `get_metric_items` / `get_metric_data`，通过 `describe_health_summary` 获取整体指标
- `execute_sql` 仅支持只读操作，无法执行 `SET` 修改参数
- 锁信息需通过 SQL 查询 `pg_locks` + `pg_stat_activity` 获取

## ⚠️ 应急处置（需确认后执行）

### 终止长时间运行的查询

> **警告**：终止进程会导致当前事务失败，请在确认后执行！

```python
# 按条件终止：终止执行时间超过 60 秒的查询
kill_process(client,
    command_type="Query",
    min_time=60,
    instance_id="pg-xxx",
)

# 精确终止：终止指定进程（从 list_connections 获取 process_id 和 node_id）
kill_process(client,
    process_ids=["12345"],
    node_id="node-1",
    instance_id="pg-xxx",
)
```

## 预防措施

1. 添加适当的索引
2. 优化查询计划
3. 使用连接池（PgBouncer）
4. 监控长时间运行的查询
5. 设置资源限制
6. 定期统计信息收集（ANALYZE）

## 关联场景

- [慢查询](slow-query.md)
- [锁等待](lock-wait.md)
