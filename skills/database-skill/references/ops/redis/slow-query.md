# 慢查询 / 大 Key 故障排查

## 概述

Redis 响应变慢通常由以下原因导致：大 Key 操作（HGETALL/SMEMBERS 读取大量元素）、复杂命令（KEYS/SORT/EVAL）、或突发流量。Redis 单线程模型下，一个慢命令会阻塞所有后续请求。

## 典型症状

- 响应偶尔变慢（不是持续慢）
- 客户端超时
- 某些接口延迟波动大

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

> Redis 不支持 `describe_slow_logs` 等运维诊断 API，所有排查通过 `execute_sql`（Redis 命令）进行。

| 优先级 | 数据来源 | 命令 | 目的 |
|--------|----------|------|------|
| P0 | `execute_sql` | `SLOWLOG GET 20` | 查看最近 20 条慢命令（命令名、耗时、参数） |
| P0 | `execute_sql` | `INFO commandstats` | 各命令的调用次数和平均耗时，定位高耗时命令类型 |
| P1 | `execute_sql` | `MEMORY USAGE <key>` | 检查疑似大 Key 的内存占用（字节） |
| P1 | `execute_sql` | `SCARD <key>` / `HLEN <key>` / `LLEN <key>` / `ZCARD <key>` | 检查集合类 Key 的元素数量 |
| P2 | `execute_sql` | `INFO memory` | 查看整体内存使用情况 |

## 诊断路径

1. **查慢日志** → `SLOWLOG GET 20` — 看最近的慢命令是什么、耗时多少、操作哪些 key
   - 出现 HGETALL / SMEMBERS / LRANGE / ZRANGEBYSCORE → 可能是大 Key 操作，**必须执行步骤 3 验证**
   - 出现 KEYS / SORT / EVAL → 复杂命令阻塞
2. **分析命令分布** → `INFO commandstats` — 找平均耗时（`usec_per_call`）高的命令
   - HGETALL / SMEMBERS / LRANGE / ZRANGE 等集合读取命令平均耗时 > 1ms → 大 Key 嫌疑，**必须执行步骤 3 验证**
   - EVAL 平均耗时 > 100ms → Lua 脚本复杂度问题
   - 可能同时存在多个问题（如 EVAL 慢 + 大 Key），每个高耗时命令类型都要分析
3. **验证大 Key**（当步骤 1 或 2 发现集合类命令耗时异常时，**必须执行此步骤**，不能仅推断"可能是大 Key"） → 从慢日志中提取具体 key 名，逐个检查：
   - `MEMORY USAGE <key>` — 超过 1MB 即为大 Key
   - `HLEN <key>` / `SCARD <key>` / `LLEN <key>` / `ZCARD <key>` — 元素数超过 10000 即需关注
   - `TYPE <key>` — 确认 key 的数据类型
   - 如果慢日志中无具体 key 名，用 `SCAN 0 COUNT 100` 采样后逐个检查 `MEMORY USAGE`
4. **定位来源** → `CLIENT LIST` — 找到发送慢命令的客户端 IP

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|----------|----------|------------|
| SLOWLOG 中大量 HGETALL + 同一 key | 大 Hash Key 全量读取 | `HLEN` 确认字段数，`MEMORY USAGE` 确认大小 |
| SLOWLOG 中大量 SMEMBERS / SUNION | 大 Set Key 操作 | `SCARD` 确认元素数 |
| commandstats 中 EVAL 平均耗时极高 | Lua 脚本阻塞主线程 | 检查脚本逻辑和调用频率 |
| commandstats 中 KEYS 调用次数高 | KEYS 遍历全量 key | 改用 SCAN 代替 |
| SLOWLOG 中 LRANGE 0 -1 或大范围 | 大 List 全量读取 | `LLEN` 确认长度 |
| 偶发性超时 + SLOWLOG 中出现大 Key 操作 | 大 Key 读取间歇性阻塞 | 确认业务访问模式（定时任务？缓存刷新？） |

## 约束与边界

- `execute_sql` 仅用于查询类操作
- `SLOWLOG GET` 返回的是 Redis 本地慢日志（由 `slowlog-log-slower-than` 参数控制阈值），不同于平台侧的慢查询分析
- `MEMORY USAGE` 需逐 key 检查，无法批量扫描所有大 Key
- 修改 `slowlog-log-slower-than` 等参数需到**火山引擎控制台**操作

## 预防措施

1. 避免全量读取大 Key（HGETALL → HSCAN，SMEMBERS → SSCAN，LRANGE 0 -1 → 分批 LRANGE）
2. 拆分大 Key（Hash 按前缀分桶，List 按时间分段）
3. 设置大 Key 告警
4. 避免 KEYS 命令，使用 SCAN 代替
5. Lua 脚本控制复杂度，避免长时间阻塞

## 关联场景

- [CPU 打满](cpu-spike.md)
- [阻塞命令](blocking-command.md)
- [内存打满](memory-full.md)
