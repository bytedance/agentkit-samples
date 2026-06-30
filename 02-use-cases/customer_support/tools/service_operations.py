# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from datetime import datetime
from typing import Optional

from tools.crm_mock import (
    ACTIVE_SERVICE_STATUSES,
    get_customer_info,
    get_customer_purchases,
    get_service_records,
    query_warranty,
)
from tools.customer_recovery import summarize_recovery_case
from tools.service_intelligence import (
    analyze_service_backlog,
    prepare_customer_follow_up,
    score_service_record_health,
)


PRIORITY_WEIGHTS = {
    "appointment_overdue": 35,
    "long_overdue": 30,
    "out_of_warranty": 10,
    "missing_completion_notes": 10,
    "duration_overrun": 15,
}

CONTACT_CHANNEL_PRIORITY = ["sms", "email", "phone"]


def _parse_reference_time(reference_time: Optional[str]) -> datetime | dict:
    if not reference_time:
        return datetime.now()
    try:
        return datetime.strptime(reference_time, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return {"error": "reference_time must use YYYY-MM-DD HH:MM:SS format"}


def _parse_service_date(record: dict) -> Optional[datetime]:
    try:
        return datetime.strptime(record["service_date"], "%Y-%m-%d %H:%M:%S")
    except (KeyError, ValueError):
        return None


def _preferred_contact_channel(customer: dict) -> str:
    preferences = customer.get("communication_preferences", [])
    for channel in CONTACT_CHANNEL_PRIORITY:
        if channel in preferences:
            return channel
    return preferences[0] if preferences else "email"


def _calculate_priority_score(health: dict, record: dict, now: datetime) -> int:
    score = 0
    for flag in health.get("flags", []):
        score += PRIORITY_WEIGHTS.get(flag, 0)
    if record["status"] in ACTIVE_SERVICE_STATUSES:
        score += 20
    service_date = _parse_service_date(record)
    if service_date and service_date < now:
        score += min(30, max(0, (now.date() - service_date.date()).days) * 5)
    return min(score, 100)


def build_service_dashboard(
    customer_id: str,
    reference_time: Optional[str] = None,
) -> dict:
    """生成客户服务运营视图，聚合工单、保修、积压和主动关怀信号。"""
    customer = get_customer_info(customer_id)
    if "error" in customer:
        return customer
    parsed_time = _parse_reference_time(reference_time)
    if isinstance(parsed_time, dict):
        return parsed_time
    now = parsed_time

    records = get_service_records(customer_id)
    purchases = get_customer_purchases(customer_id)
    backlog = analyze_service_backlog(
        customer_id,
        reference_time=now.strftime("%Y-%m-%d %H:%M:%S"),
    )
    recovery = summarize_recovery_case(
        customer_id,
        reference_time=now.strftime("%Y-%m-%d %H:%M:%S"),
    )
    record_health = [
        score_service_record_health(
            customer_id,
            record["record_id"],
            reference_time=now.strftime("%Y-%m-%d %H:%M:%S"),
        )
        for record in records
    ]
    warranty_counts = {"valid": 0, "expired": 0}
    for purchase in purchases:
        warranty = query_warranty(purchase["serial_number"])
        if warranty["status_text"] == "保修已经过期":
            warranty_counts["expired"] += 1
        else:
            warranty_counts["valid"] += 1

    return {
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "preferred_contact_channel": _preferred_contact_channel(customer),
        "service_record_count": len(records),
        "active_record_count": backlog["active_record_count"],
        "completed_record_count": backlog["completed_record_count"],
        "warranty_counts": warranty_counts,
        "escalation_required": backlog["escalation_required"]
        or recovery["proactive_care_required"],
        "record_health": record_health,
        "recommendations": backlog["recommendations"] + recovery["proactive_reasons"],
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
    }


def build_priority_work_queue(
    customer_id: str,
    reference_time: Optional[str] = None,
    limit: int = 10,
) -> dict:
    """按风险优先级生成客服待办队列。"""
    customer = get_customer_info(customer_id)
    if "error" in customer:
        return customer
    parsed_time = _parse_reference_time(reference_time)
    if isinstance(parsed_time, dict):
        return parsed_time
    now = parsed_time

    queue_items = []
    for record in get_service_records(customer_id):
        health = score_service_record_health(
            customer_id,
            record["record_id"],
            reference_time=now.strftime("%Y-%m-%d %H:%M:%S"),
        )
        priority_score = _calculate_priority_score(health, record, now)
        if priority_score == 0 and record["status"] == "completed":
            continue
        queue_items.append(
            {
                "customer_id": customer_id,
                "service_id": record["record_id"],
                "status": record["status"],
                "priority_score": priority_score,
                "health": health["health"],
                "flags": health["flags"],
                "recommended_action": _recommended_action_for_queue_item(
                    record,
                    health,
                ),
            }
        )

    queue_items.sort(
        key=lambda item: (-item["priority_score"], item["service_id"])
    )
    return {
        "customer_id": customer_id,
        "queue_size": len(queue_items),
        "items": queue_items[:limit],
    }


def _recommended_action_for_queue_item(record: dict, health: dict) -> str:
    flags = set(health.get("flags", []))
    if "long_overdue" in flags:
        return "立即升级服务调度并向客户解释延误原因"
    if "appointment_overdue" in flags:
        return "联系工程师确认当前处理状态并同步客户"
    if record["status"] in ACTIVE_SERVICE_STATUSES:
        return "在预约时间前提醒客户保持联系方式畅通"
    if "missing_completion_notes" in flags:
        return "补充维修完成备注后再进行回访"
    return "按常规节奏进行客户回访"


def create_follow_up_tasks(
    customer_id: str,
    reference_time: Optional[str] = None,
) -> dict:
    """根据维修单状态生成结构化回访任务。"""
    customer = get_customer_info(customer_id)
    if "error" in customer:
        return customer
    parsed_time = _parse_reference_time(reference_time)
    if isinstance(parsed_time, dict):
        return parsed_time
    now = parsed_time

    tasks = []
    channel = _preferred_contact_channel(customer)
    for record in get_service_records(customer_id):
        health = score_service_record_health(
            customer_id,
            record["record_id"],
            reference_time=now.strftime("%Y-%m-%d %H:%M:%S"),
        )
        follow_up = prepare_customer_follow_up(customer_id, record["record_id"])
        if record["status"] == "completed" or health["flags"]:
            tasks.append(
                {
                    "task_id": f"FOLLOW-{record['record_id']}",
                    "customer_id": customer_id,
                    "service_id": record["record_id"],
                    "channel": channel,
                    "priority": "high" if health["health"] == "poor" else "normal",
                    "reason": _task_reason(record, health),
                    "talking_points": follow_up["talking_points"],
                    "due_before": now.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

    return {
        "customer_id": customer_id,
        "task_count": len(tasks),
        "tasks": tasks,
    }


def _task_reason(record: dict, health: dict) -> str:
    if "long_overdue" in health["flags"]:
        return "维修单长时间逾期，需要主动安抚"
    if "appointment_overdue" in health["flags"]:
        return "维修单已过预约时间，需要同步进度"
    if record["status"] == "completed":
        return "维修已完成，需要确认客户问题是否解决"
    return "存在服务风险，需要跟进"


def summarize_service_metrics(
    customer_id: str,
    reference_time: Optional[str] = None,
) -> dict:
    """计算客户维度服务指标，方便展示在运营看板或长期记忆中。"""
    customer = get_customer_info(customer_id)
    if "error" in customer:
        return customer
    parsed_time = _parse_reference_time(reference_time)
    if isinstance(parsed_time, dict):
        return parsed_time
    now = parsed_time

    records = get_service_records(customer_id)
    if not records:
        return {
            "customer_id": customer_id,
            "total_records": 0,
            "completion_rate": 0,
            "average_actual_duration": None,
            "overdue_rate": 0,
            "risk_index": 0,
        }

    completed = [record for record in records if record["status"] == "completed"]
    durations = [
        record["actual_duration"]
        for record in completed
        if record.get("actual_duration") is not None
    ]
    health_scores = [
        score_service_record_health(
            customer_id,
            record["record_id"],
            reference_time=now.strftime("%Y-%m-%d %H:%M:%S"),
        )["score"]
        for record in records
    ]
    overdue_count = len(
        [
            record
            for record in records
            if record["status"] in ACTIVE_SERVICE_STATUSES
            and _parse_service_date(record)
            and _parse_service_date(record) < now
        ]
    )

    return {
        "customer_id": customer_id,
        "total_records": len(records),
        "completion_rate": round(len(completed) / len(records), 2),
        "average_actual_duration": (
            round(sum(durations) / len(durations), 2) if durations else None
        ),
        "overdue_rate": round(overdue_count / len(records), 2),
        "risk_index": round(100 - (sum(health_scores) / len(health_scores)), 2),
    }
