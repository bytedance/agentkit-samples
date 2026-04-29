# 连接泄漏故障排查

## 概述

连接泄漏是指应用未正确关闭 MongoDB 连接，导致连接堆积、资源耗尽，最终可能导致连接数打满。

## 典型症状

- 连接数持续增长不回落
- 大量连接处于空闲状态
- 连接数接近上限
- 重启应用后连接数下降

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

## 必看数据

> 函数参数详见 [api/metadata-query.md](../../api/metadata-query.md)。

| 优先级 | 数据来源 | 命令 | 目的 |
|--------|----------|------|------|
| P0 | `execute_sql` | `db.serverStatus().connections;` | 获取连接统计（current / available / totalCreated） |
| P0 | `execute_sql` | `db.getSiblingDB('admin').aggregate([{$currentOp: {allUsers: true, idleConnections: true}}, {$group: {_id: {client: "$client", appName: "$appName"}, count: {$sum: 1}}}, {$sort: {count: -1}}, {$limit: 20}]);` | 按客户端 IP 和应用名分组统计连接数 |
| P1 | `execute_sql` | `db.getSiblingDB('admin').aggregate([{$currentOp: {allUsers: true, idleConnections: true}}, {$group: {_id: "$active", count: {$sum: 1}}}]);` | 统计活跃 vs 空闲连接比例 |
| P2 | `execute_sql` | `db.serverStatus().network;` | 查看网络流量（bytesIn / bytesOut / numRequests） |

所有命令的 `database` 参数使用 `"admin"`。

## 关键分析维度

- **current vs available**：current 接近 available 说明连接即将耗尽
- **活跃 vs 空闲比例**：大量空闲连接说明连接未正确释放
- **totalCreated 增长速率**：持续快速增长说明应用频繁创建新连接而非复用
- **按客户端分组**：定位哪个应用/IP 占用连接最多

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|----------|----------|------------|
| 空闲连接占比 > 80% + 连接数持续增长 | 应用未正确关闭连接 | 检查应用代码是否在 finally 中关闭连接 |
| 单个客户端 IP 连接数异常高 | 该应用连接池配置不当或泄漏 | 检查该应用的连接池参数（maxPoolSize / minPoolSize） |
| 重启应用后连接数骤降再缓慢上升 | 应用存在连接泄漏 | 重启后观察连接增长曲线，确认是否线性增长 |
| totalCreated 快速增长 + current 不高 | 连接频繁创建销毁（短连接模式） | 检查是否每次请求新建连接而非使用连接池 |

## 约束与边界

- `execute_sql` 仅用于查询类操作
- 连接数上限由实例规格决定，修改需到火山引擎控制台调整

## 预防措施

1. 使用正确的连接池配置
2. 实现正确的连接生命周期管理
3. 正确处理异常（确保 finally 中释放连接）
4. 设置适当的超时值（connectTimeoutMS / socketTimeoutMS）
5. 监控连接状态
6. 设置连接数告警

## 关联场景

- [连接数打满](connection-full.md)
