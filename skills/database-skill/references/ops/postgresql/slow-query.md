# PostgreSQL 慢查询排查

## 概述

慢查询是指执行时间较长的 SQL 语句，可能是由于缺少索引、统计信息过期、VACUUM 未及时执行、数据量过大等原因导致。

## 典型症状

- 查询响应时间变长
- 慢查询日志增加
- 监控显示 QueryTime 增大
- 特定页面加载变慢

> 函数参数详见 [api/ops.md](../../api/ops.md) 和 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|:---|:---|:---|:---|
| P0 | `describe_aggregate_slow_logs` | `order_by="TotalQueryTime"` | 按 SQL 模板聚合，定位 Top 耗时 SQL（推荐首选） |
| P0 | `describe_slow_logs` | `order_by="QueryTime"` | 单条慢查询明细，查看具体 SQL 和执行时间 |
| P1 | `describe_slow_log_time_series_stats` | `interval=300` | 慢查询时间趋势，定位高峰时段 |
| P1 | `describe_full_sql_detail` | — | 完整 SQL 历史（含执行计划），深入分析用 |
| P1 | `describe_full_sql_detail` | — | 完整 SQL 历史（含执行计划），深入分析用 |
| P2 | `describe_health_summary` | — | 整体健康概览，确认 CPU/内存是否也受影响 |

## 诊断路径

1. **定位 Top 慢 SQL** → `describe_aggregate_slow_logs(order_by="TotalQueryTime")` — 从聚合维度找出总耗时最多的 SQL 模板
2. **查看明细** → `describe_slow_logs(order_by="QueryTime")` — 查看具体 SQL 文本和执行时间
   - 如果慢查询日志为空 → 可能 `log_min_duration_statement` 阈值过高，用 `describe_full_sql_detail` 获取全量 SQL 历史
3. **分析执行计划** → 对 Top 慢 SQL 执行 `execute_sql("EXPLAIN (ANALYZE, BUFFERS) <sql>")` — PG 的 BUFFERS 输出能看到 buffer cache 命中情况，这是 IO 瓶颈诊断的关键信息
4. **检查 PG 特有问题**（MySQL 不需要这一步）：
   - **dead tuple 膨胀** → `execute_sql("SELECT relname, n_dead_tup, n_live_tup, last_autovacuum FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT 10")` — dead tuple 过多导致顺序扫描效率下降
   - **统计信息过期** → 同一查询中的 `last_analyze` / `last_autoanalyze` — 统计信息过期导致优化器选错执行计划
   - **buffer 命中率** → 通过 `EXPLAIN (ANALYZE, BUFFERS)` 的输出判断：Buffers shared read 远大于 shared hit 说明内存不足
5. **确认整体健康** → `describe_health_summary` — CPU/内存是否也受影响（慢查询可能是更上层问题的结果）

## 关键分析维度

拿到慢查询数据后，按以下维度分析：

- **by SQL Template**：哪个 SQL 模板总耗时最多 -- aggregate_slow_logs 的 `query_time_stats.total` 排序
- **by Execute Count**：高频 + 慢 = 优化优先级最高
- **by rows_examined vs rows_sent**：扫描行远大于返回行 = 缺索引或索引失效
- **by time**：慢查询是持续发生还是集中在某个时段 -- 用 time_series_stats 判断
- **by Buffers shared hit vs read**（EXPLAIN BUFFERS 输出）：缓存命中率低 = 内存不足或工作集过大
- **by dead tuple count**（pg_stat_user_tables）：dead tuple 多 = vacuum 不及时，表膨胀
- **by user/source_ip**：是否特定应用/服务产生的慢查询

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| rows_examined >> rows_sent，Seq Scan | 缺少索引 | `execute_sql("EXPLAIN <sql>")` 查看执行计划 |
| 有索引但优化器选择 Seq Scan | 统计信息过期 | `execute_sql("SELECT relname, last_analyze, last_autoanalyze FROM pg_stat_user_tables")` 检查 ANALYZE 时间 |
| 索引存在但未被使用 | 索引失效 | 检查是否有函数包裹字段、类型不匹配、表达式索引缺失 |
| 多表 JOIN，Nested Loop 扫描行数极大 | 复杂 JOIN | 检查 JOIN 条件是否有索引，考虑拆分查询或调整 join_collapse_limit |
| 慢查询集中在某个时段，其他时段正常 | 业务高峰 / 批处理任务 | 查 time_series_stats 对应时段 |
| 查询被阻塞，等待锁释放 | 锁等待 / VACUUM 阻塞 | 转到[锁等待排查](lock-wait.md)或 [VACUUM 阻塞排查](vacuum-blocking.md) |
| shared_blks_read 远大于 shared_blks_hit | 缓存命中率低 | 检查 shared_buffers 配置和工作集大小 |
| 大量死元组，表膨胀 | VACUUM 未及时执行 | `execute_sql("SELECT relname, n_dead_tup, last_autovacuum FROM pg_stat_user_tables ORDER BY n_dead_tup DESC")` |

## 深入分析方法

- **EXPLAIN 分析**：对 Top 慢 SQL 执行 `execute_sql("EXPLAIN <sql>")` 查看执行计划，关注 Seq Scan、Nested Loop、Sort（外部排序）、Hash Join 内存溢出等
- **EXPLAIN ANALYZE**：`execute_sql("EXPLAIN ANALYZE <sql>")` 实际执行查询并返回真实耗时和行数。注意：ANALYZE 会真正执行查询，对写操作慎用
- **索引建议**：根据 WHERE / JOIN / ORDER BY 字段设计索引，通过 `create_ddl_sql_change_ticket` 提交 DDL 工单
- **全量 SQL 对比**：`describe_full_sql_detail` 可查看正常时段 vs 异常时段的 SQL 执行时间变化

## 约束与边界

- `execute_sql` 仅支持只读操作（SELECT, SHOW, EXPLAIN），DDL 变更须通过 `create_ddl_sql_change_ticket` 工单
- `describe_health_summary` 时间范围限制在最近 1 小时
- 慢查询日志需实例已开启慢查询记录（`log_min_duration_statement` 参数）

## 应急处置（需确认后执行）

> **终止进程会导致当前事务失败，请在确认后执行！**

- **终止指定进程**：`kill_process(client, process_ids=["<id>"], node_id="<node>")`
- **终止慢查询**：`kill_process(client, command_type="Query", min_time=60)` -- 终止执行超过 60 秒的查询
- **添加索引**：`create_ddl_sql_change_ticket(client, sql_text="CREATE INDEX idx_col ON t (col);", database="db")`

## 预防措施

1. 定期审查慢查询日志
2. 添加适当的索引
3. 保持统计信息更新（ANALYZE），确保 autovacuum 正常运行
4. 使用 EXPLAIN 分析查询计划
5. 设置慢查询告警
6. 优化应用 SQL 模式
7. 监控表膨胀和死元组数量

## 关联场景

- [锁等待](lock-wait.md)
- [CPU 打满](cpu-spike.md)
- [VACUUM 阻塞](vacuum-blocking.md)
