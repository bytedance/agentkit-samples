# CPU 打满故障排查

## 概述

CPU 打满是指 Redis 实例的 CPU 使用率持续接近或达到 100%，导致响应变慢或完全无响应。Redis 是单线程模型，CPU 打满通常意味着某个命令消耗过多 CPU。

## 典型症状

- CPU 使用率持续 100% 或接近 100%
- 命令响应变慢
- 客户端超时
- 请求堆积

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

| 优先级 | 数据来源 | 命令 | 目的 |
|--------|----------|------|------|
| P0 | `execute_sql` | `INFO commandstats` | 查看各命令调用次数和耗时，定位高频/高耗时命令 |
| P0 | `execute_sql` | `INFO cpu` | 获取 CPU 使用详情（user/sys 时间） |
| P1 | `execute_sql` | `CLIENT LIST` | 查看客户端连接，定位高负载来源 |
| P2 | `execute_sql` | `INFO clients` | 查看连接数统计 |

## 诊断路径

1. **分析命令分布** → `INFO commandstats` — 找调用次数高且平均耗时大的命令
   - 出现 KEYS/HGETALL/SMEMBERS 等全量遍历 → 大 key 或危险命令是根因
3. **定位客户端** → `CLIENT LIST` — 找到发送高耗时命令的客户端 IP
4. **需要终止时** → `CLIENT KILL ID <id>`（需用户确认）

## 关键分析维度

- **命令类型**：`commandstats` 中哪些命令调用次数/平均耗时最高
- **单线程瓶颈**：Redis 单线程模型，一个慢命令会阻塞所有后续请求
- **数据结构大小**：操作的 key 是否为大 key（大 Set/Hash/List）
- **客户端来源**：是否某个客户端发送了大量高复杂度命令

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|----------|----------|------------|
| `commandstats` 中 KEYS 调用次数高 | 使用 KEYS 遍历全量 key | 改用 SCAN 代替 |
| `commandstats` 中 SORT/SUNION/SINTER 平均耗时高 | 大 Set 操作 | 检查涉及 key 的元素数量（`SCARD`） |
| `commandstats` 中 HGETALL 平均耗时高 | 大 Hash 读取 | 检查 Hash 字段数（`HLEN`） |
| EVALSHA/EVAL 占用大量时间 | 复杂 Lua 脚本 | 检查脚本逻辑和执行频率 |
| `commandstats` 中总调用次数突增 | 突发流量 | 确认客户端行为变化 |

## 约束与边界

- `execute_sql` 仅用于查询类操作
- Redis 单线程模型：一个慢命令会阻塞整个实例，`O(N)` 命令在大数据量时尤其危险
- `CLIENT KILL` 只能终止客户端连接，无法终止正在执行的命令

## ⚠️ 应急处置（需确认后执行）

### 终止高 CPU 客户端

> **警告**：`CLIENT KILL` 等写操作需到**火山引擎控制台**执行，`execute_sql` 仅用于查询。通过 `CLIENT LIST` 定位目标客户端 ID 后，在控制台执行终止。

## 预防措施

1. 避免 KEYS 命令，使用 SCAN 代替
2. 使用适当的数据结构
3. 设置命令超时
4. 监控命令执行耗时（`INFO commandstats`）
5. 使用 pipeline 批量操作
6. 设置 CPU 使用告警

## 关联场景

- [阻塞命令](blocking-command.md)
- [内存打满](memory-full.md)
