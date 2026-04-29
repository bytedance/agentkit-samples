# MySQL 慢查询排查

## 概述

慢查询是指执行时间超过 `long_query_time` 阈值的 SQL 语句，可能是由于缺少索引、SQL 写法问题、数据量过大等原因导致。

## 典型症状

- 查询响应时间变长
- 慢查询日志增加
- 监控显示 QueryTime 增大
- 特定页面加载变慢

> 函数参数详见 [api/ops.md](../../api/ops.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|:---|:---|:---|:---|
| P0 | `describe_aggregate_slow_logs` | `order_by="TotalQueryTime"`, `database=` | 按 SQL 模板聚合，定位 Top 耗时 SQL（推荐首选） |
| P0 | `describe_slow_logs` | `order_by="QueryTime"`, `database=` | 单条慢查询明细，查看具体 SQL 和执行时间 |
| P1 | `describe_slow_log_time_series_stats` | `interval=300`, `database=` | 慢查询时间趋势，定位高峰时段 |
| P1 | `describe_full_sql_detail` | — | 完整 SQL 历史（含执行计划），深入分析用 |
| P2 | `describe_health_summary` | — | 整体健康概览，确认 CPU/内存是否也受影响 |

> **提示**：同一实例上往往有多个数据库。排查特定数据库的慢查询时，务必传 `database` 参数做服务端过滤，避免其他数据库的慢查询干扰分析。

## 关键分析维度

拿到慢查询数据后，按以下维度分析：

- **by SQL Template**：哪个 SQL 模板总耗时最多 -- aggregate_slow_logs 的 `query_time_stats.total` 排序
- **by Execute Count**：高频 + 慢 = 优化优先级最高
- **by rows_examined vs rows_sent**：扫描行远大于返回行 = 缺索引或索引失效
- **by time**：慢查询是持续发生还是集中在某个时段 -- 用 time_series_stats 判断
- **by user/source_ip**：是否特定应用/服务产生的慢查询

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| rows_examined >> rows_sent，SQL 含全表扫描 | 缺少索引 | `execute_sql("EXPLAIN <sql>")` 查看执行计划 |
| 有索引但未被使用，rows_examined 仍很高 | 索引失效 | 检查是否有函数包裹字段、隐式类型转换、OR 条件 |
| 多表 JOIN，rows_examined 呈乘积关系 | 复杂 JOIN | 检查 JOIN 条件是否有索引，考虑拆分查询 |
| 慢查询集中在某个时段，其他时段正常 | 业务高峰 / 批处理任务 | 查 time_series_stats 对应时段 |
| lock_time 占 query_time 比例高 | 锁等待 | 转到[锁等待排查](lock-wait.md) |
| 大量 SQL 扫描同一张大表 | 数据量过大 | 查 `describe_table_space` 确认表大小，考虑分区/归档 |
| 统计信息过期，优化器选择错误执行计划 | 统计信息过期 | `execute_sql("SELECT TABLE_NAME, TABLE_ROWS, DATA_LENGTH FROM information_schema.TABLES WHERE TABLE_SCHEMA='<db>'")` 查看 Data_length、Rows 是否合理 |

## 深入分析方法

- **EXPLAIN 分析**：对 Top 慢 SQL 执行 `execute_sql("EXPLAIN <sql>")` 查看执行计划，关注 type（ALL=全表扫描）、rows、Extra（Using filesort / Using temporary）
- **索引建议**：根据 WHERE / JOIN / ORDER BY 字段设计索引，通过 `create_ddl_sql_change_ticket` 提交 DDL 工单
- **全量 SQL 对比**：`describe_full_sql_detail` 可查看正常时段 vs 异常时段的 SQL 执行时间变化

## 约束与边界

- `execute_sql` 仅支持只读操作（SELECT, SHOW, EXPLAIN），DDL 变更须通过 `create_ddl_sql_change_ticket` 工单
- `describe_health_summary` 时间范围限制在最近 1 小时
- 慢查询日志需实例已开启慢查询记录

## 应急处置（需确认后执行）

> **终止查询会导致当前事务失败，请在确认后执行！**

- **终止指定查询**：`kill_process(client, process_ids=["<id>"], node_id="<node>")`
- **终止慢查询**：`kill_process(client, command_type="Query", min_time=60)` -- 终止执行超过 60 秒的查询
- **添加索引**：`create_ddl_sql_change_ticket(client, sql_text="ALTER TABLE t ADD INDEX idx_col (col);", database="db")`

## 预防措施

1. 定期审查慢查询日志
2. 根据查询模式添加适当索引
3. 保持表统计信息更新（ANALYZE TABLE）
4. 使用查询分析工具
5. 设置慢查询告警
6. 优化应用 SQL 模式

## 关联场景

- [锁等待](lock-wait.md)
- [CPU 打满](cpu-spike.md)
- [IO 瓶颈](io-bottleneck.md)
