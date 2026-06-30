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

from datetime import datetime, timedelta
from typing import Optional

from tools.crm_mock import (
    ACTIVE_SERVICE_STATUSES,
    get_available_service_slots,
    get_customer_info,
    get_customer_purchases,
    get_service_records,
    query_warranty,
)


ISSUE_RULES = [
    {
        "category": "screen",
        "service_type": "屏幕维修",
        "severity": "high",
        "keywords": ["屏幕", "黑屏", "花屏", "竖线", "横线", "裂", "显示"],
        "first_steps": [
            "确认是否外接设备或信号源导致显示异常",
            "断电 60 秒后重新开机观察屏幕表现",
            "拍摄屏幕异常照片，便于维修前判断是否涉及面板",
        ],
        "questions": [
            "屏幕是否有外力磕碰或进液痕迹？",
            "异常是开机即出现，还是使用一段时间后出现？",
        ],
    },
    {
        "category": "power",
        "service_type": "硬件维修",
        "severity": "high",
        "keywords": ["不开机", "无法开机", "断电", "电源", "自动关机", "重启"],
        "first_steps": [
            "确认插座、电源线和适配器连接正常",
            "移除外接设备后再次开机",
            "长按电源键 10 秒进行硬重启",
        ],
        "questions": [
            "电源指示灯是否亮起？",
            "是否更换过插座或电源线测试？",
        ],
    },
    {
        "category": "network",
        "service_type": "软件调试",
        "severity": "medium",
        "keywords": ["wifi", "Wi-Fi", "网络", "联网", "蓝牙", "连接", "掉线"],
        "first_steps": [
            "重启路由器和设备后重新连接",
            "忘记当前网络后重新输入密码",
            "确认同一网络下其他设备是否可正常联网",
        ],
        "questions": [
            "是否只有该设备无法联网？",
            "近期是否更换过路由器、宽带或网络密码？",
        ],
    },
    {
        "category": "audio",
        "service_type": "硬件维修",
        "severity": "medium",
        "keywords": ["声音", "音量", "扬声器", "杂音", "无声", "麦克风"],
        "first_steps": [
            "检查是否处于静音或外接音频输出模式",
            "恢复声音设置后再次播放测试音频",
            "更换片源或 App 排除内容源问题",
        ],
        "questions": [
            "所有 App 都无声，还是特定 App 无声？",
            "是否连接过蓝牙音箱或耳机？",
        ],
    },
    {
        "category": "general",
        "service_type": "上门检测",
        "severity": "medium",
        "keywords": [],
        "first_steps": [
            "记录故障发生时间、频率和最近一次操作",
            "尝试重启设备并观察是否复现",
            "准备产品序列号和购买信息",
        ],
        "questions": [
            "故障是否可以稳定复现？",
            "近期是否升级系统、安装应用或移动设备位置？",
        ],
    },
]

SERVICE_ESTIMATE_RULES = {
    "屏幕维修": {
        "base_duration": 120,
        "covered_labor_fee": 0,
        "out_of_warranty_labor_fee": 180,
        "covered_parts_fee_range": [0, 0],
        "out_of_warranty_parts_fee_range": [600, 1800],
        "sla_hours": 48,
    },
    "硬件维修": {
        "base_duration": 120,
        "covered_labor_fee": 0,
        "out_of_warranty_labor_fee": 150,
        "covered_parts_fee_range": [0, 0],
        "out_of_warranty_parts_fee_range": [200, 900],
        "sla_hours": 48,
    },
    "软件调试": {
        "base_duration": 90,
        "covered_labor_fee": 0,
        "out_of_warranty_labor_fee": 80,
        "covered_parts_fee_range": [0, 0],
        "out_of_warranty_parts_fee_range": [0, 0],
        "sla_hours": 24,
    },
    "上门检测": {
        "base_duration": 60,
        "covered_labor_fee": 0,
        "out_of_warranty_labor_fee": 60,
        "covered_parts_fee_range": [0, 0],
        "out_of_warranty_parts_fee_range": [0, 0],
        "sla_hours": 24,
    },
}

RISK_RULES = [
    {
        "code": "duplicate_active_record",
        "severity": "high",
        "message": "客户已有进行中的维修单，需先确认是否为同一问题",
    },
    {
        "code": "out_of_warranty",
        "severity": "medium",
        "message": "商品已过保，创建维修单前需确认客户接受可能产生的费用",
    },
    {
        "code": "high_impact_issue",
        "severity": "medium",
        "message": "故障影响核心使用能力，建议优先提供最近可约时段",
    },
]

