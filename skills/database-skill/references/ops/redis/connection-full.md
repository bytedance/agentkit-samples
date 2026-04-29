# 连接数打满故障排查

## 概述

连接数打满是指 Redis 实例的当前连接数达到 `maxclients` 上限，导致新请求无法建立连接，出现 `max number of clients reached` 错误。

**诊断原则：连接数打满是结果，不是原因。** 排查时必须按客户端 IP、空闲时长等维度分析，定位哪个服务/客户端贡献了异常连接数。

## 典型症状

- 应用报错: `max number of clients reached`
- 无法建立新的数据库连接
- 连接数监控显示达到上限
- 旧连接未被释放，堆积

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

> **注意**：Redis 不支持任何运维诊断函数（`list_connections`、`kill_process`、`describe_health_summary` 等均不可用）。所有诊断信息通过 `execute_sql` 执行 Redis 原生命令获取。

| 优先级 | 命令 | 目的 |
|:---|:---|:---|
| P0 | `INFO clients` | 连接数概览（connected_clients / blocked_clients / maxclients） |
| P0 | `CLIENT LIST` | 全量客户端列表（含 IP、空闲时长、命令等） |
| P1 | `INFO stats` | 总连接创建数（total_connections_received）、命令处理数 |
| P2 | `INFO commandstats` | 排除高耗时命令导致的连接堆积 |

### 原生命令参考

```redis
-- 连接统计概览
INFO clients

-- 全量客户端列表（包含每个连接的详细信息）
-- 关键字段：addr(客户端IP:端口)、idle(空闲秒数)、cmd(最近命令)、age(连接存活秒数)、db(数据库号)
CLIENT LIST

-- 按类型过滤（仅正常客户端，排除主从复制等内部连接）
CLIENT LIST TYPE normal

-- 总连接创建数（判断是否有短连接风暴）
INFO stats
```

> 以上命令均通过 `execute_sql(client, sql="...", instance_id="redis-xxx", database=...)` 执行，`database` 参数由 Agent 根据上下文决定。

## 诊断路径

1. **确认规模** → `INFO clients` — 查看 connected_clients 和 maxclients
   - ⚠️ maxclients 打满时 `execute_sql` 也可能失败（新连接被拒）
2. **拉全量客户端** → `CLIENT LIST TYPE normal` — 按 addr/idle/cmd 分析
   - idle 大的连接占多数 + 集中少数 IP → 连接泄漏
   - 活跃连接多 + IP 分散 → 容量不足
3. **检查短连接** → `INFO stats` 看 total_connections_received — 如果持续快速增长说明有短连接风暴
4. **需要终止时** → `CLIENT KILL ID <id>` 或 `CLIENT KILL ADDR <ip>:<port>`（需用户确认）

## 关键统计维度

`CLIENT LIST` 返回每个连接的详细信息，按以下维度分析：

- **by Client IP**（addr 字段取 IP 部分）：是否来自少数 IP — 定位问题服务器
- **by idle time**：空闲时长分布（0-10s / 10-60s / 1-5min / 5-60min / >1h）— 区分正常空闲和泄漏
- **by cmd**：最近执行的命令类型 — 判断连接用途
- **by age**：连接存活时长 — 长寿命连接是否正常
- **by db**：各数据库号的连接分布

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| idle > 60s 的连接占比 > 70%，集中在少数 IP | 连接泄漏 | 检查对应 IP 的应用连接池配置（maxIdle、minIdle、timeout） |
| 活跃连接多，IP 分散 | 连接池容量不足 | 查 `maxclients` 配置；确认是否需要调大 |
| total_connections_received 持续快速增长 | 短连接风暴 | 应用未使用连接池或连接池配置过小，频繁创建销毁连接 |
| blocked_clients > 0，有大量 BLPOP/BRPOP | 阻塞命令占用连接 | 检查是否有消费者积压，考虑减少阻塞超时时间 |
| 空闲连接多，IP 分散，无明显单点 | 全局空闲超时过大 | 检查 `timeout` 配置（默认 0 = 不超时）和应用侧连接池 idleTimeout |
| 大量连接 cmd=subscribe | Pub/Sub 订阅连接堆积 | 检查是否有僵尸订阅者；Pub/Sub 连接是长连接，正常但需控制数量 |

## 约束与边界

- `execute_sql` 仅用于查询类操作，`CLIENT KILL` 等写操作需到**火山引擎控制台**执行
- `execute_sql` 在连接打满时也可能失败：`maxclients` 打满后新连接被拒绝

## ⚠️ 应急处置（需确认后执行）

### 终止空闲连接

> **警告**：`CLIENT KILL` 等写操作需到**火山引擎控制台**执行，`execute_sql` 仅用于查询。

### 配置空闲超时

> 需到**火山引擎控制台 → 参数管理**修改 `timeout` 参数（建议 300s），设置空闲连接自动断开。

## 预防措施

1. 使用正确的连接池（Jedis, Lettuce 等），配置合理的 maxTotal / maxIdle
2. 配置 `timeout` 参数自动断开空闲连接（建议 300s）
3. 监控 connected_clients 设置告警
4. 审查应用连接生命周期，确保连接正确归还连接池
5. 配置 `client-output-buffer-limit` 防止大输出占满内存
6. 避免短连接模式，使用持久连接池

## 关联场景

- [阻塞命令](blocking-command.md)
