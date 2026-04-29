# 巡检 SOP

## 概述

巡检是对数据库实例的健康检查，目的是发现潜在风险而非排查具体故障。巡检产出概览报告，只需标注正常/异常/风险项，不深入排查细节。

> 函数参数详见 [api/ops.md](../api/ops.md)。

## 巡检项

按优先级执行以下检查。每项查完后记录状态（✅ 正常 / ⚠️ 关注 / ❌ 异常），最后汇总为巡检报告。

> **兼容性规则**：每个巡检项标注了支持的 db_type。当前实例不支持的项直接跳过，报告中也不体现。部分项提供了 `execute_sql` 替代方案。
>
> **安全原则**：巡检只做只读查询，`execute_sql` 替代命令必须是只读的，不能对服务产生影响。
>
> **Redis 注意**：Redis 命令不加分号，如 `INFO` 而非 `INFO;`。

### 第 1 项：健康概览

**MySQL / VeDB / PG**：

```python
import time
now = int(time.time())

describe_health_summary(client,
    end_time=now,
    instance_id="xxx"
)
```

返回最近一小时 9 项核心指标：
- CPU 使用率、内存使用率、连接数使用率（avg/max/min/环比/同比）
- QPS、TPS、InnoDB BufferPool 命中率（MySQL/VeDB）
- 当前打开连接数、活跃会话数
- 慢查询数量（total）

**Redis 替代**：`execute_sql(client, sql="INFO", instance_id="redis-xxx", database="0")` — 从输出提取 `used_memory_human`、`connected_clients`、`blocked_clients`、`instantaneous_ops_per_sec`。

**MongoDB 替代**：`execute_sql(client, sql="db.serverStatus()", instance_id="mongo-xxx", database="admin")` — 从输出提取 `connections.current`/`available`、`opcounters`、`mem.resident`。

**判断标准：**

| 指标 | 正常 | 关注 | 异常 |
|:---|:---|:---|:---|
| CPU 使用率 | < 60% | 60-80% | > 80% |
| 内存使用率 | < 70% | 70-85% | > 85% |
| 连接数使用率 [^1] | < 60% | 60-80% | > 80% |
| BufferPool 命中率 | > 99% | 95-99% | < 95% |
| 慢查询数量 | 0 | > 0 | 持续增长 |
| 环比/同比 | 波动 < 20% | 波动 20-50% | 波动 > 50% |

[^1]: 连接数使用率 = 活跃会话数 / max_connections，**不含 Sleep 连接**。连接打满场景需额外查 `list_connections(show_sleep=True)` 获取实际总连接数。

### 第 2 项：慢查询

**MySQL / VeDB / PG / MongoDB**：

```python
describe_aggregate_slow_logs(client,
    start_time=now - 86400,
    end_time=now,
    instance_id="xxx",
    order_by="TotalQueryTime",
    sort_by="DESC"
)
```

关注 Top 5 慢 SQL 模板：执行次数、平均耗时、总耗时。

**判断标准：**

| 指标 | 正常 | 关注 | 异常 |
|:---|:---|:---|:---|
| 慢查询总数（24h） | 0 | 1-100 | > 100 或持续增长 |
| Top1 平均耗时 | < 1s | 1-10s | > 10s |
| Top1 执行次数 | < 10 | 10-100 | > 100（高频慢查询） |

### 第 3 项：活跃会话

**MySQL / VeDB / PG / MongoDB**：

```python
list_connections(client, instance_id="xxx")
# 巡检时建议同时加 show_sleep=True 查看全量连接，便于发现空闲连接堆积
# list_connections(client, instance_id="xxx", show_sleep=True)
# 若 API 返回失败（如 VeDB 连接问题），fallback:
# execute_sql(client, sql="SHOW PROCESSLIST", instance_id="xxx", database="xxx")
```

**Redis 替代**：`execute_sql(client, sql="CLIENT LIST", instance_id="redis-xxx", database="0")` — 关注 idle 时间长的连接。

**判断标准：**

| 指标 | 正常 | 关注 | 异常 |
|:---|:---|:---|:---|
| 执行时间 > 60s 的活跃查询 | 0 | 1-3 | > 3 |
| Sleep/idle 连接占比 | < 50% | 50-80% | > 80% |
| 总连接数 vs max_connections | < 60% | 60-80% | > 80% |

**可选：历史连接趋势**（需实例已开启会话快照采集）：

```python
# 对比 1 小时前的连接快照，判断连接数是否持续增长
list_history_connections(client,
    start_time=now - 7200,
    end_time=now - 3600,
    instance_id="xxx",
)
```

若 `summary.by_user` 分布与当前差异大，标注 ⚠️ 关注。

### 第 4 项：错误日志（MySQL / VeDB / PG）

```python
describe_err_logs(client,
    start_time=now - 86400,
    end_time=now,
    instance_id="xxx"
)
```

**判断标准：**

| 指标 | 正常 | 关注 | 异常 |
|:---|:---|:---|:---|
| 错误日志数（24h） | 0 | 1-10 | > 10 或含 OOM/crash |
| 关键词（OOM / crash / replication error） | 无 | — | 出现任意一个 |

### 第 5 项：表空间（MySQL / VeDB / PG）

```python
describe_table_space(client, instance_id="xxx")
```

**判断标准：**

| 指标 | 正常 | 关注 | 异常 |
|:---|:---|:---|:---|
| 磁盘使用率 | < 60% | 60-80% | > 80% |
| 单表大小 | < 10GB | 10-50GB | > 50GB |
| 碎片率（data_free / data_length） | < 20% | 20-50% | > 50% |

### 第 6 项：事务与锁检查（MySQL / VeDB / PG）

以下三个函数均为实时触发分析。

```python
# 死锁分析（MySQL / VeDB）
describe_deadlock(client, instance_id="xxx")

# 事务和锁分析（MySQL / VeDB / PG）
describe_trx_and_locks(client, instance_id="xxx")

# 锁等待分析（MySQL / VeDB / PG）
describe_lock_wait(client, instance_id="xxx")
```

关注：是否有死锁、是否有长事务持锁、是否有锁等待。无异常则标注 ✅，有锁等待或长事务标注 ⚠️，有死锁标注 ❌。

## 巡检报告格式

```
## 巡检报告：{instance_id}
巡检时间：{当前时间}
时间范围：最近 24 小时

| 巡检项 | 状态 | 摘要 |
|:---|:---|:---|
| 健康概览 | ✅/⚠️/❌ | CPU avg 2%，内存 10%，连接 3% |
| 慢查询 | ✅/⚠️/❌ | Top1: SELECT ... 平均 2.3s，执行 150 次 |
| 活跃会话 | ✅/⚠️/❌ | 3 个活跃连接，无长事务 |
| 错误日志 | ✅/⚠️/❌ | 无错误 |
| 表空间 | ✅/⚠️/❌ | 磁盘使用 45%，最大表 orders 2.3GB |
| 事务与锁 | ✅/⚠️/❌ | 无死锁，无锁等待 |

### 风险项及建议
- （列出 ⚠️ 和 ❌ 项的具体建议）

### 结论
整体健康状态：良好 / 需关注 / 需处理
```

