# 内存压力故障排查

## 概述

内存压力是指 MySQL 实例的内存使用率持续较高，可能导致 OOM (Out of Memory)、swap 使用、缓存命中率下降等问题。

## 典型症状

- 内存使用率持续 80% 以上
- 系统出现 swap
- InnoDB 缓存命中率下降
- 查询性能下降
- OOM 报错

> 函数参数详见 [api/ops.md](../../api/ops.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|--------|------|----------|------|
| P0 | `get_metric_data` | `metric_name="MemUtil"` | 确认内存使用率和趋势 |
| P0 | `execute_sql` | `sql="SELECT ... FROM information_schema.INNODB_BUFFER_POOL_STATS"` | 查看 InnoDB Buffer Pool 状态（FREE_BUFFERS / DATABASE_PAGES / TOTAL_MEM_ALLOC） |
| P1 | `execute_sql` | `sql="SELECT ... FROM performance_schema.memory_summary_global_by_event_name ORDER BY HIGH_NUMBER_OF_BYTES_USED DESC LIMIT 20"` | 查看各组件内存使用 TOP 20 |
| P1 | `list_connections` | — | 查看活跃连接数，每个连接占用独立内存 |
| P2 | `get_metric_items` | — | 获取支持的监控指标列表，按需选取更多指标 |

## 诊断路径

1. **确认趋势** → MySQL: `get_metric_data(MemUtil)`；VeDB: 用 `describe_health_summary` 看内存环比 — 判断是逐步上涨还是突然飙升
2. **检查 Buffer Pool** → `execute_sql("SELECT ... FROM INNODB_BUFFER_POOL_STATS")` — FREE_BUFFERS 接近 0 说明缓存已满
3. **检查内存分布** → `execute_sql("SELECT ... FROM memory_summary_global_by_event_name")` — 找占用最多的组件
   - sort/join buffer 占比高 → 有大排序/JOIN 操作，转查 `describe_slow_logs`
   - 连接内存占比高 → 查 `list_connections` 确认连接数是否过多
4. **需要处理时** → 终止大查询走 `kill_process`，Buffer Pool 调整走控制台参数管理

## 关键分析维度

- **Buffer Pool 使用率**：FREE_BUFFERS 是否接近 0，说明缓存已满
- **连接数**：每个连接占用 sort_buffer + join_buffer + thread_stack 等独立内存，连接数过多会导致内存压力
- **内存组件分布**：`memory_summary_global_by_event_name` 中哪个组件占用最多（InnoDB、temp table、sort buffer 等）
- **增长趋势**：内存是逐步上涨还是突然飙升，判断是泄漏还是突发大查询

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|----------|----------|------------|
| Buffer Pool FREE_BUFFERS=0 + 缓存命中率下降 | Buffer Pool 配置过小 | 检查 `innodb_buffer_pool_size` 与数据集大小的比例 |
| 连接数高 + 内存持续上涨 | 连接过多消耗内存 | 检查连接数 × per-thread buffer 的总量 |
| `memory_summary` 中 sort/join buffer 占比高 | 大排序/JOIN 操作 | 检查慢查询中是否有大量 filesort / Using temporary |
| 内存缓慢增长不释放 | 内存泄漏（罕见） | 对比不同时间段 `memory_summary`，看是否某组件持续增长 |
| 内存突然飙升 + 某个大查询正在运行 | 大查询消耗内存 | 检查 `list_connections` 中运行时间最长的 SQL |

## 约束与边界

- `execute_sql` 仅支持只读操作，无法执行 `SET GLOBAL` 修改参数
- Buffer Pool 大小调整需到**火山引擎控制台 → 参数管理**修改 `innodb_buffer_pool_size`，或通过**实例扩容**增加内存规格

## ⚠️ 应急处置（需确认后执行）

### 终止大查询

> **警告**：终止查询会导致当前事务失败，请在确认后执行！

```python
# 查找并终止大查询
kill_process(client,
    process_ids=["12345"],
    node_id="node-1",
    instance_id="mysql-xxx",
)
```

## 预防措施

1. 正确配置 innodb_buffer_pool_size
2. 设置适当的连接限制
3. 监控内存使用趋势
4. 优化查询以减少内存消耗
5. 设置 OOM 告警
6. 配置 swap 使用告警

## 关联场景

- [慢查询](slow-query.md)
- [临时表溢出](temp-table-overflow.md)
