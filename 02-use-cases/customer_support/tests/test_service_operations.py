from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from tools import crm_mock
from tools import service_operations as operations


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


def test_build_service_dashboard_aggregates_records_warranty_and_recommendations():
    crm_mock.create_service_record(
        "CUST001",
        make_service_record(service_date="2024-02-01 09:00:00"),
    )

    dashboard = operations.build_service_dashboard(
        "CUST001",
        reference_time="2024-02-03 10:00:00",
    )

    assert dashboard["customer_name"] == "张明"
    assert dashboard["preferred_contact_channel"] == "sms"
    assert dashboard["service_record_count"] == 2
    assert dashboard["active_record_count"] == 1
    assert dashboard["completed_record_count"] == 1
    assert dashboard["warranty_counts"] == {"valid": 1, "expired": 1}
    assert dashboard["escalation_required"] is True
    assert dashboard["record_health"][1]["flags"] == [
        "appointment_overdue",
        "out_of_warranty",
    ]
    assert "存在逾期维修单" in dashboard["recommendations"]


def test_build_priority_work_queue_orders_by_risk():
    overdue = crm_mock.create_service_record(
        "CUST001",
        make_service_record(service_date="2024-02-01 09:00:00"),
    )
    upcoming = crm_mock.create_service_record(
        "CUST001",
        make_service_record(service_date="2024-02-06 09:00:00"),
    )

    queue = operations.build_priority_work_queue(
        "CUST001",
        reference_time="2024-02-05 10:00:00",
    )

    assert queue["queue_size"] == 3
    assert queue["items"][0]["service_id"] == overdue["record_id"]
    assert queue["items"][0]["priority_score"] == 100
    assert queue["items"][0]["recommended_action"] == "立即升级服务调度并向客户解释延误原因"
    upcoming_item = next(
        item for item in queue["items"] if item["service_id"] == upcoming["record_id"]
    )
    assert upcoming_item["recommended_action"] == "在预约时间前提醒客户保持联系方式畅通"


def test_build_priority_work_queue_respects_limit():
    for index in range(3):
        crm_mock.create_service_record(
            "CUST001",
            make_service_record(
                service_date=f"2024-02-0{index + 1} 09:00:00",
                description=f"问题 {index}",
            ),
        )

    queue = operations.build_priority_work_queue(
        "CUST001",
        reference_time="2024-02-05 10:00:00",
        limit=2,
    )

    assert queue["queue_size"] == 4
    assert len(queue["items"]) == 2


def test_create_follow_up_tasks_for_completed_and_risky_records():
    created = crm_mock.create_service_record(
        "CUST001",
        make_service_record(service_date="2024-02-01 09:00:00"),
    )

    result = operations.create_follow_up_tasks(
        "CUST001",
        reference_time="2024-02-03 10:00:00",
    )

    assert result["task_count"] == 2
    assert result["tasks"][0]["task_id"] == "FOLLOW-SRV001"
    assert result["tasks"][0]["reason"] == "维修已完成，需要确认客户问题是否解决"
    assert result["tasks"][1]["service_id"] == created["record_id"]
    assert result["tasks"][1]["channel"] == "sms"
    assert result["tasks"][1]["reason"] == "维修单已过预约时间，需要同步进度"


def test_summarize_service_metrics_calculates_rates_and_risk_index():
    crm_mock.create_service_record(
        "CUST001",
        make_service_record(service_date="2024-02-01 09:00:00"),
    )

    metrics = operations.summarize_service_metrics(
        "CUST001",
        reference_time="2024-02-03 10:00:00",
    )

    assert metrics["total_records"] == 2
    assert metrics["completion_rate"] == 0.5
    assert metrics["average_actual_duration"] == 110
    assert metrics["overdue_rate"] == 0.5
    assert metrics["risk_index"] == 20


def test_service_operations_validate_customer_and_reference_time():
    assert operations.build_service_dashboard("CUST404") == {
        "error": "Customer not found"
    }
    assert operations.build_priority_work_queue(
        "CUST001",
        reference_time="2024-02-03",
    ) == {"error": "reference_time must use YYYY-MM-DD HH:MM:SS format"}
    assert operations.create_follow_up_tasks("CUST404") == {
        "error": "Customer not found"
    }
    assert operations.summarize_service_metrics(
        "CUST001",
        reference_time="2024-02-03",
    ) == {"error": "reference_time must use YYYY-MM-DD HH:MM:SS format"}
