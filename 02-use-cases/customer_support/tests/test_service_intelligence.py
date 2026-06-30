from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from tools import crm_mock
from tools import service_intelligence as intelligence


BASE_RECORDS = copy.deepcopy(crm_mock.mock_service_records)


@pytest.fixture(autouse=True)
def reset_service_records():
    crm_mock.mock_service_records[:] = copy.deepcopy(BASE_RECORDS)
    yield
    crm_mock.mock_service_records[:] = copy.deepcopy(BASE_RECORDS)


def make_service_record(**overrides):
    data = {
        "serial_number": "SN20240001",
        "service_type": "屏幕维修",
        "description": "屏幕出现竖线",
        "technician": "王师傅",
        "service_date": "2024-02-01 09:00:00",
        "estimated_duration": 120,
    }
    data.update(overrides)
    return crm_mock.ServiceRecordCreate(**data)


@pytest.mark.parametrize(
    ("description", "category", "service_type", "requires_service"),
    [
        ("电视屏幕出现竖线和花屏", "screen", "屏幕维修", True),
        ("智能音箱 Wi-Fi 总是掉线", "network", "软件调试", False),
        ("设备无法开机，电源灯不亮", "power", "硬件维修", True),
        ("声音有杂音", "audio", "硬件维修", False),
        ("使用体验不太对", "general", "上门检测", False),
    ],
)
def test_triage_service_issue_maps_symptoms_to_actionable_categories(
    description, category, service_type, requires_service
):
    result = intelligence.triage_service_issue(description, serial_number="SN20240001")

    assert result["category"] == category
    assert result["service_type"] == service_type
    assert result["requires_service"] is requires_service
    assert result["clarifying_questions"]
    assert result["first_steps"]


def test_triage_service_issue_requires_description():
    assert intelligence.triage_service_issue("   ") == {
        "error": "issue_description is required"
    }


def test_estimate_service_cost_uses_warranty_status_and_service_type():
    covered = intelligence.estimate_service_cost(
        "CUST001",
        "SN20240001",
        "屏幕维修",
        preferred_date="2024-02-01",
    )
    expired = intelligence.estimate_service_cost(
        "CUST001",
        "SN20240002",
        "软件调试",
        preferred_date="2024-02-01",
    )

    assert covered["product_name"] == "智能电视 65寸"
    assert covered["labor_fee"] == 0
    assert covered["parts_fee_range"] == [0, 0]
    assert covered["estimated_duration"] == 120
    assert covered["visit_window"]["earliest_date"] == "2024-02-01"
    assert expired["warranty_status"] == "保修已经过期"
    assert expired["labor_fee"] == 80
    assert expired["customer_confirmation_required"] == "需确认客户接受自费维修"


def test_estimate_service_cost_rejects_unknown_customer_or_product():
    assert intelligence.estimate_service_cost("CUST404", "SN20240001", "屏幕维修") == {
        "error": "Customer not found"
    }
    assert intelligence.estimate_service_cost("CUST001", "SN404", "屏幕维修") == {
        "error": "Product not found for customer"
    }


def test_assess_service_risks_detects_duplicate_out_of_warranty_and_high_impact():
    crm_mock.create_service_record(
        "CUST001",
        make_service_record(
            serial_number="SN20240002",
            service_type="硬件维修",
            description="设备无法开机",
            technician="王师傅",
        ),
    )

    result = intelligence.assess_service_risks(
        "CUST001",
        "SN20240002",
        "设备无法开机，电源灯不亮",
    )

    assert result["product_name"] == "智能音箱 Pro"
    assert result["active_record_ids"] == ["SRV002"]
    assert [risk["code"] for risk in result["risks"]] == [
        "duplicate_active_record",
        "out_of_warranty",
        "high_impact_issue",
    ]
    assert result["can_schedule_without_manual_review"] is False


def test_recommend_service_plan_combines_triage_cost_risk_and_slots():
    result = intelligence.recommend_service_plan(
        "CUST001",
        "SN20240001",
        "电视屏幕出现竖线",
        preferred_date="2024-02-01",
        customer_verified=True,
    )

    assert result["ready_to_schedule"] is True
    assert result["triage"]["service_type"] == "屏幕维修"
    assert result["cost_estimate"]["estimated_duration"] == 120
    assert result["available_slots"][0]["service_date"] == "2024-02-01 09:00:00"
    assert result["next_steps"][-1] == "向客户展示费用预估和可预约时段，获得明确确认后创建维修单"


def test_recommend_service_plan_requires_identity_before_ready_to_schedule():
    result = intelligence.recommend_service_plan(
        "CUST001",
        "SN20240001",
        "电视屏幕出现竖线",
        preferred_date="2024-02-01",
        customer_verified=False,
    )

    assert result["ready_to_schedule"] is False
    assert result["next_steps"][0] == "先完成至少两项身份信息核验"


def test_build_service_completion_summary_for_completed_record():
    result = intelligence.build_service_completion_summary("CUST001", "SRV001")

    assert result["customer_name"] == "张明"
    assert result["service_id"] == "SRV001"
    assert result["completion_ready"] is True
    assert result["customer_facing_summary"] == (
        "张明的屏幕维修服务当前状态为completed，服务单号为SRV001。"
    )
    assert "确认客户设备是否恢复正常" in result["follow_up_items"]


