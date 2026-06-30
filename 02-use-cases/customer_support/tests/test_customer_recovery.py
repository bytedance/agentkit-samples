from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from tools import crm_mock
from tools import customer_recovery as recovery


BASE_RECORDS = copy.deepcopy(crm_mock.mock_service_records)


@pytest.fixture(autouse=True)
def reset_service_records():
    crm_mock.mock_service_records[:] = copy.deepcopy(BASE_RECORDS)
    yield
    crm_mock.mock_service_records[:] = copy.deepcopy(BASE_RECORDS)


def make_service_record(**overrides):
    data = {
        "serial_number": "SN20240002",
        "service_type": "软件调试",
        "description": "智能音箱无法联网",
        "technician": "李师傅",
        "service_date": "2024-02-01 09:00:00",
        "estimated_duration": 90,
    }
    data.update(overrides)
    return crm_mock.ServiceRecordCreate(**data)


@pytest.mark.parametrize(
    ("message", "level", "requires_empathy"),
    [
        ("我要投诉你们，还要找消协举报", "critical", True),
        ("这次服务太差了，我要求赔偿", "angry", True),
        ("我很着急，什么时候能修好？", "anxious", True),
        ("帮我看一下维修进度", "neutral", False),
    ],
)
def test_detect_customer_sentiment_classifies_escalation_language(
    message, level, requires_empathy
):
    result = recovery.detect_customer_sentiment(message)

    assert result["sentiment_level"] == level
    assert result["requires_empathy_first"] is requires_empathy
    assert result["summary"] == message


def test_detect_customer_sentiment_requires_message():
    assert recovery.detect_customer_sentiment("   ") == {"error": "message is required"}


def test_build_escalation_plan_uses_sentiment_health_and_backlog():
    created = crm_mock.create_service_record(
        "CUST001",
        make_service_record(service_date="2024-02-01 09:00:00"),
    )

    result = recovery.build_escalation_plan(
        "CUST001",
        "我很着急，维修一直没消息",
        service_id=created["record_id"],
        reference_time="2024-02-03 10:00:00",
    )

    assert result["customer_name"] == "张明"
    assert result["service_id"] == created["record_id"]
    assert result["escalation_level"] == "anxious"
    assert result["queue"] == "service_dispatch"
    assert result["owner"] == "服务调度"
    assert result["deadline_minutes"] == 240
    assert "优先处理逾期维修单并同步预计完成时间" in result["action_items"]
    assert result["backlog"]["overdue_record_ids"] == [created["record_id"]]


def test_build_escalation_plan_promotes_poor_health_to_critical():
    created = crm_mock.create_service_record(
        "CUST001",
        make_service_record(service_date="2024-02-01 09:00:00"),
    )

    result = recovery.build_escalation_plan(
        "CUST001",
        "帮我看一下维修进度",
        service_id=created["record_id"],
        reference_time="2024-02-10 10:00:00",
    )

    assert result["escalation_level"] == "critical"
    assert result["queue"] == "manager_priority"
    assert result["health"]["health"] == "poor"


def test_recommend_compensation_scales_for_high_value_customer_and_flags_constraints():
    created = crm_mock.create_service_record(
        "CUST001",
        make_service_record(service_date="2024-02-01 09:00:00"),
    )

    result = recovery.recommend_compensation(
        "CUST001",
        "这次服务太差了，我要求赔偿",
        service_id=created["record_id"],
        reference_time="2024-02-03 10:00:00",
    )

    assert result["service_id"] == created["record_id"]
    assert result["max_compensation_amount"] == 180
    assert result["requires_manager_approval"] is True
    assert "存在逾期维修单" in result["reasons"]
    assert "不得承诺超出政策范围的现金赔付" in result["constraints"]


def test_build_manager_handoff_contains_customer_products_and_brief():
    created = crm_mock.create_service_record(
        "CUST001",
        make_service_record(service_date="2024-02-01 09:00:00"),
    )

    result = recovery.build_manager_handoff(
        "CUST001",
        "我要投诉你们，还要找媒体曝光",
        service_id=created["record_id"],
        reference_time="2024-02-03 10:00:00",
    )

    assert result["contact_email"] == "zhang.ming@example.com"
    assert len(result["owned_products"]) == 2
    assert result["escalation_plan"]["escalation_level"] == "critical"
    assert "客户：张明（CUST001）" in result["manager_brief"]
    assert f"关联维修单：{created['record_id']}" in result["handoff_notes"]


def test_draft_recovery_response_includes_owner_deadline_and_guardrails():
    created = crm_mock.create_service_record(
        "CUST001",
        make_service_record(service_date="2024-02-01 09:00:00"),
    )

    result = recovery.draft_recovery_response(
        "CUST001",
        "我很着急，怎么还没修好？",
        service_id=created["record_id"],
        reference_time="2024-02-03 10:00:00",
    )

    assert result["tone"] == "anxious"
    assert created["record_id"] in result["response"]
    assert "服务调度" in result["response"]
    assert "240 分钟内" in result["response"]
    assert "避免超范围承诺" in result["must_include"]
    assert "直接承诺无条件退款" in result["avoid"]


def test_summarize_recovery_case_marks_proactive_care_for_open_overdue_case():
    created = crm_mock.create_service_record(
        "CUST001",
        make_service_record(service_date="2024-02-01 09:00:00"),
    )

    result = recovery.summarize_recovery_case(
        "CUST001",
        service_id=created["record_id"],
        reference_time="2024-02-03 10:00:00",
    )

    assert result["latest_service_id"] == created["record_id"]
    assert result["active_record_count"] == 1
    assert result["proactive_care_required"] is True
    assert result["proactive_reasons"] == [
        "存在逾期维修单",
        "客户名下存在过保商品，沟通费用时需更谨慎",
        "最近维修单尚未完成",
    ]
    assert result["generated_at"] == "2024-02-03 10:00:00"


def test_customer_recovery_tools_reject_unknown_customer():
    assert recovery.build_escalation_plan("CUST404", "我要投诉") == {
        "error": "Customer not found"
    }
    assert recovery.summarize_recovery_case("CUST404") == {
        "error": "Customer not found"
    }
