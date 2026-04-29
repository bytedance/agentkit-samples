---
name: "database-skill-ops-api"
description: "运维诊断函数的参数、返回格式速查。SOP 中需要查看函数详细参数时读取本文件。"
---

# 运维诊断 API

> **调用前提**：
> ```python
> cd skills/database-skill/scripts && python3 -c "
> from toolbox import create_client, <函数名>
> client = create_client(region='cn-beijing')  # 可选参数见下方 create_client 说明
> result = <函数名>(client, ...)
> print(result)
> "
> ```
>
> **`create_client` 参数**（均可选，不传时从环境变量读取）：
> | 参数 | 说明 |
> |:---|:---|
> | `region` | 地域，如 `"cn-beijing"`。环境变量 `VOLCENGINE_REGION` |
> | `instance_id` | 默认实例 ID。环境变量 `VOLCENGINE_INSTANCE_ID` |
> | `database` | 默认数据库名。环境变量 `VOLCENGINE_DATABASE` |

## 数据库类型兼容性

| 函数 | MySQL | VeDB | PG | MongoDB |
|:---|:---:|:---:|:---:|:---:|
| `describe_slow_logs` | ✓ | ✓ | ✓ | ✓ |
| `describe_aggregate_slow_logs` | ✓ | ✓ | ✓ | ✓ |
| `describe_slow_log_time_series_stats` | ✓ | ✓ | ✓ | ✓ |
| `describe_full_sql_detail` | ✓ | ✓ | ✓ | ✗ |
| `describe_health_summary` | ✓ | ✓ | ✓ | ✗ |
| `get_metric_items` / `get_metric_data` | ✓ | ✗ | ✗ | ✗ |
| `describe_table_metric` | ✓ | ✓ | ✓ | ✗ |
| `list_connections` | ✓ | ✓ | ✓ | ✓ |
| `kill_process` | ✓ | ✓ | ✓ | ✓ |
| `describe_deadlock` | ✓ | ✓ | ✗ | ✗ |
| `describe_trx_and_locks` | ✓ | ✓ | ✓ | ✗ |
| `describe_lock_wait` | ✓ | ✓ | ✓ | ✗ |
| `describe_err_logs` | ✓ | ✓ | ✓ | ✗ |
| `describe_table_space` | ✓ | ✓ | ✓ | ✗ |
| `describe_instance_nodes` | ✓ | ✓ | ✓ | ✓ |

SQL Server、Redis、External 不支持运维诊断函数。不支持的类型调用时代码自动拦截。

> **大数据量截断**：返回列表较多时，`data` 中会包含 `truncated: true` 和 `artifact_path`（完整数据的临时 JSON 文件）。定位 Top 问题用 inline 数据即可；全量统计时读取 `artifact_path`。

---

## 慢查询与全量 SQL

### describe_aggregate_slow_logs

按 SQL 模板聚合慢查询统计。**推荐首选**，比明细更适合定位 Top 问题。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| `client` | ToolboxClient | 是 | — | `create_client()` 返回值 |
| `start_time` | int | 是 | — | Unix 时间戳（秒） |
| `end_time` | int | 是 | — | Unix 时间戳（秒） |
| `instance_id` | str | 否 | 环境变量 | |
| `database` | str | 否 | None | 按数据库名过滤 |
| `page_number` | int | 否 | 1 | |
| `page_size` | int | 否 | 10 | |
| `order_by` | str | 否 | "TotalQueryTime" | TotalQueryTime / ExecuteCount |
| `sort_by` | str | 否 | "DESC" | ASC / DESC |
| `users` | list[str] | 否 | None | 按用户名过滤 |
| `source_ips` | list[str] | 否 | None | 按来源 IP 过滤 |
| `keywords` | list[str] | 否 | None | SQL 关键词过滤 |
| `tables` | list[str] | 否 | None | 按表名过滤 |
| `min_query_time` | float | 否 | None | 最小查询时间（秒） |
| `max_query_time` | float | 否 | None | 最大查询时间（秒） |
| `node_id` | str | 否 | None | VeDB 可指定节点 |

