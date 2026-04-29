# 内存压力故障排查

## 概述

内存压力是指 MongoDB 实例的内存使用率持续较高，可能导致 OOM、WiredTiger 缓存命中率下降、查询性能下降等问题。

## 典型症状

- 内存使用率持续 80% 以上
- WiredTiger 缓存命中率下降
- 查询性能下降
- OOM 报错

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

| 优先级 | 数据来源 | 命令 | 目的 |
|--------|----------|------|------|
| P0 | `execute_sql` | `db.serverStatus().mem;` | 获取内存使用详情（resident / virtual / mapped） |
| P0 | `execute_sql` | `db.serverStatus().wiredTiger.cache;` | 查看 WiredTiger 缓存使用情况（已用/最大/脏页比例） |
| P1 | `execute_sql` | `db.serverStatus().connections;` | 查看连接数统计 |
| P2 | `execute_sql` | `db.serverStatus().wiredTiger.concurrentTransactions;` | 查看并发事务情况 |

所有命令的 `database` 参数使用 `"admin"`。

## 关键分析维度

- **WiredTiger Cache 使用率**：`bytes currently in the cache` / `maximum bytes configured` 的比例，超过 80% 需关注
- **脏页比例**：脏页占比过高说明写入压力大，eviction 跟不上
- **连接数**：每个连接占用独立内存栈（约 1MB），连接过多会消耗大量内存
- **resident vs virtual**：resident 是实际物理内存占用，virtual 包含映射文件

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|----------|----------|------------|
| WiredTiger cache 使用率 > 95% + 查询变慢 | WiredTiger Cache 配置过小 | 默认为总内存的 50%-60%，检查是否被手动调小 |
| 连接数高 + resident 内存持续上涨 | 连接过多消耗内存 | 检查应用是否正确使用连接池 |
| 脏页比例高 + eviction 频繁 | 写入压力大，eviction 跟不上 | 检查写入 QPS 和操作类型 |
| resident 内存突然飙升 + 某大查询运行中 | 大查询消耗内存（全集合扫描/大排序） | 检查 `db.currentOp()` 中运行时间最长的操作 |

## 约束与边界

- `execute_sql` 仅用于查询类操作，无法修改配置参数
- WiredTiger Cache 大小通常通过实例规格决定，调整需到火山引擎控制台

## 预防措施

1. 正确配置 WiredTiger 缓存大小
2. 设置适当的连接限制
3. 监控内存使用趋势
4. 优化查询以减少内存消耗
5. 设置内存使用告警
6. 使用投影限制数据传输

## 关联场景

- [慢查询](slow-query.md)
