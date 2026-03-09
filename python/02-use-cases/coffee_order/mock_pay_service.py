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

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from veadk.utils.logger import get_logger

from alipay_payment import html_template
from qr_utils import generate_qr_tos_url, upload_frontend_code_to_tos

logger = get_logger(__name__)
ORDERS: Dict[str, Dict[str, Any]] = {}


def create_order_number() -> str:
    """
    Generate a unique order number.
    :return: 订单号
    :rtype: str
    """
    return str(uuid4().hex)


def create_order(
    trade_number: str,
    amount: float,
    currency: str = "CNY",
    description: Optional[str] = None,
):
    """
    Create a payment order.
    :param trade_number: 订单号
    :type trade_number: str
    :param amount: 金额
    :type amount: float
    :param currency: 币种，CNY、USD等
    :type currency: str
    :param description: 订单描述
    :type description: Optional[str]
    """
    created_at = datetime.now(timezone.utc).isoformat()

    # mock payment url (in real scenario, it should be returned by payment gateway)
    payment_url = f"https://pay.example.com/pay?order_id={trade_number}&amount={amount}&currency={currency}"

    qr_data_url = generate_qr_tos_url(payment_url)

    logger.info(f"Generated QR code URL: {qr_data_url}")

    order = {
        "id": trade_number,
        "amount": amount,
        "currency": currency,
        "description": description,
        "status": "pending",
        "qr_data_url": qr_data_url,
        "createdAt": created_at,
    }
    ORDERS[trade_number] = order

    html_content = alipay_payment_page(order)
    payment_url = upload_frontend_code_to_tos(html_content, "html")
    return {
        "payment_url": payment_url,
    }


# generate alipay payment page html content
def alipay_payment_page(order):
    html_content = html_template

    html_content = html_content.replace("{{ amount }}", str(order["amount"]))
    html_content = html_content.replace(
        "{{ description }}", order.get("description", "订单支付") or "订单支付"
    )
    html_content = html_content.replace("{{ order_id }}", order["id"])
    html_content = html_content.replace(
        "{{ qr_data_url }}", order.get("qr_data_url", "")
    )

    return html_content
