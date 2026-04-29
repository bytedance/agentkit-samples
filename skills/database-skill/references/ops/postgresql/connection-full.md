# 连接数打满故障排查

## 概述

连接数打满是指 PostgreSQL 实例的当前连接数达到 `max_connections` 上限，导致新请求无法建立连接，出现 `sorry, too many clients already` 错误。

**诊断原则：连接数打满是结果，不是原因。** 排查时必须按用户、来源 IP、状态等维度分组统计，定位哪个服务/客户端贡献了异常连接数，而不是只看总数。

## 典型症状

- 应用报错: `sorry, too many clients already`
- 无法建立新的数据库连接
- 连接数监控显示达到上限
- 旧连接未被释放，堆积

> 函数参数详见 [api/ops.md](../../api/ops.md)。

## 必看数据

> **重要约束**：连接数打满时，`execute_sql` 也需要建立新连接，会直接报 `sorry, too many clients already` 失败。以下函数优先使用管理 API，它们不占用数据库连接，连接打满时仍可正常调用。

| 优先级 | 函数 | 关键参数 | 目的 |
|:---|:---|:---|:---|
| P0 | `describe_health_summary` | `diag_type="ALL"` | 连接使用率概览（⚠️ 不含 idle 连接） |
| P0 | `list_connections` | **`show_sleep=True`** | 全量连接（含 idle），数据量大时自动返回 `stats` 统计摘要 |
| P1 | `list_history_connections` | 对比 1h 前 / 6h 前，`show_sleep=True` | 趋势对比，判断是突增还是持续增长 |
| P2 | `describe_lock_wait` | — | 排除锁等待导致的连接堆积 |
| P2 | `describe_aggregate_slow_logs` | 最近 1h | 排除慢查询导致的连接堆积 |

> PostgreSQL 不支持 `get_metric_items` / `get_metric_data`，无法通过监控 API 获取连接数时序趋势。
>
> `max_connections` 的精确值需到**火山引擎控制台 → 参数管理**查看，连接打满时无法通过 `execute_sql` 查询。

## 诊断路径

1. **确认规模** → `describe_health_summary` 看连接使用率 — ⚠️ 不含 idle，仅作初筛
2. **拉全量连接** → `list_connections(show_sleep=True)` — 从 `stats` 摘要判断模式：
   - idle > 70% 且集中单用户 → 连接泄漏方向
   - 大量 `idle in transaction` → 事务未提交导致堆积，检查 `idle_in_transaction_session_timeout`
   - 活跃 > 50% → 不是泄漏，转查慢查询或锁等待
3. **对比历史** → `list_history_connections(show_sleep=True)` — 区分突增 vs 持续增长
4. **需要终止时** → 按条件（`command_type`/`min_time`）或精确（`process_ids` + `node_id`）调 `kill_process`

## 关键统计维度

`list_connections` 返回数据量大时自动包含 `stats` 统计摘要（by_command、by_user_top10、by_db_top10、by_ip_top10、by_time_bucket 等），按以下维度分析：

- **by Command**：idle vs 活跃的比例 — 判断是空闲堆积还是负载过高
- **by User**：是否集中在少数用户 — 判断是单应用泄漏还是全局问题
- **by Host/IP**：是否来自少数 IP — 定位问题服务器
- **by Database**：哪个库连接最多 — 缩小排查范围
- **by Time Bucket**：空闲时长分布（0-10s / 10-60s / 1-5min / 5-60min / >1h）— 区分正常空闲和泄漏

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| idle > 70%，集中单用户(>40%)，avg 空闲 > 5min | 连接泄漏 | 查 `list_history_connections` 是否持续增长；检查该用户对应的应用连接池配置 |
| 活跃 > 50%，多用户分散 | 连接池容量不足 | 查 `max_connections` 配置；确认是否有扩容空间 |
| 大量 idle in transaction 状态 | 事务未提交导致堆积 | 查 `describe_lock_wait`；检查 `idle_in_transaction_session_timeout` 配置 |
| 活跃连接执行时间普遍 > 60s | 慢查询阻塞 | 查 `describe_aggregate_slow_logs` |
| idle > 70%，用户分散，无明显单点 | 全局空闲超时过大 | 检查 `idle_in_transaction_session_timeout` 和 `idle_session_timeout`（PG 14+）配置 |
| 短时间连接数翻倍，伴随错误日志 | 应用重连风暴 | 查 `describe_err_logs` 看是否有大量连接错误 |

## 约束与边界

- **PostgreSQL 不支持 `get_metric_items` / `get_metric_data`**，连接数时序只能通过 `list_history_connections` 对比不同时间段快照来推断趋势
- **连接数使用率**（`describe_health_summary`）= 活跃会话数 / max_connections，不含 idle 连接
- **kill_process**：必须经过用户明确确认后才能执行
- **数据量**：`list_connections` 数据量大时自动计算统计摘要并落盘全量数据到 `artifact_path`
- **idle in transaction**：PostgreSQL 特有状态，表示事务已开始但未提交/回滚，会持有锁并占用连接

## ⚠️ 应急处置（需确认后执行）

### 终止空闲连接

> **警告**：终止进程会导致当前事务失败，请在确认后执行！

```python
# 按条件终止：终止所有空闲超过 300 秒的连接
kill_process(client,
    command_type="Sleep",
    min_time=300,
    instance_id="pg-xxx",
)

# 精确终止：终止指定进程
kill_process(client,
    process_ids=["12345", "12346"],
    node_id="node-1",
    instance_id="pg-xxx",
)
```

## 预防措施

1. 使用连接池中间件（PgBouncer, Pgpool-II）
2. 设置适当的连接超时
3. 监控并终止长时间空闲的连接
4. 设置连接数告警
5. 审查应用连接生命周期
6. 配置 `idle_in_transaction_session_timeout` 自动终止长时间未提交的事务连接

## 关联场景

- [慢查询](slow-query.md)
