# 连接数打满故障排查

## 概述

连接数打满是指 MongoDB 实例的当前连接数达到 `maxIncomingConnections` 上限，导致新请求无法建立连接，出现 `too many connections` 错误。

**诊断原则：连接数打满是结果，不是原因。** 排查时必须按应用名、客户端 IP、操作状态等维度分组统计，定位哪个服务/客户端贡献了异常连接数。

## 典型症状

- 应用报错: `too many connections`
- 无法建立新的数据库连接
- 连接数监控显示达到上限
- 旧连接未被释放，堆积

> 函数参数详见 [api/ops.md](../../api/ops.md) 和 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

> 函数参数详见 [api/ops.md](../../api/ops.md) 和 [api/metadata-query.md](../../api/metadata-query.md)。

| 优先级 | 获取方式 | 命令/参数 | 目的 |
|:---|:---|:---|:---|
| P0 | `list_connections` | **`show_sleep=True`** | 全量连接列表，数据量大时自动返回 `stats` 统计摘要 |
| P0 | `execute_sql` | `db.serverStatus().connections` | 连接总数概览（current / available / totalCreated） |
| P1 | `execute_sql` | `$currentOp` 聚合（见下方） | 按 appName 分组的活跃连接分布 |
| P2 | `describe_slow_logs` | 最近 1h | 排除慢操作导致的连接堆积 |

### 原生命令参考

```javascript
// 连接总数概览
db.serverStatus().connections

// 按 appName 分组统计连接（含空闲连接）
db.getSiblingDB('admin').aggregate([
    { $currentOp: { allUsers: true, idleConnections: true } },
    { $group: { _id: "$appName", count: { $sum: 1 }, active: { $sum: { $cond: ["$active", 1, 0] } } } },
    { $sort: { count: -1 } }
])

// 按客户端 IP 分组
db.getSiblingDB('admin').aggregate([
    { $currentOp: { allUsers: true, idleConnections: true } },
    { $group: { _id: "$client", count: { $sum: 1 } } },
    { $sort: { count: -1 } }
])
```

> 以上命令均通过 `execute_sql(client, sql="...", database="admin")` 执行。

## 诊断路径

1. **确认规模** → `execute_sql("db.serverStatus().connections")` — 查看 current / available / totalCreated
2. **拉全量连接** → `list_connections(show_sleep=True)` — 从 `stats` 摘要判断模式
   - 空闲占比高 + 集中单 appName → 连接泄漏方向
   - 活跃占比高 → 不是泄漏，查慢操作
3. **按应用分组** → `execute_sql("$currentOp + $group by appName")` — 定位哪个应用占连接最多
4. **需要终止时** → `kill_process` 按条件终止（需用户确认）

## 关键统计维度

`list_connections` 返回数据量大时自动包含 `stats` 统计摘要，结合 `$currentOp` 结果按以下维度分析：

- **by appName**：是否集中在某个应用 — 判断是单应用泄漏还是全局问题
- **by Client IP**：是否来自少数 IP — 定位问题服务器
- **活跃 vs 空闲比例**：空闲连接占比高说明连接池未回收
- **by Command**（`list_connections` stats）：连接状态分布

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| 空闲连接占比 > 70%，集中单 appName | 连接泄漏 | 检查该应用的 MongoClient 连接池配置（maxPoolSize、maxIdleTimeMS） |
| 活跃 > 50%，多应用分散 | 连接池容量不足 | 查 `maxIncomingConnections` 配置（默认 65536）；确认是否需要扩容 |
| 大量长时间运行操作（secs_running > 60s） | 慢操作阻塞 | 查 `describe_slow_logs` 或 `$currentOp` 中 secs_running 较大的操作 |
| totalCreated 持续快速增长 | 短连接风暴 | 应用未使用连接池或连接池配置过小，频繁创建销毁连接 |
| 空闲连接多，appName 分散，无明显单点 | 全局 maxIdleTimeMS 过大 | 检查各应用的 MongoClient `maxIdleTimeMS` 配置（默认无超时） |

## 约束与边界

- `execute_sql` 仅用于查询类操作
- **kill_process**：必须经过用户明确确认后才能执行
- 连接数上限由实例规格决定，修改需到火山引擎控制台调整
- **数据量**：`list_connections` 数据量大时自动计算统计摘要并落盘全量数据到 `artifact_path`

## ⚠️ 应急处置（需确认后执行）

### 终止长时间运行的操作

> **警告**：终止操作会导致当前任务失败，请在确认后执行！

```python
# 通过 kill_process 按条件终止（推荐）
kill_process(client,
    min_time=300,
    instance_id="mongo-xxx",
)
```

## 预防措施

1. 使用正确的连接池（MongoClient 设置合理的 maxPoolSize）
2. 配置 `maxIdleTimeMS` 回收空闲连接
3. 监控 `db.serverStatus().connections` 设置告警
4. 审查应用连接生命周期，确保连接正确关闭
5. 适当配置 `maxIncomingConnections`
6. 避免短连接模式，使用持久连接池

## 关联场景

- [连接泄漏](connection-leak.md)
- [慢查询](slow-query.md)
