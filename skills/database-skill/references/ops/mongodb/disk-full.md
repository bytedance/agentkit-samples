# 磁盘空间不足故障排查

## 概述

磁盘空间不足是指 MongoDB 实例的磁盘使用率达到 100% 或接近上限，导致无法写入数据、无法创建索引、WiredTiger 无法 checkpoint。

## 典型症状

- 磁盘使用率 100% 或接近 100%
- 写入数据报错
- 无法创建索引
- WiredTiger checkpoint 失败

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

> MongoDB 不支持 `describe_table_space`，通过 `execute_sql` 执行 `db.stats()` 等原生命令获取存储信息。函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

| 优先级 | 数据来源 | 命令 | 目的 |
|--------|----------|------|------|
| P0 | `execute_sql` | `db.stats();` | 获取整个实例的存储统计（dataSize / storageSize / indexSize） |
| P0 | `execute_sql` | `db.getCollectionNames().map(function(c) { var s = db.getCollection(c).stats(); return { collection: c, size_mb: Math.round(s.size/1024/1024), storage_mb: Math.round(s.storageSize/1024/1024), index_mb: Math.round(s.totalIndexSize/1024/1024), count: s.count }; }).sort(function(a,b) { return b.storage_mb - a.storage_mb; });` | 按集合查看空间占用排名 |
| P1 | `execute_sql` | `db.getReplicationInfo();` | 检查 oplog 占用空间和时间窗口 |
| P2 | `execute_sql` | `db.serverStatus().wiredTiger.cache;` | 查看 WiredTiger 缓存状态 |

P0 命令的 `database` 参数使用目标数据库名；P1/P2 命令使用 `"local"` 或 `"admin"`。

## 关键分析维度

- **dataSize vs storageSize**：storageSize 远大于 dataSize 说明存在大量碎片或已删除数据未回收
- **各集合空间排名**：定位占用空间最大的集合
- **索引空间占比**：totalIndexSize 过大说明索引过多或冗余
- **oplog 占用**：oplog 大小是否合理，时间窗口是否足够

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|----------|----------|------------|
| 单个集合 storage_mb 远超其他 | 该集合数据量过大或未清理 | 检查该集合是否有 TTL 索引或归档策略 |
| storageSize 远大于 dataSize | 大量删除后空间未回收（WiredTiger 碎片） | 考虑对集合执行 compact |
| oplog 占比高 + 写入频繁 | oplog 过大 | 检查 oplog 时间窗口，评估是否需要缩小 |
| index_mb 占总空间 > 30% | 索引过多或冗余 | 检查是否有未使用的索引 |
| 空间突然快速增长 | 大批量写入或导入 | 检查最近的写入操作和数据变更 |

## 约束与边界

- MongoDB 不支持 `describe_table_space`，需通过 `execute_sql` 执行 `db.stats()` 等原生命令获取存储信息
- `execute_sql` 仅用于查询类操作，`compact` 等写操作需到火山引擎控制台执行
- 磁盘扩容需到火山引擎控制台调整实例规格

## ⚠️ 应急处置（需确认后执行）

### 压缩集合

> **警告**：`compact` 会锁定集合，需到**火山引擎控制台**或通过运维工单执行。`execute_sql` 仅用于查询类操作。

## 预防措施

1. 设置磁盘使用率监控和告警
2. 实施数据归档和清理策略
3. 监控集合大小
4. 使用 TTL 索引自动清理过期数据
5. 定期压缩回收碎片空间
6. 评估是否需要扩容存储（在火山引擎控制台调整实例磁盘规格）

## 关联场景

- [慢查询](slow-query.md)
