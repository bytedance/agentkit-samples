# 内存压力故障排查

## 概述

内存压力是指 PostgreSQL 实例的内存使用率持续较高，可能导致 OOM、swap 使用、缓存命中率下降、查询性能下降等问题。

## 典型症状

- 内存使用率持续 80% 以上
- 系统出现 swap
- 缓存命中率下降
- 查询性能下降
- OOM 报错

> 函数参数详见 [api/ops.md](../../api/ops.md) 和 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|--------|------|----------|------|
| P0 | `describe_health_summary` | — | 获取最近一小时整体健康状态（含内存使用率、连接数使用率，含环比同比） |
| P0 | `execute_sql` | `sql="SHOW shared_buffers;"` | 查看 Shared Buffers 配置 |
| P1 | `execute_sql` | `sql="SHOW work_mem;"` | 查看 work_mem 配置（每个排序/哈希操作使用的内存上限） |
| P1 | `list_connections` | — | 查看活跃连接数，每个连接占用独立内存 |

## 诊断路径

1. **整体状况** → `describe_health_summary` — 确认内存使用率和环比变化趋势
2. **检查配置** → `execute_sql("SHOW shared_buffers")` + `execute_sql("SHOW work_mem")` — 确认内存分配是否合理
   - shared_buffers 远小于实例总内存 25% → 配置过小
   - work_mem 偏大 + 并发高 → 排序/Hash 操作内存爆炸
3. **检查连接数** → `list_connections` — PG 每连接一个进程，连接多 = 内存消耗线性增长
   - 连接数高 + 未用连接池 → 建议上 PgBouncer
4. **需要处理时** → 终止大查询走 `kill_process`，参数调整走控制台参数管理

## 关键分析维度

- **Shared Buffers 大小**：是否与数据集大小匹配，通常建议为总内存的 25%
- **work_mem 配置**：过大的 work_mem × 高并发连接数 = 内存爆炸
- **连接数**：PostgreSQL 每个连接是独立进程，内存占用比 MySQL 更高
- **增长趋势**：通过 `describe_health_summary` 的环比判断是否持续恶化

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|----------|----------|------------|
| 内存高 + shared_buffers 占比低 | Shared Buffers 配置过小 | 对比 shared_buffers 与实例总内存 |
| 连接数高 + 内存持续上涨 | 连接过多（每连接一个进程） | 检查是否使用连接池（PgBouncer） |
| work_mem 较大 + 并发排序查询多 | 排序操作占用过多内存 | 检查慢查询中是否有大量 Sort/Hash 操作 |
| 内存突然飙升 + 某大查询运行中 | 大查询消耗内存 | 检查 `list_connections` 中运行时间最长的查询 |

## 约束与边界

- PostgreSQL 不支持 `get_metric_items` / `get_metric_data`，通过 `describe_health_summary` 获取整体指标
- `execute_sql` 仅支持只读操作，无法执行 `ALTER SYSTEM SET` 修改参数
- 参数调整需到**火山引擎控制台 → 参数管理**修改，或通过**实例扩容**增加内存规格

## ⚠️ 应急处置（需确认后执行）

### 终止大查询

> **警告**：终止进程会导致当前事务失败，请在确认后执行！

```python
kill_process(client,
    process_ids=["12345"],
    node_id="node-1",
    instance_id="pg-xxx",
)
```

## 预防措施

1. 正确配置 shared_buffers
2. 设置适当的 work_mem
3. 使用连接池（PgBouncer）
4. 监控内存使用趋势
5. 优化查询以减少内存消耗
6. 设置内存使用告警

## 关联场景

- [慢查询](slow-query.md)
