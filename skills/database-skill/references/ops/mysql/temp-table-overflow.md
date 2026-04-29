# 临时表溢出故障排查

## 概述

临时表溢出是指由于排序或分组操作产生的数据无法完全在内存中完成，导致使用磁盘临时表（MyISAM 临时表或 InnoDB 内部临时表），性能下降。

## 典型症状

- 磁盘临时表使用增多
- 查询执行时间变长
- `Created_tmp_disk_tables` 变量增大
- 性能下降

> 函数参数详见 [api/ops.md](../../api/ops.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|:---|:---|:---|:---|
| P0 | `execute_sql` | `sql="SHOW GLOBAL STATUS LIKE 'Created_tmp%';"` | 查看临时表统计（内存 vs 磁盘临时表数量） |
| P0 | `execute_sql` | `sql="SHOW GLOBAL STATUS LIKE 'Sort%';"` | 排序统计（Sort_merge_passes 高说明排序溢出磁盘） |
| P1 | `execute_sql` | `sql="SHOW VARIABLES LIKE 'tmp_table_size';"` | 内存临时表大小限制 |
| P1 | `execute_sql` | `sql="SHOW VARIABLES LIKE 'max_heap_table_size';"` | MEMORY 引擎表大小限制（与 tmp_table_size 取较小值） |
| P1 | `describe_slow_logs` | `order_by="QueryTime"` | 定位含 GROUP BY / ORDER BY 的慢查询 |
| P2 | `describe_aggregate_slow_logs` | `order_by="TotalQueryTime"` | 按模板聚合，找高频临时表溢出 SQL |

## 关键分析维度

- **磁盘临时表占比**：`Created_tmp_disk_tables / Created_tmp_tables` — 比例高说明内存不够用
- **Sort_merge_passes**：值大说明排序数据量超出 `sort_buffer_size`，需要多趟归并
- **tmp_table_size vs 实际需求**：对比 `tmp_table_size` 和 `max_heap_table_size`（取较小值）
- **SQL 特征**：含 GROUP BY / ORDER BY / DISTINCT / UNION 的 SQL 最可能产生临时表

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| Created_tmp_disk_tables 持续增长 + tmp_table_size 很小 | 内存临时表大小限制过低 | 对比当前值与慢查询的数据量需求 |
| 慢查询含 GROUP BY 且 rows_examined 很大 | 分组结果集过大，超出内存限制 | `execute_sql("EXPLAIN <sql>")` 检查 Extra 列是否有 Using temporary |
| SQL 含 ORDER BY 无索引列 | 缺少排序索引导致 filesort + 磁盘临时表 | 检查 ORDER BY 字段是否有索引 |
| SQL 含 TEXT/BLOB 列参与运算 | 大字段强制使用磁盘临时表（MEMORY 引擎不支持） | 优化 SQL 避免在 GROUP BY/ORDER BY 中使用大字段 |
| Sort_merge_passes 高 + sort_buffer_size 小 | 排序缓冲区不足 | 考虑适当增大 `sort_buffer_size` |

## 约束与边界

- `execute_sql` 仅支持只读操作，无法执行 `SET GLOBAL` 修改参数
- 参数调整（`tmp_table_size`、`max_heap_table_size`、`sort_buffer_size`）需到**火山引擎控制台 → 参数管理**修改
- DDL 变更（添加索引）须通过 `create_ddl_sql_change_ticket` 工单执行

## ⚠️ 应急处置（需确认后执行）

### 增加 tmp_table_size

> `execute_sql` 仅支持只读操作，无法执行 `SET GLOBAL`。需到**火山引擎控制台 → 参数管理**修改 `tmp_table_size` 和 `max_heap_table_size`。

### 优化查询（添加索引）

> DDL 变更须通过工单执行。

```python
# 通过 DDL 工单添加索引以避免 filesort
create_ddl_sql_change_ticket(client,
    sql_text="ALTER TABLE table_name ADD INDEX idx_column (column);",
    instance_id="mysql-xxx",
    database="db_name",
)
```

## 预防措施

1. 正确配置 tmp_table_size 和 max_heap_table_size
2. 添加适当索引以避免 filesort
3. 优化查询以减少结果集大小
4. 监控临时表使用情况
5. 使用适当的数据类型（避免在排序列用 TEXT/BLOB）
6. 审查慢查询日志中的临时表使用

## 关联场景

- [慢查询](slow-query.md)
- [内存压力](memory-pressure.md)
- [磁盘空间不足](disk-full.md)
