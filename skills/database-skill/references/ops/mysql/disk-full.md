# 磁盘空间不足故障排查

## 概述

磁盘空间不足是指 MySQL 实例的磁盘使用率达到 100% 或接近上限，导致无法写入数据、无法创建索引、无法执行 DDL 操作。

## 典型症状

- 磁盘使用率 100% 或接近 100%
- 写入数据报错: `Disk full`
- DDL 操作失败: `Table 'xxx' is full`
- Binlog 无法写入
- InnoDB 无法 checkpoint

> 函数参数详见 [api/ops.md](../../api/ops.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|--------|------|----------|------|
| P0 | `describe_table_space` | — | 获取所有库表的数据量和索引大小，定位空间消耗最大的表 |
| P0 | `describe_table_space` | `database="db_name"`, `table_name="table_name"` | 查看特定表的详细空间信息 |
| P1 | `get_metric_data` | `metric_name="DiskUtil"` | 确认磁盘使用率趋势和增长速度 |
| P1 | — | ~~`SHOW BINARY LOGS`~~ 被平台拦截 | Binlog 占用需到**控制台 → 日志管理**查看 |
| P2 | `execute_sql` | `sql="SELECT ... FROM information_schema.FILES WHERE FILE_TYPE='TABLESPACE'"` | 检查 InnoDB 表空间文件大小 |
| P2 | `get_metric_items` | — | 获取支持的监控指标列表，按需选取更多指标 |

## 诊断路径

1. **定位大表** → `describe_table_space` — 找空间消耗最大的表和库
2. **检查 Binlog** — `SHOW BINARY LOGS` 被平台 SQL parser 拦截不可执行；通过 `describe_table_space` 的整体空间占用间接判断 Binlog 是否异常，或到控制台 → 日志管理查看
3. **确认趋势** → MySQL: `get_metric_data(DiskUtil)`；VeDB: 用 `describe_health_summary` — 判断是突发还是持续增长
   - 突发 → 检查是否有大查询/DDL 产生临时文件
   - 持续增长 → 数据增长未配套清理策略
4. **需要清理时** → 旧数据走 `create_dml_sql_change_ticket`，无用索引走 `create_ddl_sql_change_ticket`

## 关键分析维度

- **空间占用分布**：数据 vs 索引 vs Binlog vs 临时文件各占多少
- **增长速度**：通过磁盘使用率趋势判断是突发还是持续增长
- **碎片率**：表碎片空间占比，OPTIMIZE TABLE 可回收
- **Binlog 累积**：Binlog 未清理可能占用大量空间

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|----------|----------|------------|
| 某几张表数据量远超其他表 | 数据快速增长未清理 | 检查表的行数增长趋势和数据保留策略 |
| SHOW BINARY LOGS 显示大量文件 | Binlog 累积未清理 | 检查 `binlog_expire_logs_seconds` 配置 |
| 表数据量不大但空间占用高 | 碎片空间（删除数据后未回收） | 对比 `describe_table_space` 的数据大小与文件大小 |
| 磁盘突然满 + 有大查询/DDL 运行 | 临时表/排序文件占用 | 检查是否有正在执行的大排序或 DDL |
| InnoDB 表空间文件远大于数据量 | Undo/Redo 日志过大 | 检查 `information_schema.FILES` 中的文件大小 |

## 约束与边界

- `execute_sql` 仅支持只读操作，无法执行 `PURGE BINARY LOGS`、`OPTIMIZE TABLE`
- Binlog 清理需到**火山引擎控制台 → 日志管理**操作
- 数据变更（DELETE）须通过 DML 工单执行
- DDL 操作（OPTIMIZE TABLE、DROP INDEX）须通过 DDL 工单执行

## ⚠️ 应急处置（需确认后执行）

### 清理 Binlog

> `execute_sql` 仅支持只读操作，无法执行 `PURGE BINARY LOGS`。需到**火山引擎控制台 → 日志管理**清理 Binlog。

### 删除旧数据

> 数据变更须通过 DML 工单执行。

```python
# 通过 DML 工单归档或删除旧数据
create_dml_sql_change_ticket(client,
    sql_text="DELETE FROM logs WHERE created_at < '2023-01-01';",
    instance_id="mysql-xxx",
    database="db_name",
)
```

### 删除未使用的索引

先查找未使用的索引，再通过 DDL 工单删除：

```python
# 查找未使用的索引（只读查询）
execute_sql(client,
    sql="""
    SELECT
        OBJECT_SCHEMA,
        OBJECT_NAME,
        INDEX_NAME
    FROM performance_schema.table_io_waits_summary_by_index_usage
    WHERE INDEX_NAME IS NOT NULL
    AND COUNT_STAR = 0
    AND OBJECT_SCHEMA != 'mysql';
    """,
    instance_id="mysql-xxx",
    database="performance_schema",
)

# 确认后通过 DDL 工单删除
create_ddl_sql_change_ticket(client,
    sql_text="DROP INDEX idx_name ON table_name;",
    instance_id="mysql-xxx",
    database="db_name",
)
```

## 预防措施

1. 设置磁盘使用率监控和告警
2. 实施数据归档和清理策略
3. 配置 binlog 过期（binlog_expire_logs_seconds）
4. 定期表优化（OPTIMIZE TABLE 回收碎片空间）
5. 监控临时表使用情况
6. 评估是否需要扩容存储（在火山引擎控制台调整实例磁盘规格）
7. 设置空间使用预测

## 关联场景

- [临时表溢出](temp-table-overflow.md)