def test_build_service_completion_summary_for_open_record():
    created = crm_mock.create_service_record(
        "CUST001",
        make_service_record(
            service_type="软件调试",
            technician="李师傅",
            serial_number="SN20240002",
        ),
    )

    result = intelligence.build_service_completion_summary(
        "CUST001",
        created["record_id"],
    )

    assert result["completion_ready"] is False
    assert "维修单尚未完成，先同步当前进度和下一步安排" in result["follow_up_items"]
    assert "如已产生费用，确认客户已知晓收费原因" in result["follow_up_items"]


def test_build_service_completion_summary_rejects_unknown_record():
    assert intelligence.build_service_completion_summary("CUST001", "SRV404") == {
        "error": "Service record not found"
    }


def test_analyze_service_backlog_identifies_overdue_and_upcoming_records():
    overdue = crm_mock.create_service_record(
        "CUST001",
        make_service_record(
            service_date="2024-02-01 09:00:00",
            technician="王师傅",
        ),
    )
    upcoming = crm_mock.create_service_record(
        "CUST001",
        make_service_record(
            service_type="软件调试",
            serial_number="SN20240002",
            service_date="2024-02-03 14:00:00",
            technician="李师傅",
        ),
    )

    result = intelligence.analyze_service_backlog(
        "CUST001",
        reference_time="2024-02-02 10:00:00",
    )

    assert result["status_counts"] == {"completed": 1, "scheduled": 2}
    assert result["active_record_count"] == 2
    assert result["completed_record_count"] == 1
    assert result["overdue_record_ids"] == [overdue["record_id"]]
    assert result["upcoming_record_ids"] == [upcoming["record_id"]]
    assert result["escalation_required"] is True
    assert "存在已过预约时间但未完成的维修单，建议优先联系客户同步进度" in result[
        "recommendations"
    ]


def test_analyze_service_backlog_validates_reference_time():
    assert intelligence.analyze_service_backlog(
        "CUST001",
        reference_time="2024-02-02",
    ) == {"error": "reference_time must use YYYY-MM-DD HH:MM:SS format"}


def test_score_service_record_health_flags_overdue_out_of_warranty_records():
    created = crm_mock.create_service_record(
        "CUST001",
        make_service_record(
            serial_number="SN20240002",
            service_type="软件调试",
            service_date="2024-02-01 09:00:00",
            technician="李师傅",
        ),
    )

    result = intelligence.score_service_record_health(
        "CUST001",
        created["record_id"],
        reference_time="2024-02-03 10:00:00",
    )

    assert result["status_label"] == "已预约"
    assert result["score"] == 60
    assert result["health"] == "attention"
    assert result["flags"] == ["appointment_overdue", "out_of_warranty"]
    assert result["age_days"] == 2


def test_score_service_record_health_flags_long_overdue_records():
    created = crm_mock.create_service_record(
        "CUST001",
        make_service_record(
            serial_number="SN20240002",
            service_type="软件调试",
            service_date="2024-02-01 09:00:00",
            technician="李师傅",
        ),
    )

    result = intelligence.score_service_record_health(
        "CUST001",
        created["record_id"],
        reference_time="2024-02-10 10:00:00",
    )

    assert result["score"] == 40
    assert result["health"] == "poor"
    assert result["flags"] == [
        "appointment_overdue",
        "long_overdue",
        "out_of_warranty",
    ]


def test_score_service_record_health_flags_duration_overrun():
    update = crm_mock.ServiceRecordUpdate(actual_duration=180, notes="")
    crm_mock.update_service_record("CUST001", "SRV001", update)

    result = intelligence.score_service_record_health(
        "CUST001",
        "SRV001",
        reference_time="2024-02-03 10:00:00",
    )

    assert result["status_label"] == "已完成"
    assert result["flags"] == ["duration_overrun"]
    assert result["score"] == 90


def test_prepare_customer_follow_up_for_completion_and_recovery():
    completed = intelligence.prepare_customer_follow_up(
        "CUST001",
        "SRV001",
        satisfaction_score=5,
    )
    recovery = intelligence.prepare_customer_follow_up(
        "CUST001",
        "SRV001",
        satisfaction_score=1,
    )

    assert completed["follow_up_type"] == "completion_check"
    assert completed["should_save_to_memory"] is True
    assert "确认客户是否愿意对本次服务进行评价" in completed["talking_points"]
    assert recovery["follow_up_type"] == "service_recovery"
    assert recovery["should_save_to_memory"] is False
    assert "询问不满意原因，并承诺反馈给服务主管跟进" in recovery["talking_points"]


def test_prepare_customer_follow_up_for_open_record():
    created = crm_mock.create_service_record(
        "CUST001",
        make_service_record(
            service_type="软件调试",
            serial_number="SN20240002",
            technician="李师傅",
        ),
    )

    result = intelligence.prepare_customer_follow_up("CUST001", created["record_id"])

    assert result["follow_up_type"] == "progress_update"
    assert result["should_save_to_memory"] is False
    assert "说明下一步处理节点和预计反馈时间" in result["talking_points"]
