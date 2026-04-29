# 阻塞命令故障排查

## 概述

阻塞命令是指 Redis 中某些命令会长时间阻塞主线程，如 `KEYS`、`FLUSHDB`、`FLUSHALL`、`SORT` 等，导致其他命令无法执行。Redis 采用单线程模型处理命令，一个慢命令会阻塞所有后续请求。

## 典型症状

- 命令执行超时
- 其他命令响应变慢
- 主线程被阻塞
- 客户端超时断开

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

| 优先级 | 数据来源 | 命令 | 目的 |
|--------|----------|------|------|
| P0 | `execute_sql` | `CLIENT LIST` | 查看所有客户端连接状态（age / idle / cmd / flags） |
| P0 | `execute_sql` | `INFO commandstats` | 查看各命令调用次数和平均耗时 |
| P1 | `execute_sql` | `INFO server` | 查看 server 信息（hz / tcp_backlog 等） |

`database` 参数填写需要查询的 Redis DB 编号（如 `"0"`），由 Agent 根据上下文决定。

## 关键分析维度

- **commandstats 中的高频危险命令**：某些命令调用次数多且平均耗时高，关注 `KEYS`、`SORT`、`HGETALL`、`SMEMBERS`、`LRANGE` 等全量遍历命令
- **CLIENT LIST 中的阻塞客户端**：`flags` 包含 `b`（blocked）的客户端，以及 `cmd` 列显示正在执行的命令
- **单线程模型影响范围**：一个阻塞命令会导致所有连接排队等待

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|----------|----------|------------|
| commandstats 中 `KEYS` 调用次数高 | 使用了 KEYS 遍历全量 key | 检查应用代码，替换为 SCAN |
| commandstats 中 `HGETALL` / `SMEMBERS` 平均耗时长 | 操作大 key（hash/set 元素过多） | 用 `MEMORY USAGE <key>` 检查 key 大小 |
| commandstats 中 `SORT` 平均耗时高 | SORT 操作复杂度高 | 检查排序的集合大小和是否有 LIMIT |
| 多个客户端 cmd 列显示同一命令 + idle 高 | Lua 脚本长时间运行阻塞主线程 | 检查是否有复杂 Lua 脚本 |

## 约束与边界

- `execute_sql` 仅用于查询类操作
- `CLIENT KILL` 可终止阻塞客户端，但会导致该客户端当前任务失败
- 无法通过 `execute_sql` 禁用特定命令，需在控制台修改配置

## ⚠️ 应急处置（需确认后执行）

### 终止阻塞客户端

> **警告**：`CLIENT KILL` 等写操作需到**火山引擎控制台**执行，`execute_sql` 仅用于查询。通过 `CLIENT LIST` 定位目标客户端 ID 后，在控制台执行终止。

## 预防措施

1. 避免 KEYS 命令，使用 SCAN 代替
2. 使用 pipeline 批量操作
3. 设置适当的客户端超时
4. 避免在高峰期进行阻塞操作
5. 谨慎使用 Lua 脚本（控制复杂度）
6. 监控命令执行耗时（`INFO commandstats`）

## 关联场景

- [CPU 打满](cpu-spike.md)
- [连接数打满](connection-full.md)
