# 磁盘空间不足故障排查

## 概述

磁盘空间不足是指 PostgreSQL 实例的磁盘使用率达到 100% 或接近上限，导致无法写入数据、无法创建索引、WAL 无法写入。

## 典型症状

- 磁盘使用率 100% 或接近 100%
- 写入数据报错
- DDL 操作失败
- WAL 无法写入

> 函数参数详见 [api/ops.md](../../api/ops.md) 和 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|--------|------|----------|------|
| P0 | `describe_table_space` | — | 获取所有库表的数据量和索引大小，定位空间消耗最大的表 |
| P0 | `describe_health_summary` | — | 获取最近一小时整体健康状态，了解整体负载和趋势 |
| P1 | `execute_sql` | `sql="SELECT pg_current_wal_lsn(), ..."` | 检查 WAL 使用情况和增长 |
| P1 | `describe_table_space` | `database="db_name"`, `table_name="table_name"` | 查看特定表的详细空间信息 |

## 诊断路径

1. **定位大表** → `describe_table_space` — 找空间消耗最大的表和库
2. **检查 WAL** → `execute_sql("SELECT pg_current_wal_lsn(), ...")` — WAL 累积是 PG 常见空间大户
   - WAL 快速增长 → 检查复制状态和归档进程
3. **检查膨胀** → `execute_sql("SELECT ... FROM pg_stat_user_tables WHERE n_dead_tup > ...")` — dead tuple 多说明需要 VACUUM
   - 表数据不大但空间占用高 → 碎片/膨胀，走 DDL 工单执行 VACUUM
4. **需要清理时** → VACUUM 走 `create_ddl_sql_change_ticket`，旧数据走 `create_dml_sql_change_ticket`

## 关键分析维度

- **空间占用分布**：数据 vs 索引 vs WAL vs 临时文件各占多少
- **表膨胀**：dead tuple 比例高说明需要 VACUUM
- **WAL 累积**：WAL 日志积压可能占用大量空间（复制延迟、归档失败）
- **索引膨胀**：索引大小与数据量不成比例，可能需要 REINDEX

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|----------|----------|------------|
| 某几张表空间占用远超其他表 | 数据快速增长未清理 | 检查表的行数和数据保留策略 |
| WAL LSN 快速增长 | WAL 累积（复制延迟/归档失败） | 检查复制状态和归档进程 |
| 表数据量不大但空间占用高 | 表膨胀（dead tuple 未回收） | 检查 `pg_stat_user_tables` 的 n_dead_tup |
| 索引大小远超数据大小 | 索引膨胀 | 对比索引大小与表数据大小的比例 |
| VACUUM 长时间未完成 | VACUUM 被阻塞或进度缓慢 | 检查 `pg_stat_progress_vacuum` |

## 约束与边界

- PostgreSQL 不支持 `get_metric_items` / `get_metric_data`，通过 `describe_health_summary` 获取整体指标
- `execute_sql` 仅支持只读操作，无法执行 `VACUUM`、`REINDEX`
- `VACUUM` 须通过 DDL 工单执行
- 数据变更（DELETE）须通过 DML 工单执行

## ⚠️ 应急处置（需确认后执行）

### 回收空间

> `execute_sql` 仅支持只读操作，`VACUUM` 须通过 DDL 工单执行。

```python
# 通过 DDL 工单执行 VACUUM
create_ddl_sql_change_ticket(client,
    sql_text="VACUUM (VERBOSE, ANALYZE) table_name;",
    instance_id="pg-xxx",
    database="db_name",
)
```

### 删除旧数据

> 数据变更须通过 DML 工单执行。

```python
# 通过 DML 工单归档或删除旧数据
create_dml_sql_change_ticket(client,
    sql_text="DELETE FROM logs WHERE created_at < '2023-01-01';",
    instance_id="pg-xxx",
    database="db_name",
)
```

## 预防措施

1. 设置磁盘使用率监控和告警
2. 实施数据归档和清理策略
3. 定期 VACUUM（启用 AUTOVACUUM）
4. 监控 WAL 增长
5. 使用表分区
6. 评估是否需要扩容存储（在火山引擎控制台调整实例磁盘规格）
7. 设置空间使用预测

## 关联场景

- [WAL 积压](wal-backlog.md)
- [VACUUM 阻塞](vacuum-blocking.md)
