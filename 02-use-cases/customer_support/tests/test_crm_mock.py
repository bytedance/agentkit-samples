from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "crm_mock.py"
SPEC = importlib.util.spec_from_file_location("customer_support_crm_mock", MODULE_PATH)
crm_mock = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(crm_mock)

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
        "description": "设备无法连接网络",
        "technician": "李师傅",
        "service_date": "2024-02-01 09:30:00",
        "estimated_duration": 90,
    }
    data.update(overrides)
    return crm_mock.ServiceRecordCreate(**data)


def test_get_customer_info_returns_known_customer_profile():
    customer = crm_mock.get_customer_info("CUST001")

    assert customer["customer_id"] == "CUST001"
    assert customer["name"] == "张明"
    assert customer["total_purchases"] == 3
    assert customer["communication_preferences"] == ["email", "sms"]


def test_get_customer_info_returns_error_for_unknown_customer():
    assert crm_mock.get_customer_info("CUST404") == {"error": "Customer not found"}


def test_get_customer_purchases_returns_active_products():
    purchases = crm_mock.get_customer_purchases("CUST001")

    assert len(purchases) == 2
    assert {item["serial_number"] for item in purchases} == {
        "SN20240001",
        "SN20240002",
    }
    assert all(item["status"] == "active" for item in purchases)


def test_get_customer_purchases_returns_empty_list_for_unknown_customer():
    assert crm_mock.get_customer_purchases("missing") == []


@pytest.mark.parametrize(
    ("serial_number", "expected_status"),
    [
        ("SN20240001", "保修有效"),
        ("SN20240002", "保修已经过期"),
    ],
)
def test_query_warranty_returns_status_for_known_products(
    serial_number, expected_status
):
    warranty = crm_mock.query_warranty(serial_number)

    assert warranty["serial_number"] == serial_number
    assert warranty["customer_id"] == "CUST001"
    assert warranty["status_text"] == expected_status


def test_query_warranty_returns_error_for_unknown_serial_number():
    assert crm_mock.query_warranty("SN00000000") == {"error": "Warranty not found"}


def test_get_service_records_returns_module_level_records_for_known_customer():
    records = crm_mock.get_service_records("CUST001")

    assert records is crm_mock.mock_service_records
    assert records[0]["record_id"] == "SRV001"


def test_get_service_records_returns_empty_list_for_unknown_customer():
    assert crm_mock.get_service_records("CUST404") == []


def test_create_service_record_appends_scheduled_record():
    record = make_service_record()

    created = crm_mock.create_service_record("CUST001", record)

    assert created["record_id"] == "SRV002"
    assert created["serial_number"] == "SN20240002"
    assert created["status"] == "scheduled"
    assert created["actual_duration"] is None
    assert created["notes"] is None
    assert crm_mock.mock_service_records[-1] == created


def test_create_service_record_rejects_unknown_customer():
    created = crm_mock.create_service_record("CUST404", make_service_record())

    assert created == {"error": "Customer not found"}
    assert crm_mock.mock_service_records == BASE_RECORDS


def test_update_service_record_changes_only_provided_fields():
    update = crm_mock.ServiceRecordUpdate(status="in_progress", notes="已联系客户")

    updated = crm_mock.update_service_record("CUST001", "SRV001", update)

    assert updated["status"] == "in_progress"
    assert updated["notes"] == "已联系客户"
    assert updated["service_date"] == BASE_RECORDS[0]["service_date"]
    assert updated["actual_duration"] == BASE_RECORDS[0]["actual_duration"]


def test_update_service_record_can_change_actual_duration():
    update = crm_mock.ServiceRecordUpdate(actual_duration=130)

    updated = crm_mock.update_service_record("CUST001", "SRV001", update)

    assert updated["actual_duration"] == 130
    assert updated["status"] == "completed"


def test_update_service_record_rejects_unknown_customer():
    update = crm_mock.ServiceRecordUpdate(status="cancelled")

    assert crm_mock.update_service_record("CUST404", "SRV001", update) == {
        "error": "Customer not found"
    }


