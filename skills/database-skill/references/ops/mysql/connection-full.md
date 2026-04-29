# 连接数打满故障排查

## 概述

连接数打满是指 MySQL 实例的当前连接数达到 `max_connections` 上限，导致新请求无法建立连接，出现 `Too many connections` 错误。

**诊断原则：连接数打满是结果，不是原因。** 排查时必须按用户、来源 IP、状态等维度分组统计，定位哪个服务/客户端贡献了异常连接数，而不是只看总数。

> **VeDB 注意**：
> - 不支持 `get_metric_items` / `get_metric_data`，跳过监控指标步骤，直接用 `list_connections` 获取连接总数
> - `list_connections` 自动查所有节点并合并，注意区分读写节点的连接分布
> - `describe_health_summary` 可用，但连接数使用率口径为活跃连接（不含 Sleep）

## 典型症状

- 应用报错: `Too many connections`
- 无法建立新的数据库连接
- 连接数监控显示达到上限
- 旧连接未被释放，堆积

> 函数参数详见 [api/ops.md](../../api/ops.md)。

## 必看数据

> **重要约束**：连接数打满时，`execute_sql` 也需要建立新连接，会直接报 `Too many connections` 失败。以下函数优先使用管理 API，它们不占用数据库连接，连接打满时仍可正常调用。

| 优先级 | 函数 | 关键参数 | 目的 |
|:---|:---|:---|:---|
| P0 | `describe_health_summary` | `diag_type="ALL"` | 连接使用率概览（⚠️ 不含 Sleep 连接） |
| P0 | `list_connections` | **`show_sleep=True`** | 全量连接（含 Sleep），数据量大时自动返回 `stats` 统计摘要 |
| P1 | `get_metric_items` → `get_metric_data` | `metric_name="ThreadsConnected"` | 连接数时序趋势（仅 MySQL，VeDB 不支持） |
| P1 | `list_history_connections` | 对比 1h 前 / 6h 前，`show_sleep=True` | 趋势对比，判断是突增还是持续增长 |
| P2 | `describe_lock_wait` | — | 排除锁等待导致的连接堆积 |
| P2 | `describe_aggregate_slow_logs` | 最近 1h | 排除慢查询导致的连接堆积 |

> `max_connections` 的精确值需到**火山引擎控制台 → 参数管理**查看，连接打满时无法通过 `execute_sql` 查询。

## 诊断路径

1. **确认规模** → `describe_health_summary` 看连接使用率 — ⚠️ 不含 Sleep，仅作初筛
2. **拉全量连接** → `list_connections(show_sleep=True)` — 从 `stats` 摘要判断模式：
   - Sleep > 70% 且集中单用户 → 连接泄漏方向
   - 活跃 > 50% → 不是泄漏，转查慢查询或锁等待
3. **对比历史** → `list_history_connections(show_sleep=True)` — 区分突增 vs 持续增长
   - 突增 + 伴随错误日志 → 查 `describe_err_logs` 确认是否重连风暴
4. **需要终止时** → 从 `list_connections` 获取目标会话信息，按条件（`command_type`/`users`/`min_time`）或精确（`process_ids` + `node_id`）调 `kill_process`

## 关键统计维度

`list_connections` 返回数据量大时自动包含 `stats` 统计摘要（by_command、by_user_top10、by_db_top10、by_ip_top10、by_time_bucket 等），按以下维度分析：

- **by Command**：Sleep vs 活跃的比例 — 判断是空闲堆积还是负载过高
- **by User**：是否集中在少数用户 — 判断是单应用泄漏还是全局问题
- **by Host/IP**：是否来自少数 IP — 定位问题服务器
- **by Database**：哪个库连接最多 — 缩小排查范围
- **by Time Bucket**：空闲时长分布（0-10s / 10-60s / 1-5min / 5-60min / >1h）— 区分正常空闲和泄漏

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| Sleep > 70%，集中单用户(>40%)，avg 空闲 > 5min | 连接泄漏 | 查 `list_history_connections` 是否持续增长；检查该用户对应的应用连接池配置 |
| 活跃 > 50%，多用户分散 | 连接池容量不足 | 查 `max_connections` 配置；确认是否有扩容空间 |
| 大量 Locked / Waiting for lock 状态 | 锁等待导致堆积 | 查 `describe_lock_wait` |
| 活跃连接执行时间普遍 > 60s | 慢查询阻塞 | 查 `describe_aggregate_slow_logs` |
| Sleep > 70%，用户分散，无明显单点 | 全局 wait_timeout 过大 | 检查 `wait_timeout` 配置（默认 28800s = 8h） |
| 短时间连接数翻倍，伴随错误日志 | 应用重连风暴 | 查 `describe_err_logs` 看是否有大量连接错误 |

## 约束与边界

- **VeDB**：不支持 `get_metric_items` / `get_metric_data`，跳过监控指标，直接用 `list_connections` 获取连接总数
- **VeDB**：`list_connections` 自动查所有节点并合并，注意区分读写节点的连接分布
- **连接数使用率**（`describe_health_summary`）= 活跃会话数 / max_connections，不含 Sleep 连接
- **kill_process**：必须经过用户明确确认后才能执行
- **数据量**：`list_connections` 数据量大时自动计算统计摘要并落盘全量数据到 `artifact_path`

## 修复建议（排查后必须给出）

排查完成后，**必须**向用户提供具体可操作的修复方案，从以下常见方案中选择：

1. **终止空闲连接** — 通过 `kill_process` 批量终止 Sleep 状态超过阈值的连接
2. **调整 max\_connections** — 临时或永久提升最大连接数上限
3. **优化连接池配置** — 建议调整应用侧连接池参数（最大连接数、空闲超时、最小连接数）
4. **实例扩容** — 在火山引擎控制台升级实例规格以支持更多连接
5. **配置 wait\_timeout** — 设置合理的空闲连接自动断开时间

## ⚠️ 应急处置（需确认后执行）

### 终止空闲连接

> **警告**：终止连接会导致当前事务失败，请在确认后执行！

```python
# 按条件终止：终止所有 Sleep 超过 300 秒的空闲连接
kill_process(client,
    command_type="Sleep",
    min_time=300,
    instance_id="mysql-xxx",
)

# 按条件终止：终止指定用户的全部连接
kill_process(client,
    users="leak_user",
    instance_id="mysql-xxx",
)

# 精确终止：终止指定进程
kill_process(client,
    process_ids=["12345", "12346"],
    node_id="node-1",
    instance_id="mysql-xxx",
)
```

### 增加 max\_connections

> `execute_sql` 仅支持只读操作，无法执行 `SET GLOBAL` 或 `FLUSH`。需到**火山引擎控制台 → 参数管理**修改 `max_connections` 等参数。

## 预防措施

1. 使用正确的连接池（HikariCP, Druid 等）
2. 设置适当的连接超时
3. 监控并终止长时间空闲的连接
4. 设置连接数告警
5. 审查应用连接生命周期
6. 配置 `wait_timeout` 和 `interactive_timeout`

## 关联场景

- [会话堆积](session-pileup.md)
- [慢查询](slow-query.md)
