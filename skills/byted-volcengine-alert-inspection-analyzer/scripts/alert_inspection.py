#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normalize and analyze Feishu alert bot messages.

Input: JSON exported from feishu_im_user_get_messages, or an object containing `messages`.
Output directory:
- raw_messages.json
- normalized_messages.json
- analysis.json
- report.md
- run_meta.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_messages(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [m for m in obj if isinstance(m, dict)]
    if isinstance(obj, dict):
        if isinstance(obj.get("messages"), list):
            return [m for m in obj["messages"] if isinstance(m, dict)]
        if isinstance(obj.get("data"), dict) and isinstance(obj["data"].get("messages"), list):
            return [m for m in obj["data"]["messages"] if isinstance(m, dict)]
    raise ValueError("input JSON must be a list of messages or an object with messages[]")


def dedupe_messages(messages: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for m in messages:
        mid = m.get("message_id") or m.get("id") or json.dumps(m, ensure_ascii=False, sort_keys=True)
        if mid in seen:
            continue
        seen.add(mid)
        out.append(m)
    return out


def text_after_label(content: str, label: str) -> str:
    # Supports markdown card text like **告警策略**\n[value](url)
    pattern = rf"\*\*{re.escape(label)}\*\*\s*\n([^\n]+)"
    m = re.search(pattern, content)
    if not m:
        return ""
    val = m.group(1).strip()
    link = re.match(r"\[([^\]]+)\]\([^\)]+\)", val)
    return link.group(1).strip() if link else val


def extract_status(content: str) -> str:
    title = re.search(r"<card title=\"([^\"]+)\"", content)
    hay = title.group(1) if title else content[:120]
    if "已恢复" in hay:
        return "已恢复"
    if "严重" in hay:
        return "严重"
    if "警告" in hay:
        return "警告"
    return text_after_label(content, "告警级别").strip("「」") or "未知"


def extract_resource(content: str) -> str:
    # Prefer the ResourceId line, strip monitor link markdown tail if present.
    m = re.search(r"资源Id：([^\n]+)", content)
    if not m:
        return ""
    raw = m.group(1).strip()
    raw = raw.split("|[查看监控详情]")[0]
    return raw


def extract_metric_value(content: str) -> Tuple[str, str]:
    # Current value line examples:
    # 当前值：AVG(监听器/平均响应时间)[1m]:2500ms---[创建屏蔽策略]
    m = re.search(r"当前值：([^\n]+)", content)
    if not m:
        return "", ""
    raw = m.group(1).strip().split("---")[0].strip()
    if ":" in raw:
        metric, value = raw.rsplit(":", 1)
        return metric.strip(), value.strip()
    return raw, ""


def normalize_message(m: Dict[str, Any]) -> Dict[str, Any]:
    content = str(m.get("content") or "")
    metric, current_value = extract_metric_value(content)
    sender = m.get("sender") or {}
    return {
        "message_id": m.get("message_id") or m.get("id") or "",
        "create_time": m.get("create_time") or m.get("timestamp") or "",
        "status": extract_status(content),
        "policy": text_after_label(content, "告警策略"),
        "account": text_after_label(content, "账号"),
        "region": text_after_label(content, "地域"),
        "project": text_after_label(content, "项目"),
        "alert_time": text_after_label(content, "告警时间"),
        "resource": extract_resource(content),
        "metric": metric,
        "current_value": current_value,
        "msg_type": m.get("msg_type") or "",
        "sender": sender,
        "content": content,
    }


def matches_filter(m: Dict[str, Any], bot_sender_id: str = "", keyword: str = "") -> bool:
    sender = m.get("sender") or {}
    if bot_sender_id and sender.get("id") != bot_sender_id:
        return False
    if keyword and keyword not in str(m.get("content") or ""):
        return False
    return True


def parse_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def build_episodes(messages: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    episodes: List[Dict[str, Any]] = []
    open_warns: List[Dict[str, Any]] = []
    for m in messages:
        status = m.get("status")
        if status in {"警告", "严重"}:
            open_warns.append(m)
        elif status == "已恢复":
            if open_warns:
                start = open_warns[0]
                st = parse_dt(start.get("create_time", ""))
                et = parse_dt(m.get("create_time", ""))
                duration = round((et - st).total_seconds() / 60, 1) if st and et else None
                episodes.append({
                    "start_time": start.get("create_time"),
                    "end_time": m.get("create_time"),
                    "duration_minutes": duration,
                    "warning_count": len(open_warns),
                    "policy": start.get("policy"),
                    "resource": start.get("resource"),
                    "metric": start.get("metric"),
                    "warning_values": [w.get("current_value") for w in open_warns],
                    "recovery_message_id": m.get("message_id"),
                    "warning_message_ids": [w.get("message_id") for w in open_warns],
                    "closed": True,
                })
                open_warns = []
            else:
                episodes.append({
                    "start_time": None,
                    "end_time": m.get("create_time"),
                    "duration_minutes": None,
                    "warning_count": 0,
                    "policy": m.get("policy"),
                    "resource": m.get("resource"),
                    "metric": m.get("metric"),
                    "warning_values": [],
                    "recovery_message_id": m.get("message_id"),
                    "warning_message_ids": [],
                    "closed": True,
                })
    return episodes, open_warns


def counter_dict(items: Iterable[Any]) -> Dict[str, int]:
    return dict(Counter(str(x or "未识别") for x in items))


def analyze(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    episodes, unclosed = build_episodes(messages)
    warning_messages = [m for m in messages if m.get("status") in {"警告", "严重"}]
    recovery_messages = [m for m in messages if m.get("status") == "已恢复"]
    hours = []
    for m in messages:
        dt = parse_dt(m.get("create_time", ""))
        if dt:
            hours.append(dt.hour)
    warning_hours = []
    for m in warning_messages:
        dt = parse_dt(m.get("create_time", ""))
        if dt:
            warning_hours.append(dt.hour)

    max_duration = max([e.get("duration_minutes") or 0 for e in episodes], default=0)
    repeated_resource = Counter(m.get("resource") for m in warning_messages).most_common(1)
    repeated_metric = Counter(m.get("metric") for m in warning_messages).most_common(1)

    risk = "低"
    reasons = []
    if unclosed:
        risk = "高"
        reasons.append(f"存在 {len(unclosed)} 条未恢复告警")
    if len(warning_messages) >= 10 or (repeated_resource and repeated_resource[0][1] >= 5):
        risk = "中" if risk != "高" else risk
        reasons.append("同一资源或指标反复触发告警")
    if max_duration >= 30:
        risk = "高"
        reasons.append("存在持续时间较长的告警事件")
    if not reasons:
        reasons.append("告警数量较少且均已恢复")

    return {
        "summary": {
            "total_messages": len(messages),
            "warning_count": len(warning_messages),
            "recovery_count": len(recovery_messages),
            "unknown_count": len([m for m in messages if m.get("status") == "未知"]),
            "episode_count": len(episodes),
            "unclosed_warning_count": len(unclosed),
            "risk_level": risk,
            "risk_reasons": reasons,
            "first_message_time": messages[0].get("create_time") if messages else "",
            "last_message_time": messages[-1].get("create_time") if messages else "",
        },
        "by_policy": counter_dict(m.get("policy") for m in messages),
        "by_metric": counter_dict(m.get("metric") for m in messages),
        "by_resource": counter_dict(m.get("resource") for m in messages),
        "by_hour": dict(sorted(Counter(hours).items())),
        "warning_by_hour": dict(sorted(Counter(warning_hours).items())),
        "episodes": episodes,
        "unclosed_warnings": unclosed,
        "top_repeated_resource": repeated_resource[0] if repeated_resource else None,
        "top_repeated_metric": repeated_metric[0] if repeated_metric else None,
    }


def render_report(meta: Dict[str, Any], analysis: Dict[str, Any]) -> str:
    s = analysis["summary"]
    lines = [
        "# 飞书告警巡检分析报告",
        "",
        "## 一、巡检范围",
        f"- 群聊：{meta.get('chat_id')}",
        f"- 机器人：{meta.get('bot_name') or meta.get('bot_sender_id') or '未指定'}",
        f"- 机器人 sender id：{meta.get('bot_sender_id') or '未指定'}",
        f"- 时间范围：{meta.get('start_time') or ''} ~ {meta.get('end_time') or ''}",
        f"- 过滤方式：{meta.get('filter_mode')}",
        "",
        "## 二、总体结论",
        f"- 命中消息数：{s['total_messages']} 条",
        f"- 警告：{s['warning_count']} 条",
        f"- 恢复：{s['recovery_count']} 条",
        f"- 告警事件周期：{s['episode_count']} 个",
        f"- 未闭环告警：{s['unclosed_warning_count']} 条",
        f"- 风险等级：{s['risk_level']}",
        "",
        "风险原因：",
    ]
    for r in s.get("risk_reasons", []):
        lines.append(f"- {r}")

    lines.extend(["", "## 三、策略统计"])
    for k, v in analysis.get("by_policy", {}).items():
        lines.append(f"- {k}：{v} 条")

    lines.extend(["", "## 四、指标统计"])
    for k, v in analysis.get("by_metric", {}).items():
        lines.append(f"- {k}：{v} 条")

    lines.extend(["", "## 五、小时分布"])
    for k, v in analysis.get("warning_by_hour", {}).items():
        lines.append(f"- {k}:00：{v} 次警告")

    lines.extend(["", "## 六、告警闭环"])
    if analysis.get("episodes"):
        for idx, e in enumerate(analysis["episodes"], 1):
            lines.append(
                f"- 事件 {idx}：{e.get('start_time')} ~ {e.get('end_time')}，"
                f"持续 {e.get('duration_minutes')} 分钟，警告 {e.get('warning_count')} 次，"
                f"策略：{e.get('policy') or '未识别'}，资源：{e.get('resource') or '未识别'}"
            )
    else:
        lines.append("- 未识别到完整告警事件周期。")

    lines.extend([
        "",
        "## 七、建议",
        "- 优先排查重复触发次数最高的资源和指标，确认是否存在后端慢响应、容量瓶颈或定时任务冲击。",
        "- 对集中时段进行日志、监控曲线和业务发布/任务记录关联分析。",
        "- 如果告警均短时恢复但频繁触发，先确认业务影响，再评估是否优化阈值、持续周期或聚合规则。",
        "- 对未闭环或长时间持续的告警应立即升级处理。",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Analyze Feishu alert bot messages")
    ap.add_argument("--input", required=True, help="Raw messages JSON path")
    ap.add_argument("--output-dir", required=True, help="Output directory")
    ap.add_argument("--chat-id", default="")
    ap.add_argument("--bot-name", default="")
    ap.add_argument("--bot-sender-id", default="")
    ap.add_argument("--keyword", default="")
    ap.add_argument("--start-time", default="")
    ap.add_argument("--end-time", default="")
    args = ap.parse_args()

    input_path = Path(args.input)
    out = Path(args.output_dir)
    raw_obj = load_json(input_path)
    raw_messages = dedupe_messages(extract_messages(raw_obj))
    filtered = [m for m in raw_messages if matches_filter(m, args.bot_sender_id, args.keyword)]
    normalized = [normalize_message(m) for m in filtered]
    normalized.sort(key=lambda x: x.get("create_time") or "")

    filter_mode = "bot_sender_id" if args.bot_sender_id else ("keyword_only" if args.keyword else "none")
    meta = {
        "chat_id": args.chat_id,
        "bot_name": args.bot_name,
        "bot_sender_id": args.bot_sender_id,
        "keyword": args.keyword,
        "filter_mode": filter_mode,
        "start_time": args.start_time,
        "end_time": args.end_time,
        "raw_message_count": len(raw_messages),
        "message_count": len(normalized),
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "input_path": str(input_path),
    }
    analysis = analyze(normalized)
    report = render_report(meta, analysis)

    out.mkdir(parents=True, exist_ok=True)
    dump_json(out / "raw_messages.json", {"meta": meta, "messages": raw_messages})
    dump_json(out / "normalized_messages.json", {"meta": meta, "messages": normalized})
    dump_json(out / "analysis.json", {"meta": meta, "analysis": analysis})
    dump_json(out / "run_meta.json", meta)
    (out / "report.md").write_text(report, encoding="utf-8")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
