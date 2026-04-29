# 网络抖动故障排查

## 概述

网络抖动是指网络延迟不稳定或丢包，导致数据库连接超时、响应时间波动、数据传输中断等问题。

## 典型症状

- 连接超时错误
- 响应时间波动大
- 连接断开重连
- 网络延迟监控显示抖动

> 函数参数详见 [api/ops.md](../../api/ops.md)。

## 必看数据

| 优先级 | 函数 | 关键参数 | 目的 |
|:---|:---|:---|:---|
| P0 | `get_metric_data` | `metric_name="NetworkReceiveThroughput"`, `period=60` | 网络入流量趋势，判断是否有异常波动 |
| P0 | `get_metric_data` | `metric_name="NetworkTransmitThroughput"`, `period=60` | 网络出流量趋势 |
| P0 | `execute_sql` | `sql="SHOW GLOBAL STATUS LIKE 'Aborted%';"` | 查看异常断开连接数（Aborted_clients / Aborted_connects） |
| P1 | `execute_sql` | `sql="SHOW GLOBAL STATUS LIKE 'Connection%';"` | 查看连接统计 |
| P1 | `list_connections` | `show_sleep=True` | 查看活跃会话，筛选异常状态（Timeout/Disconnect） |
| P2 | `get_metric_items` | — | 获取支持的监控指标列表，按需选取更多指标 |

## 关键分析维度

- **断连模式**：Aborted_clients（已连接后断开）vs Aborted_connects（连接阶段失败）— 前者多为网络问题，后者多为认证/连接数问题
- **时间相关性**：网络抖动是否与特定时段、特定操作关联
- **来源分布**：是所有来源 IP 都有问题还是特定来源 — 用 `list_connections` 按 host 分析
- **流量特征**：是否有突发大流量导致网络拥塞

## 根因判断知识

| 现象组合 | 通常根因 | 进一步确认 |
|:---|:---|:---|
| Aborted_clients 快速增长 + 连接数正常 | 客户端网络不稳定或未正确关闭连接 | 检查应用日志中的连接错误 |
| Aborted_connects 增长 + 连接数接近上限 | 连接数打满导致新连接被拒 | 转到[连接数打满](connection-full.md)排查 |
| 网络入出流量突然归零或剧烈波动 | 网络设备故障（交换机/网卡） | 联系基础设施团队检查 |
| 特定来源 IP 集中出现断连 | 客户端侧网络问题或 DNS 解析异常 | 建议应用使用 IP 连接而非主机名 |
| 周期性连接超时 + 响应延迟增大 | 网络带宽拥塞 | 检查网络流量峰值是否接近带宽上限 |

## 约束与边界

- `get_metric_data` / `get_metric_items` 仅 MySQL 支持
- `execute_sql` 仅支持只读操作，无法执行 `SET GLOBAL` 修改超时参数
- 超时参数调整（`connect_timeout`、`wait_timeout`）需到**火山引擎控制台 → 参数管理**修改
- 网络层面的问题（路由、交换机、DNS）超出数据库工具能力范围，需联系基础设施团队

## ⚠️ 应急处置（需确认后执行）

### 调整超时参数

> `execute_sql` 仅支持只读操作，无法执行 `SET GLOBAL`。需到**火山引擎控制台 → 参数管理**修改 `connect_timeout`、`wait_timeout` 等参数。

### 使用 IP 而非主机名

建议应用连接字符串使用 IP 地址而非主机名，避免 DNS 解析延迟。

## 预防措施

1. 使用稳定的网络基础设施
2. 监控网络指标
3. 设置适当的超时值
4. 使用连接池
5. 在应用中实现重试逻辑
6. 设置网络告警

## 关联场景

- [连接数打满](connection-full.md)
