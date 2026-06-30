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
