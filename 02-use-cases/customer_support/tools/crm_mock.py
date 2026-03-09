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
