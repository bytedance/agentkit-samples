# 内存打满故障排查

## 概述

内存打满是指 Redis 实例的内存使用率达到 `maxmemory` 上限，导致 OOM (Out of Memory) 错误，无法写入新数据。

## 典型症状

- 内存使用率 100% 或达到 maxmemory 上限
- 写入数据报错: `OOM command not allowed when used memory`
- 内存监控显示持续高水位
- 数据被驱逐（如果配置了驱逐策略）

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

| 优先级 | 数据来源 | 命令 | 目的 |
|--------|----------|------|------|
| P0 | `execute_sql` | `INFO memory` | 获取内存详情（used_memory / maxmemory / fragmentation_ratio） |
| P0 | `execute_sql` | `INFO keyspace` | 查看各 db 的 key 数量，定位数据集中的 db |
| P1 | `execute_sql` | `CONFIG GET maxmemory-policy` | 查看驱逐策略（noeviction 则不驱逐，写入直接报错） |
| P1 | `execute_sql` | `INFO clients` | 查看客户端连接数和输出缓冲区内存占用 |
| P2 | `execute_sql` | `DBSIZE` | 获取当前 db 的 key 总数 |

`database` 参数填写需要查询的 Redis DB 编号（如 `"0"`），由 Agent 根据上下文决定。

## 诊断路径

1. **确认内存状况** → `INFO memory` — 对比 used_memory 和 maxmemory，检查 mem_fragmentation_ratio
   - fragmentation_ratio > 1.5 → 碎片严重，考虑 `MEMORY PURGE` 或重启
2. **定位数据分布** → `INFO keyspace` — 找 key 数量最多的 db
3. **检查驱逐策略** → `CONFIG GET maxmemory-policy` — noeviction 则写入直接报错
4. **排查大 key** → 对可疑 key 用 `MEMORY USAGE <key>` 抽样 — 大 key 是内存高的常见原因
5. **检查客户端** → `INFO clients` — 输出缓冲区可能消耗大量内存

## 关键分析维度

- **used_memory vs maxmemory**：used_memory 接近或超过 maxmemory 时触发驱逐或 OOM
- **内存碎片率**（mem_fragmentation_ratio）：> 1.5 说明碎片严重，实际可用内存小于物理内存
- **驱逐策略**：`noeviction` 策略下内存满后直接拒绝写入；其他策略会淘汰旧数据
- **key 分布**：哪个 db 的 key 最多，是否存在大 key

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|----------|----------|------------|
| key 数量持续增长 + 无 TTL | 数据增长未及时清理 | 检查 key 是否设置了 TTL |
| 某个 db key 数量异常多 | 大 key 或大量小 key 堆积 | 用 `MEMORY USAGE <key>` 抽样检查 |
| mem_fragmentation_ratio > 1.5 | 内存碎片严重 | 考虑重启实例或使用 `MEMORY PURGE` |
| clients 输出缓冲区占用大 | 客户端输出缓冲区泄漏 | 检查是否有大量 SUBSCRIBE 或 MONITOR 连接 |
| used_memory 高但 key 数量少 | 大 key 占用 | 排查大 key（参考大 Key SOP） |

## 约束与边界

- `execute_sql` 仅用于查询类操作，`FLUSHDB`、`CONFIG SET` 等写操作需到**火山引擎控制台**执行

## ⚠️ 应急处置（需确认后执行）

### 清空数据库

> **警告**：`FLUSHDB` 会删除所有数据，需到**火山引擎控制台**执行，`execute_sql` 仅用于查询。

### 调整 maxmemory

> 需到**火山引擎控制台 → 参数管理**修改 `maxmemory` 参数，或通过扩容实例规格增加内存。

## 预防措施

1. 设置内存监控和告警
2. 对 key 使用 TTL
3. 实施数据清理策略
4. 监控大 key
5. 使用适当的驱逐策略
6. 设置内存使用预测

## 关联场景

- [CPU 打满](cpu-spike.md)
