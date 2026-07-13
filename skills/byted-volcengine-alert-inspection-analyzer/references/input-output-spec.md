# 输入输出规格

## 标准输入

用户应提供：

```json
{
  "chat_id": "oc_xxx",
  "time": {
    "start_time": "2026-06-05T00:00:00+08:00",
    "end_time": "2026-06-05T23:59:59+08:00"
  },
  "bot": {
    "name": "云告警通知",
    "sender_id": "cli_xxx"
  },
  "output_dir": "output/alert_inspection_2026-06-05_oc_xxx"
}
```

## 原始消息输入文件

`scripts/alert_inspection.py` 支持两种 JSON：

1. 飞书工具直接返回对象：

```json
{
  "messages": [
    {
      "message_id": "om_xxx",
      "msg_type": "interactive",
      "content": "<card title=\"【警告】火山引擎云监控告警通知\">...",
      "sender": {"id": "cli_xxx", "sender_type": "app"},
      "create_time": "2026-06-05T02:02:55+08:00"
    }
  ],
  "has_more": false
}
```

2. 消息数组：

```json
[
  {"message_id": "om_xxx", "content": "..."}
]
```

## 输出目录

```text
output/alert_inspection_<date>_<chat_id>/
├── raw_messages.json
├── normalized_messages.json
├── analysis.json
├── report.md
└── run_meta.json
```

## analysis.json 关键字段

```json
{
  "meta": {},
  "analysis": {
    "summary": {
      "total_messages": 42,
      "warning_count": 22,
      "recovery_count": 20,
      "episode_count": 20,
      "unclosed_warning_count": 0,
      "risk_level": "中"
    },
    "by_policy": {},
    "by_metric": {},
    "by_resource": {},
    "warning_by_hour": {},
    "episodes": [],
    "unclosed_warnings": []
  }
}
```

## 风险等级

- 低：少量告警，全部恢复，无集中重复模式。
- 中：同一资源或指标反复告警，但均可恢复。
- 高：存在未恢复、严重告警、长时间持续或高频爆发。
