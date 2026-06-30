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

from datetime import datetime, time, timedelta
from typing import Optional

from pydantic import BaseModel


class ServiceRecordCreate(BaseModel):
    serial_number: str
    service_type: str
    description: str
    technician: str
    service_date: str
    estimated_duration: int


class ServiceRecordUpdate(BaseModel):
    service_date: Optional[str] = None
    status: Optional[str] = None
    actual_duration: Optional[int] = None
    notes: Optional[str] = None


mock_service_records = [
    {
        "record_id": "SRV001",
        "serial_number": "SN20240001",
        "customer_id": "CUST001",
        "service_date": "2024-01-15 10:00:00",
        "service_type": "屏幕维修",
        "description": "屏幕出现竖线",
        "technician": "王师傅",
        "status": "completed",
        "estimated_duration": 120,
        "actual_duration": 110,
        "notes": "更换屏幕面板，测试正常",
    },
]

mock_technician_roster = [
    {
        "technician": "王师傅",
        "skills": ["屏幕维修", "硬件维修", "上门检测"],
        "service_areas": ["北京"],
    },
    {
        "technician": "李师傅",
        "skills": ["软件调试", "网络配置", "上门检测"],
        "service_areas": ["北京"],
    },
]

SERVICE_SLOT_TIMES = [
    time(9, 0),
    time(10, 30),
    time(14, 0),
    time(15, 30),
    time(17, 0),
]
ACTIVE_SERVICE_STATUSES = {"scheduled", "in_progress"}
FINAL_SERVICE_STATUSES = {"completed", "cancelled", "deleted"}


def get_customer_info(customer_id: str) -> dict:
    """
    查询客户信息
    :param customer_id: 客户ID
    :return: 客户信息字典或错误信息字典
    """
    if customer_id != "CUST001":
        return {"error": "Customer not found"}
    return {
        "customer_id": "CUST001",
        "name": "张明",
        "email": "zhang.ming@example.com",
        "address": "北京市朝阳区建国门外大街1号",
        "registration_date": "2022-03-15",
        "date_of_birth": "1985-10-20",
        "notes": "优质客户，经常购买高端产品",
        "total_purchases": 3,
        "lifetime_value": 28500.00,
        "support_cases_count": 2,
        "communication_preferences": ["email", "sms"],
    }


def get_customer_purchases(customer_id: str) -> list:
    """
    查询客户购买记录
    :param customer_id: 客户ID
    :return: 客户购买记录列表或空列表
    """
    if customer_id != "CUST001":
        return []
    return [
        {
            "product_id": "PROD001",
            "serial_number": "SN20240001",
            "product_name": "智能电视 65寸",
            "customer_id": "CUST001",
            "purchase_date": "2023-12-10",
            "warranty_end_date": "2025-12-10",
            "warranty_type": "standard",
            "status": "active",
        },
        {
            "product_id": "PROD002",
            "serial_number": "SN20240002",
            "product_name": "智能音箱 Pro",
            "customer_id": "CUST001",
            "purchase_date": "2023-08-15",
            "warranty_end_date": "2024-08-15",
            "warranty_type": "extended",
            "status": "active",
        },
    ]


def query_warranty(serial_number: str) -> dict:
    """
    查询保修信息
    :param serial_number: 商品序列号
    :return: 保修信息字典或错误信息字典
    """
    if serial_number not in ["SN20240001", "SN20240002"]:
        return {"error": "Warranty not found"}
    if serial_number == "SN20240001":
        return {
            "serial_number": "SN20240001",
            "product_name": "智能电视 65寸",
            "customer_id": "CUST001",
            "purchase_date": "2023-12-10",
            "warranty_end_date": "2025-12-10",
            "warranty_type": "standard",
            "status_text": "保修有效",
        }
    return {
        "serial_number": "SN20240002",
        "product_name": "智能音箱 Pro",
        "customer_id": "CUST001",
        "purchase_date": "2023-08-15",
        "warranty_end_date": "2024-08-15",
        "warranty_type": "extended",
        "status_text": "保修已经过期",
    }


def _find_purchase(customer_id: str, serial_number: str) -> Optional[dict]:
    for purchase in get_customer_purchases(customer_id):
        if purchase["serial_number"] == serial_number:
            return purchase
    return None