def test_update_service_record_returns_error_for_unknown_service_id():
    update = crm_mock.ServiceRecordUpdate(status="cancelled")

    assert crm_mock.update_service_record("CUST001", "SRV404", update) == {
        "error": "Service record not found"
    }


def test_delete_service_record_removes_matching_record():
    result = crm_mock.delete_service_record("CUST001", "SRV001")

    assert result == {"service_id": "SRV001", "status": "deleted"}
    assert crm_mock.mock_service_records == []


def test_delete_service_record_rejects_unknown_customer():
    assert crm_mock.delete_service_record("CUST404", "SRV001") == {
        "error": "Customer not found"
    }
    assert crm_mock.mock_service_records == BASE_RECORDS


def test_delete_service_record_returns_error_for_unknown_service_id():
    assert crm_mock.delete_service_record("CUST001", "SRV404") == {
        "error": "Service record not found"
    }
    assert crm_mock.mock_service_records == BASE_RECORDS


def test_get_service_case_brief_summarizes_customer_after_sale_context():
    crm_mock.create_service_record(
        "CUST001",
        make_service_record(
            service_type="软件调试",
            service_date="2024-02-01 09:30:00",
            technician="李师傅",
        ),
    )

    brief = crm_mock.get_service_case_brief("CUST001")

    assert brief["customer_name"] == "张明"
    assert brief["owned_product_count"] == 2
    assert brief["active_service_record_count"] == 1
    assert brief["active_service_records"][0]["record_id"] == "SRV002"
    assert brief["warranty_status"]["SN20240001"]["status_text"] == "保修有效"
    assert brief["warranty_status"]["SN20240002"]["status_text"] == "保修已经过期"
    assert "先确认已有维修单进度，避免重复创建工单" in brief["next_actions"]
    assert "涉及过保商品时，需先确认客户是否接受自费维修" in brief["next_actions"]


def test_get_service_case_brief_rejects_unknown_customer():
    assert crm_mock.get_service_case_brief("CUST404") == {"error": "Customer not found"}


def test_get_available_service_slots_respects_product_ownership_skill_and_conflicts():
    crm_mock.create_service_record(
        "CUST001",
        make_service_record(
            service_type="屏幕维修",
            service_date="2024-02-01 09:00:00",
            technician="王师傅",
            estimated_duration=120,
        ),
    )

    result = crm_mock.get_available_service_slots(
        "CUST001",
        "SN20240001",
        "屏幕维修",
        preferred_date="2024-02-01",
        estimated_duration=90,
        limit=3,
    )

    assert result["product_name"] == "智能电视 65寸"
    assert [slot["technician"] for slot in result["slots"]] == ["王师傅", "王师傅", "王师傅"]
    assert [slot["service_date"] for slot in result["slots"]] == [
        "2024-02-01 14:00:00",
        "2024-02-01 15:30:00",
        "2024-02-01 17:00:00",
    ]
    assert all(slot["warranty_status"] == "保修有效" for slot in result["slots"])


def test_get_available_service_slots_validates_inputs():
    assert crm_mock.get_available_service_slots(
        "CUST404", "SN20240001", "屏幕维修", preferred_date="2024-02-01"
    ) == {"error": "Customer not found"}
    assert crm_mock.get_available_service_slots(
        "CUST001", "SN404", "屏幕维修", preferred_date="2024-02-01"
    ) == {"error": "Product not found for customer"}
    assert crm_mock.get_available_service_slots(
        "CUST001", "SN20240001", "屏幕维修", preferred_date="2024/02/01"
    ) == {"error": "preferred_date must use YYYY-MM-DD format"}
    assert crm_mock.get_available_service_slots(
        "CUST001",
        "SN20240001",
        "屏幕维修",
        preferred_date="2024-02-01",
        estimated_duration=0,
    ) == {"error": "estimated_duration must be greater than 0"}


