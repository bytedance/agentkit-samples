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
from tools.service_intelligence import (
    analyze_service_backlog,
    build_service_completion_summary,
    score_service_record_health,
)


SENTIMENT_RULES = [
    {
        "level": "critical",
        "score": 95,
        "keywords": [
            "投诉",
            "举报",
            "曝光",
            "监管",
            "消协",
            "起诉",
            "律师",
            "媒体",
        ],
        "signals": ["regulatory", "legal", "public_escalation"],
    },
    {
        "level": "angry",
        "score": 80,
        "keywords": [
            "生气",
            "愤怒",
            "太差",
            "差评",
            "退款",
            "赔偿",
            "不能接受",
            "失望",
        ],
        "signals": ["dissatisfaction", "compensation_requested"],
    },
    {
        "level": "anxious",
        "score": 60,
        "keywords": [
            "着急",
            "急用",
            "什么时候",
            "多久",
            "催",
            "没消息",
            "耽误",
        ],
        "signals": ["time_pressure", "status_uncertainty"],
    },
    {
        "level": "neutral",
        "score": 30,
        "keywords": [],
        "signals": [],
    },
]

COMPENSATION_POLICY = {
    "critical": {
        "max_amount": 300,
        "options": [
            "升级主管 2 小时内回电",
            "优先安排最近可用工程师",
            "在核实责任后提供服务券或配件费用减免",
        ],
        "requires_manager_approval": True,
    },
    "angry": {
        "max_amount": 150,
        "options": [
            "优先安排维修进度跟进",
            "提供延保权益或服务券",
            "对已确认的服务延误提供费用减免申请",
        ],
        "requires_manager_approval": True,
    },
    "anxious": {
        "max_amount": 50,
        "options": [
            "提供明确下一次反馈时间",
            "提醒工程师优先联系客户",
            "必要时提供小额服务券安抚",
        ],
        "requires_manager_approval": False,
    },
    "neutral": {
        "max_amount": 0,
        "options": [
            "清晰说明当前进度和下一步安排",
            "提供自助排查建议和预约时段",
        ],
        "requires_manager_approval": False,
    },
}

ESCALATION_MATRIX = {
    "critical": {
        "queue": "manager_priority",
        "deadline_minutes": 30,
        "owner": "客服主管",
    },
    "angry": {
        "queue": "senior_agent",
        "deadline_minutes": 120,
        "owner": "资深客服",
    },
    "anxious": {
        "queue": "service_dispatch",
        "deadline_minutes": 240,
        "owner": "服务调度",
    },
    "neutral": {
        "queue": "frontline_agent",
        "deadline_minutes": 480,
        "owner": "一线客服",
    },
}


def _normalize_text(text: Optional[str]) -> str:
    return (text or "").strip()


def _match_sentiment_rule(text: str) -> dict:
    normalized = text.lower()
    for rule in SENTIMENT_RULES:
        if any(keyword.lower() in normalized for keyword in rule["keywords"]):
            return rule
    return SENTIMENT_RULES[-1]


def _find_service_record(customer_id: str, service_id: Optional[str]) -> Optional[dict]:
    if not service_id:
        return None
    for record in get_service_records(customer_id):
        if record["record_id"] == service_id:
            return record
    return None


def _latest_service_record(customer_id: str) -> Optional[dict]:
    records = get_service_records(customer_id)
    if not records:
        return None
    return sorted(records, key=lambda record: record["service_date"], reverse=True)[0]


def _count_active_records(customer_id: str) -> int:
    return len(
        [
            record
            for record in get_service_records(customer_id)
            if record["status"] in ACTIVE_SERVICE_STATUSES
        ]
    )


def detect_customer_sentiment(message: str) -> dict:
    """识别客户当前情绪和升级信号，供客服选择响应策略。"""
    text = _normalize_text(message)
    if not text:
        return {"error": "message is required"}

    rule = _match_sentiment_rule(text)
    intensity = rule["score"]
    if len(text) >= 120 and rule["level"] != "neutral":
        intensity = min(100, intensity + 5)
    if "！" in text or "!" in text:
        intensity = min(100, intensity + 5)

    return {
        "sentiment_level": rule["level"],
        "intensity": intensity,
        "signals": rule["signals"],
        "requires_empathy_first": rule["level"] in {"critical", "angry", "anxious"},
        "summary": _summarize_customer_message(text),
    }