**返回** `data`:
- `total`: 总条数
- `logs[]`: `sql_template`, `db`, `user`, `source_ip`, `execute_count`, `execute_count_ratio`, `query_time_stats`(avg/max/min/total), `lock_time_stats`, `rows_sent_stats`, `rows_examined_stats`, `first_appear_time`, `last_appear_time`, `sql_fingerprint`, `sql_method`, `table`

### describe_slow_logs

查询慢查询明细日志。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| `client` | ToolboxClient | 是 | — | `create_client()` 返回值 |
| `start_time` | int | 是 | — | |
| `end_time` | int | 是 | — | |
| `instance_id` | str | 否 | 环境变量 | |
| `database` | str | 否 | None | 按数据库名过滤 |
| `page_number` | int | 否 | 1 | |
| `page_size` | int | 否 | 10 | |
| `order_by` | str | 否 | "QueryTime" | |
| `sort_by` | str | 否 | "DESC" | |
| `users` | list[str] | 否 | None | 按用户名过滤 |
| `source_ips` | list[str] | 否 | None | 按来源 IP 过滤 |
| `min_query_time` | float | 否 | None | 最小查询时间（秒） |
| `max_query_time` | float | 否 | None | 最大查询时间（秒） |
| `node_id` | str | 否 | None | |

**返回** `data`:
- `total`: 总条数
- `logs[]`: `sql`, `template`, `query_time`, `lock_time`, `rows_scanned`, `rows_sent`, `timestamp`, `user`, `ip`, `database`

### describe_slow_log_time_series_stats

慢查询时间序列趋势。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| `client` | ToolboxClient | 是 | — | `create_client()` 返回值 |
| `start_time` | int | 是 | — | |
| `end_time` | int | 是 | — | |
| `instance_id` | str | 否 | 环境变量 | |
| `database` | str | 否 | None | 按数据库名过滤 |
| `interval` | int | 否 | 300 | 采样间隔（秒） |
| `min_query_time` | float | 否 | None | 最小查询时间（秒） |
| `max_query_time` | float | 否 | None | 最大查询时间（秒） |
| `node_id` | str | 否 | None | |

**返回** `data`: `slow_log_count_stats`, `cpu_usage_stats`, `interval`

### describe_full_sql_detail

查询完整 SQL 历史详情。支持游标翻页。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| `client` | ToolboxClient | 是 | — | `create_client()` 返回值 |
| `start_time` | int | 是 | — | Unix 时间戳（秒） |
| `end_time` | int | 是 | — | Unix 时间戳（秒） |
| `instance_id` | str | 否 | 环境变量 | |
| `database` | str | 否 | None | 按数据库名过滤 |
| `page_size` | int | 否 | 50 | |
| `users` | list[str] | 否 | None | 按用户名过滤 |
| `source_ips` | list[str] | 否 | None | 按来源 IP 过滤 |
| `keywords` | list[str] | 否 | None | SQL 关键词过滤 |
| `tables` | list[str] | 否 | None | 按表名过滤 |
| `sql_methods` | list[str] | 否 | None | SQL 方法过滤（SELECT/INSERT/UPDATE/DELETE） |
| `min_exec_time` | int | 否 | None | 最小执行时间（毫秒） |
| `max_exec_time` | int | 否 | None | 最大执行时间（毫秒） |
| `context` | str | 否 | None | 翻页游标（从上次返回的 `data.context` 获取） |

**返回** `data`:
- `total`, `list_over`（是否全部返回）, `context`（翻页游标）
- `sql_list[]`: `db_name`, `session_id`, `sql_type`, `query_string`, `exec_plan`, `start_timestamp`, `end_timestamp`, `exec_time`, `cpu_time`, `row_lock_wait_time`, `rows_examined`, `rows_sent`, `user_name`, `client_ip`, `sql_fingerprint`, `sql_table`, `node_id`, `sql_template`