def _parse_service_datetime(value: str) -> Optional[datetime]:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _service_overlaps(
    existing_start: datetime,
    existing_duration: int,
    candidate_start: datetime,
    candidate_duration: int,
) -> bool:
    existing_end = existing_start + timedelta(minutes=existing_duration)
    candidate_end = candidate_start + timedelta(minutes=candidate_duration)
    return existing_start < candidate_end and candidate_start < existing_end


def _has_technician_conflict(
    technician: str,
    candidate_start: datetime,
    duration_minutes: int,
    exclude_record_id: Optional[str] = None,
) -> bool:
    for record in mock_service_records:
        if exclude_record_id and record["record_id"] == exclude_record_id:
            continue
        if record["technician"] != technician:
            continue
        if record["status"] not in ACTIVE_SERVICE_STATUSES:
            continue
        existing_start = _parse_service_datetime(record["service_date"])
        if existing_start is None:
            continue
        if _service_overlaps(
            existing_start,
            record["estimated_duration"],
            candidate_start,
            duration_minutes,
        ):
            return True
    return False


def _find_service_record(customer_id: str, service_id: str) -> Optional[dict]:
    for record in get_service_records(customer_id):
        if record["record_id"] == service_id:
            return record
    return None


def _find_technician(technician_name: str) -> Optional[dict]:
    for technician in mock_technician_roster:
        if technician["technician"] == technician_name:
            return technician
    return None


def _eligible_technicians(service_type: str) -> list[dict]:
    technicians = [
        technician
        for technician in mock_technician_roster
        if service_type in technician["skills"]
    ]
    if technicians:
        return technicians
    return [
        technician
        for technician in mock_technician_roster
        if "上门检测" in technician["skills"]
    ]


def _technician_can_handle(technician: dict, service_type: str) -> bool:
    if service_type in technician["skills"]:
        return True
    explicit_skill_match = any(
        service_type in roster["skills"] for roster in mock_technician_roster
    )
    return not explicit_skill_match and "上门检测" in technician["skills"]


def verify_customer_identity(
    customer_id: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    date_of_birth: Optional[str] = None,
) -> dict:
    """核验客户身份，仅返回匹配结果，不泄露未提供的客户敏感字段。"""
    customer = get_customer_info(customer_id)
    if "error" in customer:
        return customer

    checks = {
        "name": (name or "").strip() == customer["name"],
        "email": (email or "").strip().lower() == customer["email"].lower(),
        "date_of_birth": (date_of_birth or "").strip() == customer["date_of_birth"],
    }
    provided_fields = [
        field
        for field, value in {
            "name": name,
            "email": email,
            "date_of_birth": date_of_birth,
        }.items()
        if value
    ]
    matched_fields = [field for field in provided_fields if checks[field]]

    if len(provided_fields) < 2:
        return {
            "customer_id": customer_id,
            "verified": False,
            "matched_fields": matched_fields,
            "message": "Need at least two identity fields for verification",
        }

    return {
        "customer_id": customer_id,
        "verified": len(matched_fields) >= 2,
        "matched_fields": matched_fields,
        "failed_fields": [
            field for field in provided_fields if field not in matched_fields
        ],
    }


def get_service_case_brief(customer_id: str) -> dict:
    """汇总客户售后上下文，帮助客服在对话开始时快速判断下一步动作。"""
    customer = get_customer_info(customer_id)
    if "error" in customer:
        return customer

    purchases = get_customer_purchases(customer_id)
    warranty_by_product = {
        purchase["serial_number"]: query_warranty(purchase["serial_number"])
        for purchase in purchases
    }
    active_records = [
        record
        for record in get_service_records(customer_id)
        if record["status"] in ACTIVE_SERVICE_STATUSES
    ]
    expired_warranty_products = [
        purchase["serial_number"]
        for purchase in purchases
        if warranty_by_product[purchase["serial_number"]]["status_text"] == "保修已经过期"
    ]

    next_actions = []
    if active_records:
        next_actions.append("先确认已有维修单进度，避免重复创建工单")
    if expired_warranty_products:
        next_actions.append("涉及过保商品时，需先确认客户是否接受自费维修")
    if not active_records:
        next_actions.append("如需上门维修，可先查询可预约时段")

    return {
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "owned_product_count": len(purchases),
        "active_service_record_count": len(active_records),
        "active_service_records": active_records,
        "warranty_status": warranty_by_product,
        "next_actions": next_actions,
    }