def _summarize_customer_message(text: str) -> str:
    if len(text) <= 60:
        return text
    return text[:57] + "..."


def build_escalation_plan(
    customer_id: str,
    message: str,
    service_id: Optional[str] = None,
    reference_time: Optional[str] = None,
) -> dict:
    """结合情绪、维修单健康度和积压情况生成升级处理方案。"""
    customer = get_customer_info(customer_id)
    if "error" in customer:
        return customer

    sentiment = detect_customer_sentiment(message)
    if "error" in sentiment:
        return sentiment

    service_record = _find_service_record(customer_id, service_id) or _latest_service_record(
        customer_id
    )
    health = None
    if service_record:
        health = score_service_record_health(
            customer_id,
            service_record["record_id"],
            reference_time=reference_time,
        )
    backlog = analyze_service_backlog(customer_id, reference_time=reference_time)
    escalation_level = sentiment["sentiment_level"]
    if health and health.get("health") == "poor":
        escalation_level = "critical"
    elif backlog.get("escalation_required") and escalation_level == "neutral":
        escalation_level = "anxious"

    matrix = ESCALATION_MATRIX[escalation_level]
    action_items = [
        "先表达理解和歉意，不争辩责任归属",
        "复述客户核心诉求并确认期望结果",
        "给出明确下一步负责人和反馈时限",
    ]
    if service_record:
        action_items.append(f"核对维修单 {service_record['record_id']} 的最新状态")
    if backlog.get("overdue_record_ids"):
        action_items.append("优先处理逾期维修单并同步预计完成时间")

    return {
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "sentiment": sentiment,
        "service_id": service_record["record_id"] if service_record else None,
        "escalation_level": escalation_level,
        "queue": matrix["queue"],
        "owner": matrix["owner"],
        "deadline_minutes": matrix["deadline_minutes"],
        "action_items": action_items,
        "health": health,
        "backlog": backlog,
    }


def recommend_compensation(
    customer_id: str,
    message: str,
    service_id: Optional[str] = None,
    reference_time: Optional[str] = None,
) -> dict:
    """根据投诉强度、维修单状态和客户价值给出补偿建议。"""
    plan = build_escalation_plan(
        customer_id,
        message,
        service_id=service_id,
        reference_time=reference_time,
    )
    if "error" in plan:
        return plan

    customer = get_customer_info(customer_id)
    policy = COMPENSATION_POLICY[plan["escalation_level"]]
    lifetime_value = customer.get("lifetime_value", 0)
    max_amount = policy["max_amount"]
    if lifetime_value >= 20000 and max_amount > 0:
        max_amount = int(max_amount * 1.2)

    compensation_reasons = [f"当前客户情绪等级：{plan['escalation_level']}"]
    if plan["backlog"].get("overdue_record_ids"):
        compensation_reasons.append("存在逾期维修单")
    if plan["health"] and "out_of_warranty" in plan["health"].get("flags", []):
        compensation_reasons.append("商品过保，补偿需避免承诺免费维修")

    return {
        "customer_id": customer_id,
        "service_id": plan["service_id"],
        "recommended_options": policy["options"],
        "max_compensation_amount": max_amount,
        "requires_manager_approval": policy["requires_manager_approval"],
        "reasons": compensation_reasons,
        "constraints": [
            "不得承诺超出政策范围的现金赔付",
            "补偿需记录客户确认结果",
            "涉及费用减免时以最终检测和主管审批为准",
        ],
    }


def build_manager_handoff(
    customer_id: str,
    message: str,
    service_id: Optional[str] = None,
    reference_time: Optional[str] = None,
) -> dict:
    """生成主管交接包，减少升级时的信息丢失。"""
    plan = build_escalation_plan(
        customer_id,
        message,
        service_id=service_id,
        reference_time=reference_time,
    )
    if "error" in plan:
        return plan
    compensation = recommend_compensation(
        customer_id,
        message,
        service_id=plan["service_id"],
        reference_time=reference_time,
    )
    customer = get_customer_info(customer_id)
    purchases = get_customer_purchases(customer_id)

    handoff_notes = [
        f"客户：{customer['name']}（{customer_id}）",
        f"升级级别：{plan['escalation_level']}，处理队列：{plan['queue']}",
        f"客户诉求摘要：{plan['sentiment']['summary']}",
    ]
    if plan["service_id"]:
        handoff_notes.append(f"关联维修单：{plan['service_id']}")
    if compensation.get("recommended_options"):
        handoff_notes.append(
            "建议补偿选项：" + "；".join(compensation["recommended_options"][:2])
        )

    return {
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "contact_email": customer["email"],
        "owned_products": [
            {
                "serial_number": purchase["serial_number"],
                "product_name": purchase["product_name"],
                "warranty_end_date": purchase["warranty_end_date"],
            }
            for purchase in purchases
        ],
        "escalation_plan": plan,
        "compensation": compensation,
        "handoff_notes": handoff_notes,
        "manager_brief": "\n".join(handoff_notes),
    }