> **翻页**：`list_over=False` 时，将上次返回的 `data.context` 传入下次调用以获取下一页。`list_over=True` 表示已无更多数据。

---

## 健康概览与监控

### describe_health_summary

查询最近一小时的实例健康概览。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| `client` | ToolboxClient | 是 | — | `create_client()` 返回值 |
| `end_time` | int | 是 | — | Unix 时间戳（秒），返回截止到此时刻的最近一小时指标 |
| `instance_id` | str | 否 | 环境变量 | |
| `node_ids` | list[str] | 否 | None | 未传时自动查询 Primary 节点 |
| `diag_type` | str | 否 | "ALL" | |

**返回** `data`:
- `instance_id`, `node_ids`
- `metrics[]`: 9 项指标
  - `name`: CPU使用率 / QPS / TPS / innodbBufferPool命中率 / 内存使用率 / 当前打开连接数 / 慢查询数量 / 活跃会话数 / 连接数使用率
  - ⚠️ **连接数使用率** = 活跃会话数 / max_connections，**不含 Sleep 连接**。连接打满场景不能依赖此指标判断实际连接总数，需用 `list_connections(show_sleep=True)` 获取。
  - **当前打开连接数**：包含所有状态的连接（含 Sleep），与「活跃会话数」（不含 Sleep）的区别在于是否计入空闲连接。
  - `node_id`: 节点 ID
  - `avg`, `max`, `min`: 统计值
  - `total`: 慢查询总数（仅慢查询数量指标）
  - `unit`: 单位（`%` 或空）
  - `mom`: 环比变化率
  - `yoy`: 同比变化率

### get_metric_items / get_metric_data

监控指标查询。**仅 MySQL**。先调 `get_metric_items` 获取可用指标名，再用 `get_metric_data` 查数据。

```python
get_metric_items(client, instance_id=None)

get_metric_data(client,
    metric_name,             # str: 指标名（从 get_metric_items 获取）
    start_time, end_time,    # int
    instance_id=None,
    period=60,               # int: 采样周期（秒）
    node_id=None,
)
```

### describe_table_metric

表级 DML/DDL 监控。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| `client` | ToolboxClient | 是 | — | `create_client()` 返回值 |
| `db_name` | str | 是 | — | 数据库名 |
| `table` | str | 是 | — | 表名 |
| `start_time` | int | 是 | — | |
| `end_time` | int | 是 | — | |
| `instance_id` | str | 否 | 环境变量 | |
| `table_sql_type` | str | 否 | "DML" | "DML" 或 "DDL" |

---

## 会话与进程

### list_connections

查询实时活跃会话列表。**推荐用于巡检和会话排查**。支持服务端筛选，可按用户、数据库、命令类型等条件过滤。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| `client` | ToolboxClient | 是 | — | `create_client()` 返回值 |
| `instance_id` | str | 否 | 环境变量 | |
| `show_sleep` | bool | 否 | False | True 时包含 Sleep 连接。⚠️ **连接打满排查时必须设为 True**，否则只返回活跃连接，无法看到空闲堆积的 Sleep 连接 |
| `page_number` | int | 否 | 1 | |
| `page_size` | int | 否 | 50 | |
| `node_id` | str | 否 | None | 指定节点（VeDB 默认查所有节点） |
| `users` | str \| list[str] | 否 | None | 按用户名筛选，支持多值 |
| `hosts` | str \| list[str] | 否 | None | 按 IP 筛选，支持多值 |
| `dbs` | str \| list[str] | 否 | None | 按数据库名筛选，支持多值 |
| `command_type` | str | 否 | None | 按命令类型筛选（Query/Sleep 等） |
| `min_time` | int | 否 | None | 最小执行时间（秒），筛选执行时间≥N秒的会话 |
| `sql` | str | 否 | None | 按 SQL 语句匹配 |
| `fuzzy_match` | bool | 否 | True | 模糊匹配（False 时精确匹配） |

