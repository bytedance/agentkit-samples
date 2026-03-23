---
name: openclaw-diagnostics
description: >
  OpenClaw 系统诊断和性能分析工具。分析 agent 推理耗时、Token 用量、工具调用统计、
  Run 时间线、Gateway 重启历史。支持多种模式：批量分析（默认）、实时跟踪（-f）、
  摘要统计（-s）、高级诊断（--advanced）。支持多 Agent 过滤。
  使用场景：当用户询问 OpenClaw 运行状态、性能瓶颈、推理延迟、Token 消耗、
  工具执行统计、错误排查、agent 活动分析时触发。
  触发词：诊断、diagnostics、性能分析、推理耗时、token统计、运行状态、
  agent分析、工具调用统计、Run详情、Gateway重启。
  指令触发：/diag — 直接执行诊断，支持参数透传。
metadata:
  openclaw:
    tools:
      - exec
      - read
---

# OpenClaw 诊断工具

## 指令模式

当用户发送 `/diag` 指令时，直接执行脚本，不做额外解释：

| 用户输入 | 执行命令 | 说明 |
|----------|----------|------|
| `/diag` | `-s` | 今日摘要（默认） |
| `/diag full` | `(无-s)` | 完整报告（含 Run 详情 + 错误列表） |
| `/diag full -l 3` | `-l 3` | 最近 3 个 Run 完整详情 |
| `/diag -a waicode` | `-s -a waicode` | 指定 agent 摘要 |
| `/diag -a main full` | `-a main` | 指定 agent 完整报告 |
| `/diag 2026-03-19` | `-s 2026-03-19` | 指定日期摘要 |
| `/diag errors` | `(无-s)` | 执行完整报告，只提取错误部分汇总 |

规则：
1. 无参数时默认 `-s`（摘要模式，最简洁）
2. `full` 关键词 → 去掉 `-s`，输出含 Run 详情
3. `errors` 关键词 → 执行完整报告，只摘出错误列表
4. `-a`、`-l`、日期参数直接透传给脚本
5. 去除 ANSI 颜色码：管道 `| sed 's/\x1b\[[0-9;]*m//g'`
6. 不支持 `-f`（实时跟踪），该模式需在 SSH 终端运行
7. **直出模式**：脚本输出直接用 `message` 工具原样发送给用户，不经过模型总结。
   具体做法：
   - 执行脚本，将 stdout 存入变量
   - 用 `message(action="send", message=output)` 发送原始输出
   - 然后回复 `NO_REPLY`（避免重复发送）
   - 如果输出超过 4000 字符，按 4000 字符分段发送（Telegram 消息长度限制）
   - 每段用 ``` 代码块包裹，保持等宽字体排版

## 自然语言模式

当用户用自然语言询问（如"运行状态怎么样"、"waicode今天干了啥"）时，
自行选择合适参数执行脚本，并用中文汇总关键信息。

## 快速使用

```bash
# 诊断今天的数据
bash scripts/openclaw-diag.sh

# 诊断指定日期
bash scripts/openclaw-diag.sh 2026-03-19

# 只看摘要
bash scripts/openclaw-diag.sh -s

# 实时跟踪（类似 tail -f）
bash scripts/openclaw-diag.sh -f

# 高级实时跟踪（自动开启 debug 日志，退出时恢复）
bash scripts/openclaw-diag.sh -f --advanced

# 只看指定 agent
bash scripts/openclaw-diag.sh -a waicode

# 最近 5 个 Run
bash scripts/openclaw-diag.sh -l 5
```

## 模式说明

| 模式 | 参数 | 说明 |
|------|------|------|
| 摘要统计 | `-s`（默认） | KPI 概览，最简洁 |
| 完整报告 | 无 `-s` | 含 Run 详情 + 时间线 + 错误列表 |
| Agent 过滤 | `-a <name>` | 只看指定 agent |
| 限制数量 | `-l N` | 只显示最近 N 个 Run |
| 指定日期 | `YYYY-MM-DD` | 默认今天 |

参数可组合：`-s -a main`、`-l 3 -a wairesearch`。

> 实时跟踪（`-f`）和高级模式（`--advanced`）需在 SSH 终端运行，
> 详见 [references/advanced-mode.md](references/advanced-mode.md)。

## 数据源

脚本有两种数据源，自动切换：

| 数据源 | 路径 | 需要配置 | 精度 |
|--------|------|----------|------|
| Debug 日志 | `/tmp/openclaw/openclaw-YYYY-MM-DD.log` | `diagnostics.enabled: true` | 精确 Run 边界 |
| Session 文件 | `~/.openclaw/agents/*/sessions/*.jsonl` | 无需配置 | 虚拟 Run（消息时间戳推算） |

无 debug 日志时自动降级为 session 模式，核心指标（推理耗时、Token、工具统计）仍然准确。

## 输出内容

### 摘要统计
- 模型调用次数、平均推理延迟、Token 吞吐量
- 工具调用次数、成功率、总耗时
- Thinking 统计（次数、平均深度）
- Per-Agent 活动分布

### Run 详情（非摘要模式）
- 每个 Run 的时间线（推理段 + 工具调用段）
- 推理耗时、输出 Token、吞吐速率
- 工具调用参数摘要

### 错误列表
- 最近 20 条错误，按时间倒序

## 使用指南

### 日常检查
```bash
# 快速了解今天的运行概况
bash scripts/openclaw-diag.sh -s
```

### 性能排查
```bash
# 查看某天详细 Run 数据，找到慢查询
bash scripts/openclaw-diag.sh 2026-03-19 -l 10
```

### 特定 Agent 分析
```bash
# 只看 waicode 的活动
bash scripts/openclaw-diag.sh -a waicode -s
```

### 实时监控（SSH 终端）
```bash
# 需在 SSH 终端运行，不适合 Telegram/聊天
bash scripts/openclaw-diag.sh -f
bash scripts/openclaw-diag.sh -f --advanced
```

## 注意事项

- 脚本依赖 `python3`（3.7+，使用 `datetime.fromisoformat`）和 `bash`
- 高级模式（`--advanced`）会临时修改 `openclaw.json` 并重启 Gateway，退出时自动恢复
- 无 Swap 的机器上并发多 Agent 时注意内存
- 时间戳统一为 UTC 处理，不受本地时区影响