def get_available_service_slots(
    customer_id: str,
    serial_number: str,
    service_type: str,
    preferred_date: Optional[str] = None,
    estimated_duration: int = 90,
    limit: int = 5,
) -> dict:
    """查询可预约维修时段，综合客户商品归属、保修状态、师傅技能和已有排班。"""
    if get_customer_info(customer_id).get("error"):
        return {"error": "Customer not found"}
    purchase = _find_purchase(customer_id, serial_number)
    if purchase is None:
        return {"error": "Product not found for customer"}
    if estimated_duration <= 0:
        return {"error": "estimated_duration must be greater than 0"}

    warranty = query_warranty(serial_number)
    try:
        start_date = (
            datetime.strptime(preferred_date, "%Y-%m-%d").date()
            if preferred_date
            else datetime.now().date() + timedelta(days=1)
        )
    except ValueError:
        return {"error": "preferred_date must use YYYY-MM-DD format"}

    slots = []
    technicians = _eligible_technicians(service_type)
    for day_offset in range(7):
        service_date = start_date + timedelta(days=day_offset)
        for slot_time in SERVICE_SLOT_TIMES:
            candidate_start = datetime.combine(service_date, slot_time)
            for technician in technicians:
                if _has_technician_conflict(
                    technician["technician"],
                    candidate_start,
                    estimated_duration,
                ):
                    continue
                slots.append(
                    {
                        "service_date": candidate_start.strftime("%Y-%m-%d %H:%M:%S"),
                        "technician": technician["technician"],
                        "service_type": service_type,
                        "estimated_duration": estimated_duration,
                        "warranty_status": warranty["status_text"],
                    }
                )
                if len(slots) >= limit:
                    return {
                        "customer_id": customer_id,
                        "serial_number": serial_number,
                        "product_name": purchase["product_name"],
                        "slots": slots,
                    }

    return {
        "customer_id": customer_id,
        "serial_number": serial_number,
        "product_name": purchase["product_name"],
        "slots": slots,
    }


def schedule_service_record(
    customer_id: str,
    serial_number: str,
    service_type: str,
    description: str,
    service_date: str,
    technician: str,
    estimated_duration: int = 90,
    customer_confirmed: bool = False,
) -> dict:
    """在客户确认后创建维修预约，并校验商品归属、师傅技能和排班冲突。"""
    customer = get_customer_info(customer_id)
    if "error" in customer:
        return customer
    purchase = _find_purchase(customer_id, serial_number)
    if purchase is None:
        return {"error": "Product not found for customer"}
    if estimated_duration <= 0:
        return {"error": "estimated_duration must be greater than 0"}

    candidate_start = _parse_service_datetime(service_date)
    if candidate_start is None:
        return {"error": "service_date must use YYYY-MM-DD HH:MM:SS format"}

    technician_profile = _find_technician(technician)
    if technician_profile is None:
        return {"error": "Technician not found"}
    if not _technician_can_handle(technician_profile, service_type):
        return {"error": "Technician cannot handle requested service_type"}

    if _has_technician_conflict(technician, candidate_start, estimated_duration):
        alternatives = get_available_service_slots(
            customer_id,
            serial_number,
            service_type,
            preferred_date=candidate_start.strftime("%Y-%m-%d"),
            estimated_duration=estimated_duration,
            limit=10,
        )
        later_slots = [
            slot
            for slot in alternatives.get("slots", [])
            if _parse_service_datetime(slot["service_date"]) > candidate_start
        ][:3]
        if not later_slots:
            later_slots = alternatives.get("slots", [])[:3]
        return {
            "error": "Technician schedule conflict",
            "available_slots": later_slots,
        }

    warranty = query_warranty(serial_number)
    pending_record = {
        "serial_number": serial_number,
        "product_name": purchase["product_name"],
        "service_type": service_type,
        "description": description,
        "service_date": service_date,
        "technician": technician,
        "estimated_duration": estimated_duration,
        "warranty_status": warranty["status_text"],
    }
    if not customer_confirmed:
        return {
            "status": "confirmation_required",
            "message": "Customer confirmation required before creating service record",
            "pending_record": pending_record,
        }

    created = create_service_record(
        customer_id,
        ServiceRecordCreate(
            serial_number=serial_number,
            service_type=service_type,
            description=description,
            technician=technician,
            service_date=service_date,
            estimated_duration=estimated_duration,
        ),
    )
    created["warranty_status"] = warranty["status_text"]
    if warranty["status_text"] == "保修已经过期":
        created["billing_notice"] = "商品已过保，维修前需再次确认自费维修意愿"
    return created