**返回** `data`:
- `total`: 会话总数
- `sessions[]`: `process_id`, `user`, `host`, `db`, `command`, `time`（执行秒数）, `state`, `info`（当前 SQL）；VeDB 额外返回 `node_id`, `node_type`

> ⚠️ 部分实例类型（如 VeDB）可能因后端连接问题返回失败，此时 fallback 到 `execute_sql` 执行 `SHOW PROCESSLIST`。

### list_history_connections

查询历史连接快照。需实例已开启会话快照采集。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| `client` | ToolboxClient | 是 | — | `create_client()` 返回值 |
| `start_time` | int | 是 | | Unix 时间戳，快照搜索起始 |
| `end_time` | int | 是 | | Unix 时间戳，快照搜索结束 |
| `instance_id` | str | 否 | 环境变量 | |
| `snapshot_time` | int | 否 | 范围内最新 | 指定查询某个快照时间点 |
| `show_sleep` | bool | 否 | False | True 时包含 Sleep 连接 |
| `sort_by` | str | 否 | "time" | 排序字段：time / user / db / command |
| `page_number` | int | 否 | 1 | |
| `page_size` | int | 否 | 50 | |

**返回** `data`:
- `total`: 连接总数
- `connections[]`: `process_id`, `user`, `host`, `db`, `command`, `time`, `state`, `info`, `node_id`, `blocking_pid`
- `snapshot_time`: 实际查询的快照时间点
- `snapshots_available`: 该时间范围内可用快照数
- `summary`: 聚合统计
  - `by_user`: 按用户 Top 10
  - `by_db`: 按数据库 Top 10
  - `by_command`: 按命令类型 Top 10

> ⚠️ 未开启会话快照时返回错误提示，需在控制台 → 数据库工作台 → 可观测性 → 会话 → 开启会话快照。

---

### kill_process

终止进程。⚠️ 危险操作，需用户确认。支持两种模式：

**模式 1（精确终止）**：传 `process_ids` + `node_id`，直接终止指定进程。

**模式 2（按条件终止）**：传 `kill_all=True` 或筛选条件，内部通过 `list_connections` 服务端筛选获取匹配会话后批量终止。自动处理多节点分组。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| `client` | ToolboxClient | 是 | — | `create_client()` 返回值 |
| `process_ids` | list[str] | 模式1必填 | None | 进程 ID 列表 |
| `node_id` | str | 模式1必填 | None | 节点 ID |
| `instance_id` | str | 否 | 环境变量 | |
| `shard_id` | str | 否 | None | 分片 ID（MongoDB） |
| `kill_all` | bool | 否 | False | 终止全部会话 |
| `users` | str \| list[str] | 否 | None | 按用户名筛选 |
| `hosts` | str \| list[str] | 否 | None | 按 IP 筛选 |
| `dbs` | str \| list[str] | 否 | None | 按数据库名筛选 |
| `command_type` | str | 否 | None | 按命令类型筛选（Query/Sleep 等） |
| `min_time` | int | 否 | None | 最小执行时间（秒） |
| `sql` | str | 否 | None | 按 SQL 语句匹配 |

### describe_instance_nodes

查询实例节点列表。`describe_instance_nodes(client, instance_id=None)`

用于获取 node_id（部分函数如 VeDB 的 describe_deadlock 需要）。

返回 `data.nodes[]`：每个节点含 `node_id`、`node_type`（Primary/Secondary）、`cpu_num`、`mem_in_gi_b`、`zone_id`。

---

## 锁与事务

### describe_deadlock

触发死锁分析并返回结果。自动查询 Primary 节点执行分析。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| `client` | ToolboxClient | 是 | — | `create_client()` 返回值 |
| `instance_id` | str | 否 | 环境变量 | |
| `page_number` | int | 否 | 1 | |
| `page_size` | int | 否 | 50 | 上限 100 |

**返回** `data`:
- `total`: 记录数
- `items[]`: 死锁详情
- `diagnosis_time`: 分析时间点
- `node_id`: Primary 节点 ID

