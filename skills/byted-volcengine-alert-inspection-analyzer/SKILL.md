---
name: byted-volcengine-alert-inspection-analyzer
description: 面向日常运维巡检场景，对告警、体检等信息进行按日采集、结构化沉淀和周期输出（日报/周报/月报）。
version: 1.0.0
---

# byted-volcengine-alert-inspection-analyzer

把“飞书群告警消息拉取 + 过滤 + 去重 + 事件聚合 + 风险分析 + 报告输出”固化为标准技能。

## 适用场景

当用户提出以下类型需求时使用本技能：

- 查询某个飞书群某天/某时间段内的云告警通知
- 拉取指定机器人、Bot、应用发送的告警消息
- 对告警消息做巡检分析、日报、复盘或稳定性判断
- 需要导出结构化 JSON、Markdown 报告或压缩包
- 需要判断告警是否恢复、是否存在未闭环事件、是否为噪声告警

## 输入要求

至少需要以下三类信息：

1. `chat_id`：飞书群 ID，例如 `oc_xxx`
2. `time`：时间范围
   - 相对时间：`today`、`yesterday`、`last_24_hours`、`this_week`
   - 或绝对时间：`start_time` + `end_time`，ISO 8601 格式，例如 `2026-06-05T00:00:00+08:00`
3. `bot`：机器人标识
   - 优先使用 `bot_sender_id` / app id，例如 `cli_xxx`
   - 如果只有机器人名称，先按时间范围拉取消息后从 sender 信息识别；同时说明精确度风险

可选信息：

- `output_dir`：输出目录，默认 `output/alert_inspection_<日期>_<chat_id>/`
- `report_format`：`json`、`markdown`，默认同时生成
- `keyword`：内容关键词过滤，例如“火山引擎云监控告警通知”

## 工作流程

### 1. 校验输入

- 缺少 `chat_id`、`time` 或 `bot` 时，先向用户补齐。
- 时间必须二选一：相对时间，或 `start_time + end_time`。
- 对中文日期（如“6月5日”）默认使用当前年份和北京时间，除非用户另有说明。

### 2. 拉取飞书消息

优先使用 `feishu_im_user_get_messages` 工具：

```json
{
  "chat_id": "oc_xxx",
  "start_time": "2026-06-05T00:00:00+08:00",
  "end_time": "2026-06-05T23:59:59+08:00",
  "page_size": 50,
  "sort_rule": "create_time_asc"
}
```

分页规则：

- 每页最多 50 条。
- 如果返回 `has_more=true`，继续使用 `page_token` 拉取下一页。
- 合并所有分页结果后按 `message_id` 去重。

### 3. 机器人过滤

过滤优先级：

1. 如果用户提供 `bot_sender_id`：按 `sender.id` 精确过滤。
2. 如果只有机器人名称：
   - 先从返回消息中识别 `sender.sender_type == app` 的候选 sender id。
   - 结合消息卡片标题、内容关键词和告警语义做保守筛选。
   - 一旦确认 sender id，后续分析中记录为 `filter_mode=identified_sender_id`。
3. 如果无法确认 sender id：
   - 用内容关键词过滤。
   - 在报告中明确标注 `filter_mode=keyword_only`，说明可能不完整或不精确。

### 4. 标准化消息

使用 `scripts/alert_inspection.py` 对原始消息 JSON 做标准化。标准字段：

- `message_id`
- `create_time`
- `status`：`警告` / `已恢复` / `严重` / `未知`
- `policy`
- `resource`
- `metric`
- `current_value`
- `content`
- `sender`

从飞书卡片内容中尽量提取：

- 告警策略
- 告警级别
- 项目
- 地域
- 告警时间
- 云产品
- 资源 ID
- 当前值
- 告警详情链接

### 5. 分析告警

分析维度：

- 总消息数、警告数、恢复数、未知数
- 按策略统计
- 按指标统计
- 按资源统计
- 按小时统计
- 告警事件闭环：连续警告到恢复为一个事件周期
- 未恢复事件识别
- 持续时间、最长事件、重复事件
- 风险等级：低 / 中 / 高
- 可能原因与处置建议

风险判断建议：

- **低风险**：少量告警，全部快速恢复，无重复集中模式。
- **中风险**：同一资源/指标反复告警，全部恢复但频率较高。
- **高风险**：存在未恢复告警、严重级别告警、长时间持续、核心指标异常或高频集中爆发。

### 6. 输出文件

默认输出到：

```text
output/alert_inspection_<YYYY-MM-DD>_<chat_id>/
```

应生成：

- `raw_messages.json`：原始消息
- `normalized_messages.json`：标准化消息
- `analysis.json`：统计与分析结构化数据
- `report.md`：面向用户的中文分析报告
- `run_meta.json`：运行元数据

如用户要求发送压缩包，则将输出目录打包为 `.zip` 后用 `message` 工具发送。

## 推荐执行方式

### A. 已通过工具获得原始消息时

将工具返回结果保存为原始 JSON：

```bash
python scripts/alert_inspection.py \
  --input raw_messages.json \
  --chat-id oc_xxx \
  --bot-name 云告警通知 \
  --start-time 2026-06-05T00:00:00+08:00 \
  --end-time 2026-06-05T23:59:59+08:00 \
  --output-dir output/alert_inspection_2026-06-05_oc_xxx
```

### B. 需要从飞书实时拉取时

1. 用 `feishu_im_user_get_messages` 按群和时间分页拉取。
2. 保存为 `raw_messages.json`。
3. 调用 `scripts/alert_inspection.py` 生成分析文件。
4. 回复用户摘要；如果有文件/压缩包，使用 `message` 工具发送，不要只返回 `MEDIA:` 标签。

## 回复用户模板

```text
已完成告警巡检分析。

结果摘要：
- 时间范围：...
- 命中消息：... 条
- 警告：... 条，恢复：... 条，未闭环：... 条
- 主要资源：...
- 风险等级：...
- 输出目录：...

核心判断：...
建议：...
```

## 注意事项

- 不要编造告警数据；没有拿到原始消息就不要声称已分析。
- 机器人名称不是稳定过滤条件，优先使用 sender id。
- 报告中要明确数据来源、过滤方式和精度风险。
- 不要输出 token、cookie、授权信息等敏感数据。
- 外发文件时遵循当前平台文件发送规则，使用 `message` 工具发送本地绝对路径。
