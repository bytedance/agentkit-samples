# 高级模式参考

## 高级模式工作原理

`--advanced` 仅在实时跟踪模式 (`-f`) 下生效：

1. 检查 `openclaw.json` 中 `diagnostics.enabled` 和 `logLevel` 配置
2. 如果未开启，备份配置文件，修改为 `diagnostics.enabled: true` + `logLevel: debug`
3. 自动重启 Gateway（等待最多 60 秒）
4. 开始实时跟踪
5. Ctrl+C 退出时提示是否恢复原配置

## 配置项

| 配置 | 作用 | 高级模式设置 |
|------|------|------------|
| `diagnostics.enabled` | 启用 Run 事件记录 | `true` |
| `logLevel` | 日志详细度 | `debug` |

## 手动开启（不用 --advanced）

```bash
openclaw config set diagnostics.enabled true
openclaw config set logLevel debug
openclaw gateway restart
```

## Session 文件结构

路径：`~/.openclaw/agents/{agent}/sessions/{id}.jsonl`

每行一个 JSON 对象，关键字段：
- `role`: user / assistant / toolCall / toolResult / custom_message
- `timestamp`: ISO 8601 UTC
- `model`: 模型名称
- `usage`: `{input, output, cacheRead, cacheWrite, totalTokens}`
- `toolResult.details`: `{exitCode, durationMs, stdout, stderr}`

## 虚拟 Run 构造算法

当无 debug 日志时：
1. 扫描所有 agent 的 session 文件（含 .reset.* 和 .deleted.*）
2. 按日期过滤消息（UTC ±1 天容错）
3. 每条 user 消息标记为 Run 起点
4. 到下一条 user 消息或文件末尾为 Run 终点
5. 聚合 Run 内的 assistant/toolCall/toolResult 统计

## 多 Agent 支持

脚本扫描 `~/.openclaw/agents/*/sessions/` 下所有 agent。

`-a <name>` 过滤逻辑：
- 批量模式：通过 session 文件路径提取 agent 名称，过滤 Run
- 实时跟踪：从日志中 `sessionKey=agent:{name}:{id}` 提取 agent，过滤事件