### describe_trx_and_locks

触发事务和锁分析并返回结果。自动查询 Primary 节点执行分析。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| `client` | ToolboxClient | 是 | — | `create_client()` 返回值 |
| `instance_id` | str | 否 | 环境变量 | |
| `page_number` | int | 否 | 1 | |
| `page_size` | int | 否 | 50 | 上限 100 |
| `lock_status` | str | 否 | None | 锁状态过滤：`"LockHold"`（仅持锁）/ `"LockWait"`（仅等锁）/ `"LockHoldAndWait"` |
| `trx_status` | str | 否 | None | 事务状态过滤：`"RUNNING"` / `"LOCKWAIT"` / `"ROLLING_BACK"` / `"COMMITTING"` |
| `process_id` | str | 否 | None | 按进程 ID 精确匹配 |
| `trx_id` | str | 否 | None | 按事务 ID 精确匹配 |
| `block_trx_id` | str | 否 | None | 按阻塞事务 ID 精确匹配 |

> **快速定位持锁者**：`lock_status="LockHold"` 可直接过滤出持有锁的事务。

**返回** `data`:
- `total`: 记录数
- `items[]`: 事务和锁详情（`trx_id`, `trxstatus`, `lockstatus`, `process_id`, `trx_exec_time`, `sql_blocked`, `lock_list`/`lock_summary`, `trx_rows_locked`, `block_trx_id` 等）
- `diagnosis_time`: 分析时间点
- `node_id`: Primary 节点 ID

> `lock_list` 超过 5 条时自动裁剪：保留前 5 条 + `lock_summary`（按类型/模式/状态聚合计数）+ `lock_count`（总数）。

### describe_lock_wait

触发锁等待分析并返回结果。自动查询 Primary 节点执行分析。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| `client` | ToolboxClient | 是 | — | `create_client()` 返回值 |
| `instance_id` | str | 否 | 环境变量 | |
| `page_number` | int | 否 | 1 | |
| `page_size` | int | 否 | 50 | 上限 100 |
| `r_trx_state` | str | 否 | None | 等待方（被阻塞）事务状态：`"RUNNING"` / `"LOCKWAIT"` / `"ROLLING_BACK"` / `"COMMITTING"` |
| `b_trx_state` | str | 否 | None | 阻塞方事务状态（同上） |
| `r_trx_id` | str | 否 | None | 等待方事务 ID（精确匹配） |
| `b_trx_id` | str | 否 | None | 阻塞方事务 ID（精确匹配） |

**返回** `data`:
- `total`: 记录数
- `items[]`: 锁等待详情（`r_trx_id`, `r_waiting_query`, `r_trx_state`, `b_trx_id`, `b_blocking_query`, `b_trx_state`, `r_blocked_wait_secs`, `b_blocking_wait_secs` 等）
- `diagnosis_time`: 分析时间点
- `node_id`: Primary 节点 ID

---

## 日志与空间

### describe_err_logs

查询错误日志。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| `client` | ToolboxClient | 是 | — | `create_client()` 返回值 |
| `start_time` | int | 是 | — | |
| `end_time` | int | 是 | — | |
| `instance_id` | str | 否 | 环境变量 | |
| `page_number` | int | 否 | 1 | |
| `page_size` | int | 否 | 10 | |
| `keyword` | str | 否 | None | 关键字过滤 |

**返回**：`data.err_logs[]` — 错误日志列表，`data.total` — 总条数

### describe_table_space

查询表空间详情。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|:---|:---|:---:|:---|:---|
| `client` | ToolboxClient | 是 | — | `create_client()` 返回值 |
| `instance_id` | str | 否 | 环境变量 | |
| `database` | str | 否 | None | 过滤指定数据库 |
| `table_name` | str | 否 | None | 过滤指定表 |
| `page_number` | int | 否 | 1 | |
| `page_size` | int | 否 | 10 | |