def draft_recovery_response(
    customer_id: str,
    message: str,
    service_id: Optional[str] = None,
    reference_time: Optional[str] = None,
) -> dict:
    """生成客服可改写后发送的安抚回复草稿。"""
    plan = build_escalation_plan(
        customer_id,
        message,
        service_id=service_id,
        reference_time=reference_time,
    )
    if "error" in plan:
        return plan

    customer_name = plan["customer_name"]
    deadline = plan["deadline_minutes"]
    opening = f"{customer_name}，非常抱歉这次服务让您产生了不好的体验。"
    if plan["sentiment"]["sentiment_level"] == "anxious":
        opening = f"{customer_name}，我理解您现在比较着急，我会先帮您确认进度。"
    elif plan["sentiment"]["sentiment_level"] == "neutral":
        opening = f"{customer_name}，我来帮您核对当前服务进展。"

    status_sentence = "我会整理当前信息并推动下一步处理。"
    if plan["service_id"]:
        status_sentence = f"我会优先核对维修单 {plan['service_id']} 的状态。"
    if plan["backlog"].get("overdue_record_ids"):
        status_sentence += " 目前存在已过预约时间的记录，我会优先推动服务调度确认原因。"

    response = (
        f"{opening}{status_sentence}"
        f"接下来将由{plan['owner']}跟进，预计在 {deadline} 分钟内给您明确反馈。"
        "在确认前我不会随意承诺费用减免或处理结果，但会把您的诉求完整记录并同步给相关负责人。"
    )

    return {
        "customer_id": customer_id,
        "service_id": plan["service_id"],
        "tone": plan["sentiment"]["sentiment_level"],
        "response": response,
        "must_include": [
            "表达理解",
            "说明下一步负责人",
            "给出反馈时限",
            "避免超范围承诺",
        ],
        "avoid": [
            "指责客户操作不当",
            "直接承诺无条件退款",
            "透露内部系统或审批流程细节",
        ],
    }


def summarize_recovery_case(
    customer_id: str,
    service_id: Optional[str] = None,
    reference_time: Optional[str] = None,
) -> dict:
    """汇总客户恢复服务视角，便于 agent 判断是否需要主动关怀。"""
    customer = get_customer_info(customer_id)
    if "error" in customer:
        return customer

    service_record = _find_service_record(customer_id, service_id) or _latest_service_record(
        customer_id
    )
    backlog = analyze_service_backlog(customer_id, reference_time=reference_time)
    latest_summary = None
    if service_record:
        latest_summary = build_service_completion_summary(
            customer_id,
            service_record["record_id"],
        )

    warranties = {
        purchase["serial_number"]: query_warranty(purchase["serial_number"])[
            "status_text"
        ]
        for purchase in get_customer_purchases(customer_id)
    }
    proactive_reasons = []
    if backlog.get("overdue_record_ids"):
        proactive_reasons.append("存在逾期维修单")
    if any(status == "保修已经过期" for status in warranties.values()):
        proactive_reasons.append("客户名下存在过保商品，沟通费用时需更谨慎")
    if latest_summary and not latest_summary["completion_ready"]:
        proactive_reasons.append("最近维修单尚未完成")

    return {
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "active_record_count": backlog.get("active_record_count", 0),
        "latest_service_id": service_record["record_id"] if service_record else None,
        "latest_service_summary": latest_summary,
        "warranty_status": warranties,
        "proactive_care_required": bool(proactive_reasons),
        "proactive_reasons": proactive_reasons,
        "generated_at": (
            reference_time if reference_time else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ),
    }