STATUS_LABELS = {
    "scheduled": "已预约",
    "in_progress": "处理中",
    "completed": "已完成",
    "cancelled": "已取消",
    "deleted": "已删除",
}


def _normalize_text(text: Optional[str]) -> str:
    return (text or "").strip()


def _select_issue_rule(issue_description: str) -> dict:
    normalized = issue_description.lower()
    for rule in ISSUE_RULES:
        if any(keyword.lower() in normalized for keyword in rule["keywords"]):
            return rule
    return ISSUE_RULES[-1]


def _find_purchase(customer_id: str, serial_number: str) -> Optional[dict]:
    for purchase in get_customer_purchases(customer_id):
        if purchase["serial_number"] == serial_number:
            return purchase
    return None


def _active_records_for_serial(customer_id: str, serial_number: str) -> list[dict]:
    return [
        record
        for record in get_service_records(customer_id)
        if record["serial_number"] == serial_number
        and record["status"] in ACTIVE_SERVICE_STATUSES
    ]


def _is_out_of_warranty(warranty: dict) -> bool:
    return warranty.get("status_text") == "保修已经过期"


def _estimate_visit_window(preferred_date: Optional[str], sla_hours: int) -> dict:
    if preferred_date:
        try:
            start = datetime.strptime(preferred_date, "%Y-%m-%d")
        except ValueError:
            start = datetime.now()
    else:
        start = datetime.now()
    latest = start + timedelta(hours=sla_hours)
    return {
        "earliest_date": start.strftime("%Y-%m-%d"),
        "latest_response_before": latest.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _format_status(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def _parse_record_date(record: dict) -> Optional[datetime]:
    service_date = record.get("service_date")
    if not service_date:
        return None
    try:
        return datetime.strptime(service_date, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _record_age_days(record: dict, reference_time: datetime) -> Optional[int]:
    service_date = _parse_record_date(record)
    if service_date is None:
        return None
    return (reference_time.date() - service_date.date()).days


def triage_service_issue(issue_description: str, serial_number: Optional[str] = None) -> dict:
    """根据用户描述进行售后故障分诊，返回推荐服务类型和追问项。"""
    description = _normalize_text(issue_description)
    if not description:
        return {"error": "issue_description is required"}

    rule = _select_issue_rule(description)
    needs_photo = rule["category"] in {"screen", "power"}
    return {
        "serial_number": serial_number,
        "category": rule["category"],
        "service_type": rule["service_type"],
        "severity": rule["severity"],
        "first_steps": rule["first_steps"],
        "clarifying_questions": rule["questions"],
        "needs_photo": needs_photo,
        "requires_service": rule["severity"] == "high",
    }


def estimate_service_cost(
    customer_id: str,
    serial_number: str,
    service_type: str,
    preferred_date: Optional[str] = None,
) -> dict:
    """基于保修状态和服务类型估算时长、费用和响应窗口。"""
    customer = get_customer_info(customer_id)
    if "error" in customer:
        return customer
    purchase = _find_purchase(customer_id, serial_number)
    if purchase is None:
        return {"error": "Product not found for customer"}

    rule = SERVICE_ESTIMATE_RULES.get(service_type, SERVICE_ESTIMATE_RULES["上门检测"])
    warranty = query_warranty(serial_number)
    out_of_warranty = _is_out_of_warranty(warranty)
    estimate = {
        "customer_id": customer_id,
        "serial_number": serial_number,
        "product_name": purchase["product_name"],
        "service_type": service_type,
        "warranty_status": warranty["status_text"],
        "estimated_duration": rule["base_duration"],
        "labor_fee": (
            rule["out_of_warranty_labor_fee"]
            if out_of_warranty
            else rule["covered_labor_fee"]
        ),
        "parts_fee_range": (
            rule["out_of_warranty_parts_fee_range"]
            if out_of_warranty
            else rule["covered_parts_fee_range"]
        ),
        "visit_window": _estimate_visit_window(preferred_date, rule["sla_hours"]),
        "disclaimers": [
            "最终费用以工程师现场检测结果为准",
            "涉及人为损坏、进液或非授权维修痕迹时，可能不适用免费保修",
        ],
    }
    if out_of_warranty:
        estimate["customer_confirmation_required"] = "需确认客户接受自费维修"
    return estimate


def assess_service_risks(
    customer_id: str,
    serial_number: str,
    issue_description: str,
) -> dict:
    """识别创建维修单前的业务风险，供客服决定是否继续推进。"""
    customer = get_customer_info(customer_id)
    if "error" in customer:
        return customer
    purchase = _find_purchase(customer_id, serial_number)
    if purchase is None:
        return {"error": "Product not found for customer"}

    triage = triage_service_issue(issue_description, serial_number=serial_number)
    warranty = query_warranty(serial_number)
    active_records = _active_records_for_serial(customer_id, serial_number)
    risks = []

    if active_records:
        risks.append(RISK_RULES[0])
    if _is_out_of_warranty(warranty):
        risks.append(RISK_RULES[1])
    if triage.get("severity") == "high":
        risks.append(RISK_RULES[2])

    can_schedule = not any(risk["code"] == "duplicate_active_record" for risk in risks)
    return {
        "customer_id": customer_id,
        "serial_number": serial_number,
        "product_name": purchase["product_name"],
        "triage": triage,
        "warranty_status": warranty["status_text"],
        "active_record_ids": [record["record_id"] for record in active_records],
        "risks": risks,
        "can_schedule_without_manual_review": can_schedule,
    }


def recommend_service_plan(
    customer_id: str,
    serial_number: str,
    issue_description: str,
    preferred_date: Optional[str] = None,
    customer_verified: bool = False,
) -> dict:
    """给出客服可执行的下一步方案：分诊、费用预估、风险、可约时段。"""
    risk_assessment = assess_service_risks(customer_id, serial_number, issue_description)
    if "error" in risk_assessment:
        return risk_assessment

    service_type = risk_assessment["triage"]["service_type"]
    cost_estimate = estimate_service_cost(
        customer_id,
        serial_number,
        service_type,
        preferred_date=preferred_date,
    )
    slots = get_available_service_slots(
        customer_id,
        serial_number,
        service_type,
        preferred_date=preferred_date,
        estimated_duration=cost_estimate["estimated_duration"],
        limit=3,
    )

    next_steps = []
    if not customer_verified:
        next_steps.append("先完成至少两项身份信息核验")
    next_steps.extend(risk_assessment["triage"]["first_steps"])
    if risk_assessment["can_schedule_without_manual_review"]:
        next_steps.append("向客户展示费用预估和可预约时段，获得明确确认后创建维修单")
    else:
        next_steps.append("先核对已有维修单是否已覆盖当前问题，再决定是否新建工单")

    return {
        "customer_id": customer_id,
        "serial_number": serial_number,
        "product_name": risk_assessment["product_name"],
        "triage": risk_assessment["triage"],
        "cost_estimate": cost_estimate,
        "risks": risk_assessment["risks"],
        "available_slots": slots.get("slots", []),
        "next_steps": next_steps,
        "ready_to_schedule": (
            customer_verified
            and risk_assessment["can_schedule_without_manual_review"]
            and bool(slots.get("slots"))
        ),
    }


def build_service_completion_summary(customer_id: str, service_id: str) -> dict:
    """生成维修完成摘要，用于客服回访或沉淀到长期记忆。"""
    customer = get_customer_info(customer_id)
    if "error" in customer:
        return customer

    matched_record = None
    for record in get_service_records(customer_id):
        if record["record_id"] == service_id:
            matched_record = record
            break
    if matched_record is None:
        return {"error": "Service record not found"}

    warranty = query_warranty(matched_record["serial_number"])
    completion_ready = matched_record["status"] == "completed"
    follow_up_items = []
    if completion_ready:
        follow_up_items.append("确认客户设备是否恢复正常")
        follow_up_items.append("提醒客户保留维修记录和服务单号")
    else:
        follow_up_items.append("维修单尚未完成，先同步当前进度和下一步安排")
    if _is_out_of_warranty(warranty):
        follow_up_items.append("如已产生费用，确认客户已知晓收费原因")

    return {
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "service_id": service_id,
        "serial_number": matched_record["serial_number"],
        "service_type": matched_record["service_type"],
        "status": matched_record["status"],
        "technician": matched_record["technician"],
        "service_date": matched_record["service_date"],
        "actual_duration": matched_record["actual_duration"],
        "warranty_status": warranty.get("status_text"),
        "completion_ready": completion_ready,
        "customer_facing_summary": (
            f"{customer['name']}的{matched_record['service_type']}服务"
            f"当前状态为{matched_record['status']}，服务单号为{service_id}。"
        ),
        "follow_up_items": follow_up_items,
    }


def analyze_service_backlog(
    customer_id: str,
    reference_time: Optional[str] = None,
) -> dict:
    """分析客户维修单积压情况，帮助客服判断是否需要升级处理。"""
    customer = get_customer_info(customer_id)
    if "error" in customer:
        return customer

    if reference_time:
        try:
            now = datetime.strptime(reference_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return {"error": "reference_time must use YYYY-MM-DD HH:MM:SS format"}
    else:
        now = datetime.now()

    records = get_service_records(customer_id)
    active_records = [
        record for record in records if record["status"] in ACTIVE_SERVICE_STATUSES
    ]
    completed_records = [
        record for record in records if record["status"] == "completed"
    ]
    overdue_records = []
    upcoming_records = []
    status_counts = {}

    for record in records:
        status_counts[record["status"]] = status_counts.get(record["status"], 0) + 1
        service_date = _parse_record_date(record)
        if service_date is None:
            continue
        if record["status"] in ACTIVE_SERVICE_STATUSES and service_date < now:
            overdue_records.append(record)
        elif record["status"] in ACTIVE_SERVICE_STATUSES:
            upcoming_records.append(record)

    escalation_required = bool(overdue_records) or len(active_records) >= 3
    recommendations = []
    if overdue_records:
        recommendations.append("存在已过预约时间但未完成的维修单，建议优先联系客户同步进度")
    if upcoming_records:
        recommendations.append("提醒客户保留预约时间段并保持联系方式畅通")
    if completed_records and not active_records:
        recommendations.append("可进行服务回访，确认问题是否彻底解决")

    return {
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "status_counts": status_counts,
        "active_record_count": len(active_records),
        "completed_record_count": len(completed_records),
        "overdue_record_ids": [record["record_id"] for record in overdue_records],
        "upcoming_record_ids": [record["record_id"] for record in upcoming_records],
        "escalation_required": escalation_required,
        "recommendations": recommendations,
    }


def score_service_record_health(
    customer_id: str,
    service_id: str,
    reference_time: Optional[str] = None,
) -> dict:
    """给单个维修单计算健康度分数，突出延迟、过保、缺少备注等风险。"""
    customer = get_customer_info(customer_id)
    if "error" in customer:
        return customer
    if reference_time:
        try:
            now = datetime.strptime(reference_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return {"error": "reference_time must use YYYY-MM-DD HH:MM:SS format"}
    else:
        now = datetime.now()

    record = None
    for candidate in get_service_records(customer_id):
        if candidate["record_id"] == service_id:
            record = candidate
            break
    if record is None:
        return {"error": "Service record not found"}

    warranty = query_warranty(record["serial_number"])
    score = 100
    flags = []
    age_days = _record_age_days(record, now)
    service_date = _parse_record_date(record)

    if record["status"] in ACTIVE_SERVICE_STATUSES and service_date and service_date < now:
        score -= 30
        flags.append("appointment_overdue")
        if age_days is not None and age_days >= 3:
            score -= 20
            flags.append("long_overdue")
    if _is_out_of_warranty(warranty):
        score -= 10
        flags.append("out_of_warranty")
    if record["status"] == "completed" and not record.get("notes"):
        score -= 15
        flags.append("missing_completion_notes")
    if record["actual_duration"] and record["actual_duration"] > record["estimated_duration"]:
        score -= 10
        flags.append("duration_overrun")

    health = "good"
    if score < 60:
        health = "poor"
    elif score < 80:
        health = "attention"

    return {
        "customer_id": customer_id,
        "service_id": service_id,
        "status": record["status"],
        "status_label": _format_status(record["status"]),
        "score": max(score, 0),
        "health": health,
        "flags": flags,
        "age_days": age_days,
        "warranty_status": warranty.get("status_text"),
    }


def prepare_customer_follow_up(
    customer_id: str,
    service_id: str,
    satisfaction_score: Optional[int] = None,
) -> dict:
    """生成客服回访建议，覆盖未完成、低满意度和过保收费解释场景。"""
    summary = build_service_completion_summary(customer_id, service_id)
    if "error" in summary:
        return summary

    follow_up_type = "progress_update"
    if summary["completion_ready"]:
        follow_up_type = "completion_check"
    if satisfaction_score is not None and satisfaction_score <= 2:
        follow_up_type = "service_recovery"

    talking_points = list(summary["follow_up_items"])
    if satisfaction_score is not None:
        talking_points.append(f"记录客户满意度评分：{satisfaction_score}/5")
    if follow_up_type == "service_recovery":
        talking_points.append("询问不满意原因，并承诺反馈给服务主管跟进")
    elif follow_up_type == "completion_check":
        talking_points.append("确认客户是否愿意对本次服务进行评价")
    else:
        talking_points.append("说明下一步处理节点和预计反馈时间")

    return {
        "customer_id": customer_id,
        "service_id": service_id,
        "follow_up_type": follow_up_type,
        "customer_facing_summary": summary["customer_facing_summary"],
        "talking_points": talking_points,
        "should_save_to_memory": summary["completion_ready"]
        and (satisfaction_score is None or satisfaction_score >= 4),
    }