def reschedule_service_record(
    customer_id: str,
    service_id: str,
    service_date: str,
    technician: Optional[str] = None,
    estimated_duration: Optional[int] = None,
) -> dict:
    """改期已有维修预约，跳过已完结工单，并避免与其他排班冲突。"""
    if get_customer_info(customer_id).get("error"):
        return {"error": "Customer not found"}
    record = _find_service_record(customer_id, service_id)
    if record is None:
        return {"error": "Service record not found"}
    if record["status"] in FINAL_SERVICE_STATUSES:
        return {"error": "Finalized service record cannot be rescheduled"}

    candidate_start = _parse_service_datetime(service_date)
    if candidate_start is None:
        return {"error": "service_date must use YYYY-MM-DD HH:MM:SS format"}

    next_technician = technician or record["technician"]
    next_duration = estimated_duration or record["estimated_duration"]
    if next_duration <= 0:
        return {"error": "estimated_duration must be greater than 0"}

    technician_profile = _find_technician(next_technician)
    if technician_profile is None:
        return {"error": "Technician not found"}
    if not _technician_can_handle(technician_profile, record["service_type"]):
        return {"error": "Technician cannot handle requested service_type"}
    if _has_technician_conflict(
        next_technician,
        candidate_start,
        next_duration,
        exclude_record_id=service_id,
    ):
        return {"error": "Technician schedule conflict"}

    record["service_date"] = service_date
    record["technician"] = next_technician
    record["estimated_duration"] = next_duration
    record["status"] = "scheduled"
    record["notes"] = (
        (record["notes"] + "；" if record["notes"] else "")
        + f"已改约至 {service_date}"
    )
    return record


def get_service_records(customer_id: str) -> list:
    """
    查询客户维修记录
    :param customer_id: 客户ID
    :return: 客户维修记录列表或空列表
    """
    if customer_id != "CUST001":
        return []
    return mock_service_records


def create_service_record(
    customer_id: str, service_record: ServiceRecordCreate
) -> dict:
    """创建维修记录
    :param customer_id: 客户ID
    :param service_record: 创建的维修记录信息
    :return: 创建后的维修记录字典或错误信息字典
    """
    if customer_id != "CUST001":
        return {"error": "Customer not found"}

    r = {
        "record_id": f"SRV00{len(mock_service_records) + 1}",
        "serial_number": service_record.serial_number,
        "customer_id": customer_id,
        "service_date": service_record.service_date,
        "service_type": service_record.service_type,
        "description": service_record.description,
        "technician": service_record.technician,
        "status": "scheduled",
        "estimated_duration": service_record.estimated_duration,
        "actual_duration": None,
        "notes": None,
    }
    mock_service_records.append(r)
    return r


def update_service_record(
    customer_id: str, service_id: str, service_record: ServiceRecordUpdate
) -> dict:
    """更新维修记录
    :param customer_id: 客户ID
    :param service_id: 维修记录ID
    :param service_record: 更新的维修记录信息
    :return: 更新后的维修记录字典或错误信息字典
    """
    if customer_id != "CUST001":
        return {"error": "Customer not found"}
    for r in mock_service_records:
        if r["record_id"] == service_id:
            r["service_date"] = service_record.service_date or r["service_date"]
            r["status"] = service_record.status or r["status"]
            r["actual_duration"] = (
                service_record.actual_duration or r["actual_duration"]
            )
            r["notes"] = service_record.notes or r["notes"]
            return r
    return {"error": "Service record not found"}


def delete_service_record(customer_id: str, service_id: str) -> dict:
    """删除维修记录
    :param customer_id: 客户ID
    :param service_id: 维修记录ID
    :return: 删除结果字典或错误信息字典
    """
    if customer_id != "CUST001":
        return {"error": "Customer not found"}
    for r in mock_service_records:
        if r["record_id"] == service_id:
            mock_service_records.remove(r)
            return {"service_id": service_id, "status": "deleted"}
    return {"error": "Service record not found"}
