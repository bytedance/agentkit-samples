# 持久化阻塞故障排查

## 概述

持久化阻塞是指 Redis 在执行 RDB 快照或 AOF 重写时阻塞主线程，导致读写性能下降。这是 Redis 持久化机制的常见问题，核心原因是 fork 子进程时需要复制页表，数据量越大耗时越长。

## 典型症状

- 写入操作周期性变慢
- 主线程被阻塞（延迟突增）
- `BGSAVE` 或 `BGREWRITEAOF` 执行时间长
- 延迟尖刺与持久化周期吻合

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

| 优先级 | 数据来源 | 命令 | 目的 |
|--------|----------|------|------|
| P0 | `execute_sql` | `INFO persistence` | 查看持久化状态（rdb_last_bgsave_status / aof_rewrite_in_progress / latest_fork_usec） |
| P0 | `execute_sql` | `INFO memory` | 查看内存使用（used_memory，用于评估 fork 耗时） |
| P1 | `execute_sql` | `LASTSAVE` | 获取最后一次 RDB 保存的 UNIX 时间戳 |
| P1 | `execute_sql` | `CONFIG GET save` | 查看 RDB 自动保存配置（触发条件） |
| P2 | `execute_sql` | `CONFIG GET appendfsync` | 查看 AOF 同步策略（always / everysec / no） |

`database` 参数填写需要查询的 Redis DB 编号（如 `"0"`），由 Agent 根据上下文决定。

## 关键分析维度

- **latest_fork_usec**：最近一次 fork 耗时（微秒），通常 1GB 数据 fork 耗时约 20ms，超过 100ms 需关注
- **aof_rewrite_in_progress**：是否有 AOF 重写正在进行
- **rdb_last_bgsave_status**：最近一次 BGSAVE 是否成功
- **appendfsync 策略**：`always` 每次写入都同步，性能最差；`everysec` 每秒同步，平衡选择

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|----------|----------|------------|
| latest_fork_usec > 100000 + used_memory 大 | 数据量大导致 fork 耗时长 | 检查 used_memory 大小，考虑拆分实例 |
| 周期性延迟尖刺 + RDB save 配置频繁 | RDB 自动保存触发过于频繁 | 检查 `CONFIG GET save` 的触发条件 |
| aof_rewrite_in_progress:1 + 延迟升高 | AOF 重写导致阻塞 | 等待重写完成后延迟应恢复 |
| appendfsync:always + 写入延迟高 | 每次写入都做 fsync | 评估是否可切换为 everysec |
| rdb_last_bgsave_status:err + fork 失败 | 内存不足无法 fork（需要 2x 内存） | 检查系统可用内存是否满足 copy-on-write 需求 |

## 约束与边界

- `execute_sql` 仅用于查询类操作，参数修改需到**火山引擎控制台 → 参数管理**
- fork 耗时与数据量正相关，根本解决需要控制单实例数据量

## ⚠️ 应急处置（需确认后执行）

### 切换 AOF 同步策略

> **警告**：修改 `appendfsync` 可能影响数据持久性。需到**火山引擎控制台 → 参数管理**修改，`execute_sql` 仅用于查询。

## 预防措施

1. 使用 AOF 的 `everysec` 策略平衡性能与安全
2. 合理配置 RDB save 触发条件，避免过于频繁
3. 控制单实例数据量（减小 fork 耗时）
4. 监控 fork 时间（latest_fork_usec）
5. 使用从节点承担持久化任务，减少主节点压力
6. 确保系统有足够可用内存应对 copy-on-write

## 关联场景

- [内存打满](memory-full.md)
- [CPU 打满](cpu-spike.md)