def test_verify_customer_identity_requires_two_matching_fields():
    assert crm_mock.verify_customer_identity("CUST001", email="zhang.ming@example.com") == {
        "customer_id": "CUST001",
        "verified": False,
        "matched_fields": ["email"],
        "message": "Need at least two identity fields for verification",
    }

    result = crm_mock.verify_customer_identity(
        "CUST001",
        name="张明",
        email="zhang.ming@example.com",
        date_of_birth="1990-01-01",
    )

    assert result == {
        "customer_id": "CUST001",
        "verified": True,
        "matched_fields": ["name", "email"],
        "failed_fields": ["date_of_birth"],
    }


def test_schedule_service_record_requires_confirmation_before_creating_record():
    result = crm_mock.schedule_service_record(
        "CUST001",
        "SN20240001",
        "屏幕维修",
        "电视屏幕出现黑线",
        "2024-02-01 14:00:00",
        "王师傅",
        estimated_duration=90,
    )

    assert result["status"] == "confirmation_required"
    assert result["pending_record"]["product_name"] == "智能电视 65寸"
    assert result["pending_record"]["warranty_status"] == "保修有效"
    assert crm_mock.mock_service_records == BASE_RECORDS


def test_schedule_service_record_creates_confirmed_record_with_warranty_notice():
    created = crm_mock.schedule_service_record(
        "CUST001",
        "SN20240002",
        "软件调试",
        "智能音箱无法连接 Wi-Fi",
        "2024-02-01 14:00:00",
        "李师傅",
        estimated_duration=90,
        customer_confirmed=True,
    )

    assert created["record_id"] == "SRV002"
    assert created["serial_number"] == "SN20240002"
    assert created["status"] == "scheduled"
    assert created["warranty_status"] == "保修已经过期"
    assert created["billing_notice"] == "商品已过保，维修前需再次确认自费维修意愿"
    assert crm_mock.mock_service_records[-1] == created


def test_schedule_service_record_rejects_conflicting_or_unqualified_assignment():
    crm_mock.create_service_record(
        "CUST001",
        make_service_record(
            service_type="屏幕维修",
            service_date="2024-02-01 14:00:00",
            technician="王师傅",
            estimated_duration=120,
        ),
    )

    conflict = crm_mock.schedule_service_record(
        "CUST001",
        "SN20240001",
        "屏幕维修",
        "电视屏幕闪烁",
        "2024-02-01 14:30:00",
        "王师傅",
        estimated_duration=90,
        customer_confirmed=True,
    )
    wrong_skill = crm_mock.schedule_service_record(
        "CUST001",
        "SN20240001",
        "屏幕维修",
        "电视屏幕闪烁",
        "2024-02-01 17:00:00",
        "李师傅",
        estimated_duration=90,
        customer_confirmed=True,
    )

    assert conflict["error"] == "Technician schedule conflict"
    assert conflict["available_slots"][0]["service_date"] == "2024-02-01 17:00:00"
    assert wrong_skill == {"error": "Technician cannot handle requested service_type"}


def test_reschedule_service_record_updates_active_record_and_preserves_conflict_rules():
    record = crm_mock.create_service_record(
        "CUST001",
        make_service_record(
            service_type="软件调试",
            service_date="2024-02-01 09:30:00",
            technician="李师傅",
        ),
    )
    crm_mock.create_service_record(
        "CUST001",
        make_service_record(
            service_type="软件调试",
            service_date="2024-02-01 14:00:00",
            technician="李师傅",
        ),
    )

    conflict = crm_mock.reschedule_service_record(
        "CUST001", record["record_id"], "2024-02-01 14:30:00"
    )
    updated = crm_mock.reschedule_service_record(
        "CUST001", record["record_id"], "2024-02-02 10:30:00", estimated_duration=60
    )

    assert conflict == {"error": "Technician schedule conflict"}
    assert updated["service_date"] == "2024-02-02 10:30:00"
    assert updated["estimated_duration"] == 60
    assert updated["status"] == "scheduled"
    assert updated["notes"] == "已改约至 2024-02-02 10:30:00"


def test_reschedule_service_record_rejects_finalized_records():
    assert crm_mock.reschedule_service_record(
        "CUST001", "SRV001", "2024-02-01 10:30:00"
    ) == {"error": "Finalized service record cannot be rescheduled"}
