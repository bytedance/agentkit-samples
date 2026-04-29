# 会话堆积故障排查

## 概述

活跃会话堆积是指大量连接处于活跃状态（Sleep/Waiting），导致连接数资源耗尽，响应变慢。

## 典型症状

- 活跃连接数持续较高
- 很多连接处于 Sleep 状态
- 连接数接近上限
- 响应时间变长

> 函数参数详见 [api/ops.md](../../api/ops.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|:---|:---|:---|:---|
| P0 | `list_connections` | `show_sleep=True` | 查看全部会话（含 Sleep），按用户/状态/DB 分析分布 |
| P0 | `get_metric_data` | `metric_name="ThreadsConnected"`, `period=60` | 连接数趋势，判断是突增还是持续增长 |
| P1 | `list_history_connections` | `show_sleep=True` | 历史会话快照，与当前对比判断是泄漏还是突发 |
| P1 | `describe_slow_logs` | `order_by="QueryTime"` | 慢查询是否导致会话堆积 |
| P2 | `get_metric_items` | — | 获取支持的监控指标列表，按需选取更多指标 |

## 诊断路径

1. **拉全量会话** → `list_connections(show_sleep=True)` — 从 `stats` 摘要判断 Sleep vs 活跃分布
2. **判断模式** →
   - Sleep 多 + 集中单用户 + avg time 长 → 连接泄漏，重点查该用户
   - Query 状态堆积 + 相同 SQL → 慢查询导致，转查 `describe_slow_logs`
   - Waiting for lock 多 → 锁等待导致，转查 `describe_lock_wait`
3. **对比历史** → `list_history_connections` — 区分突增 vs 持续增长（MySQL 可补充 `get_metric_data(ThreadsConnected)` 看时序趋势）
4. **需要终止时** → 按条件（`command_type`/`users`/`min_time`）或精确（`process_ids` + `node_id`）调 `kill_process`

## 关键分析维度

拿到 `list_connections` 数据后，按以下维度分组统计：

- **by command（状态）**：Sleep / Query / Execute 各多少 — Sleep 多说明连接池未回收
- **by user（用户）**：哪个用户连接最多，avg 持有时间多长
- **by db（数据库）**：是否集中在某个库
- **by host（来源 IP）**：是否集中在某个应用节点
- **by time（执行时间分布）**：0-10s / 10-60s / 1-5min / 5-60min / >1h 各多少

**判断泄漏 vs 突发**：avg 持有时间短（< 10s）= 正常短查询；avg 持有时间长（> 60s）+ Sleep 多 = 疑似连接泄漏。

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| 大量 Sleep 连接 + avg time > 60s + 集中在某个用户 | 应用连接泄漏（未正确关闭） | 检查该用户对应应用的连接池配置 |
| Query 状态会话突增 + 相同 SQL 模板 | 慢查询导致请求堆积 | `describe_slow_logs` 查看对应 SQL |
| 连接数持续缓慢增长（从历史快照看） | 连接池 maxIdle 配置过大 | 对比 `list_history_connections` 的趋势 |
| 多个来源 IP 同时堆积 | 后端服务扩容或流量激增 | 确认是否有业务发布或扩容操作 |
| 大量 Waiting for lock 状态 | 锁等待导致连接堆积 | 转到[锁等待](lock-wait.md)排查 |

## 约束与边界

- `get_metric_data` / `get_metric_items` 仅 MySQL 支持
- `list_connections` 数据量大时需分页拉取（`page_number` 参数）
- `list_history_connections` 需实例已开启会话快照采集
- `execute_sql` 仅支持只读操作，无法执行 `SET GLOBAL` 修改 `wait_timeout` 等参数
- 参数调整需到**火山引擎控制台 → 参数管理**修改

## ⚠️ 应急处置（需确认后执行）

### 终止长时间运行的查询

> **警告**：终止会话会导致当前事务失败，请在确认后执行！

```python
# 按条件终止：终止执行时间超过 60 秒的会话
kill_process(client,
    min_time=60,
    instance_id="mysql-xxx",
)

# 按条件终止：终止指定用户的全部 Sleep 会话
kill_process(client,
    users="app_user",
    command_type="Sleep",
    instance_id="mysql-xxx",
)

# 精确终止：终止指定进程（从 list_connections 获取 process_id 和 node_id）
kill_process(client,
    process_ids=["12345", "12346"],
    node_id="node-1",
    instance_id="mysql-xxx",
)
```

### 调整超时设置

> `execute_sql` 仅支持只读操作，无法执行 `SET GLOBAL`。需到**火山引擎控制台 → 参数管理**修改 `wait_timeout` 等参数。

## 预防措施

1. 使用正确的连接池
2. 设置适当的超时值
3. 监控连接状态
4. 实现连接生命周期管理
5. 设置连接数告警
6. 审查应用连接代码

## 关联场景

- [慢查询](slow-query.md)
- [锁等待](lock-wait.md)
- [连接数打满](connection-full.md)
