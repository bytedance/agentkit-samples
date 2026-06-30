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

from tools.crm_mock import get_customer_info, get_customer_purchases
from tools.product_advisor import PRODUCT_CATALOG, build_purchase_bundle, recommend_products


DELIVERY_AREAS = {
    "北京市朝阳区": {
        "delivery_fee": 0,
        "installation_fee": 0,
        "earliest_days": 1,
        "supports_evening": True,
    },
    "北京市海淀区": {
        "delivery_fee": 0,
        "installation_fee": 0,
        "earliest_days": 2,
        "supports_evening": True,
    },
    "北京市通州区": {
        "delivery_fee": 49,
        "installation_fee": 0,
        "earliest_days": 3,
        "supports_evening": False,
    },
}

PAYMENT_PLANS = [
    {"months": 3, "fee_rate": 0.0, "min_amount": 1000},
    {"months": 6, "fee_rate": 0.015, "min_amount": 3000},
    {"months": 12, "fee_rate": 0.036, "min_amount": 6000},
    {"months": 24, "fee_rate": 0.082, "min_amount": 10000},
]

COUPONS = [
    {
        "coupon_id": "TV500",
        "name": "电视满 10000 减 500",
        "category": "tv",
        "threshold": 10000,
        "discount": 500,
    },
    {
        "coupon_id": "BUNDLE300",
        "name": "电视套餐立减 300",
        "category": "bundle",
        "threshold": 12000,
        "discount": 300,
    },
    {
        "coupon_id": "CARE100",
        "name": "延保服务立减 100",
        "category": "warranty",
        "threshold": 500,
        "discount": 100,
    },
]


def _product_by_id(product_id: str) -> Optional[dict]:
    for product in PRODUCT_CATALOG:
        if product["product_id"] == product_id:
            return product
    return None


def _public_item(product: dict, quantity: int = 1) -> dict:
    return {
        "product_id": product["product_id"],
        "name": product["name"],
        "category": product["category"],
        "unit_price": product["price"],
        "quantity": quantity,
        "subtotal": product["price"] * quantity,
    }


def _resolve_area(address: str) -> Optional[str]:
    for area in DELIVERY_AREAS:
        if area in address:
            return area
    return None


def _quote_items(items: list[dict]) -> tuple[list[dict], list[str]]:
    rendered = []
    missing = []
    for item in items:
        product = _product_by_id(item["product_id"])
        quantity = item.get("quantity", 1)
        if product is None:
            missing.append(item["product_id"])
            continue
        if quantity <= 0:
            missing.append(item["product_id"])
            continue
        rendered.append(_public_item(product, quantity=quantity))
    return rendered, missing


def _best_coupon(items: list[dict], subtotal: int) -> Optional[dict]:
    categories = {item["category"] for item in items}
    eligible = []
    for coupon in COUPONS:
        if subtotal < coupon["threshold"]:
            continue
        if coupon["category"] == "bundle" and len(categories) < 2:
            continue
        if coupon["category"] != "bundle" and coupon["category"] not in categories:
            continue
        eligible.append(coupon)
    if not eligible:
        return None
    return max(eligible, key=lambda coupon: coupon["discount"])


def _delivery_option(address: str, requested_date: Optional[str] = None) -> dict:
    area = _resolve_area(address)
    if area is None:
        return {
            "available": False,
            "reason": "Address outside supported delivery areas",
        }
    policy = DELIVERY_AREAS[area]
    earliest = datetime.now().date() + timedelta(days=policy["earliest_days"])
    requested_ok = True
    if requested_date:
        try:
            requested = datetime.strptime(requested_date, "%Y-%m-%d").date()
            requested_ok = requested >= earliest
        except ValueError:
            return {"available": False, "reason": "requested_date must use YYYY-MM-DD format"}
    return {
        "available": requested_ok,
        "area": area,
        "delivery_fee": policy["delivery_fee"],
        "installation_fee": policy["installation_fee"],
        "earliest_delivery_date": earliest.strftime("%Y-%m-%d"),
        "supports_evening": policy["supports_evening"],
        "reason": None if requested_ok else "Requested date is earlier than earliest delivery date",
    }


def build_quote(
    customer_id: str,
    items: list[dict],
    delivery_address: Optional[str] = None,
    requested_delivery_date: Optional[str] = None,
) -> dict:
    """生成购买报价，包含优惠、配送安装费用和客户确认项。"""
    customer = get_customer_info(customer_id)
    if "error" in customer:
        return customer
    quoted_items, invalid_items = _quote_items(items)
    if invalid_items:
        return {"error": "Invalid quote items", "invalid_product_ids": invalid_items}
    if not quoted_items:
        return {"error": "quote items are required"}

    address = delivery_address or customer["address"]
    delivery = _delivery_option(address, requested_delivery_date)
    subtotal = sum(item["subtotal"] for item in quoted_items)
    coupon = _best_coupon(quoted_items, subtotal)
    discount = coupon["discount"] if coupon else 0
    delivery_fee = delivery.get("delivery_fee", 0) if delivery["available"] else 0
    installation_fee = delivery.get("installation_fee", 0) if delivery["available"] else 0
    payable = subtotal - discount + delivery_fee + installation_fee

    return {
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "items": quoted_items,
        "subtotal": subtotal,
        "coupon": coupon,
        "discount": discount,
        "delivery": delivery,
        "delivery_fee": delivery_fee,
        "installation_fee": installation_fee,
        "payable_amount": payable,
        "confirmation_required": [
            "确认商品型号、尺寸和数量",
            "确认配送地址和可收货时间",
            "确认优惠和最终应付金额",
        ],
    }


def suggest_payment_plans(payable_amount: int) -> dict:
    """根据应付金额生成可选分期方案。"""
    if payable_amount <= 0:
        return {"error": "payable_amount must be greater than 0"}

    plans = []
    for plan in PAYMENT_PLANS:
        if payable_amount < plan["min_amount"]:
            continue
        total_fee = round(payable_amount * plan["fee_rate"], 2)
        total_payable = round(payable_amount + total_fee, 2)
        monthly_payment = round(total_payable / plan["months"], 2)
        plans.append(
            {
                "months": plan["months"],
                "fee_rate": plan["fee_rate"],
                "total_fee": total_fee,
                "total_payable": total_payable,
                "monthly_payment": monthly_payment,
            }
        )
    return {
        "payable_amount": payable_amount,
        "plans": plans,
        "recommended_plan": plans[0] if plans else None,
    }


def validate_purchase_readiness(
    customer_id: str,
    items: list[dict],
    delivery_address: Optional[str] = None,
    customer_confirmed: bool = False,
) -> dict:
    """校验下单前是否具备必要信息，避免 agent 过早推进成交。"""
    quote = build_quote(customer_id, items, delivery_address=delivery_address)
    if "error" in quote:
        return quote

    blockers = []
    warnings = []
    if not quote["delivery"]["available"]:
        blockers.append("配送地址暂不支持或日期不可用")
    if not customer_confirmed:
        blockers.append("客户尚未确认商品、地址和金额")
    categories = {item["category"] for item in quote["items"]}
    if "tv" in categories and not any(item["category"] == "warranty" for item in quote["items"]):
        warnings.append("大件电视未包含延保，可询问客户是否需要")
    if quote["payable_amount"] >= 10000:
        warnings.append("高金额订单建议提供分期选项")

    return {
        "customer_id": customer_id,
        "ready": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "quote": quote,
    }


def create_order_handoff(
    customer_id: str,
    items: list[dict],
    delivery_address: Optional[str] = None,
    customer_confirmed: bool = False,
    payment_months: Optional[int] = None,
) -> dict:
    """生成下单交接包，供人工坐席或订单系统继续处理。"""
    readiness = validate_purchase_readiness(
        customer_id,
        items,
        delivery_address=delivery_address,
        customer_confirmed=customer_confirmed,
    )
    if "error" in readiness:
        return readiness
    if not readiness["ready"]:
        return {
            "status": "not_ready",
            "blockers": readiness["blockers"],
            "warnings": readiness["warnings"],
            "quote": readiness["quote"],
        }

    quote = readiness["quote"]
    payment_options = suggest_payment_plans(quote["payable_amount"])
    selected_payment = None
    if payment_months:
        for plan in payment_options["plans"]:
            if plan["months"] == payment_months:
                selected_payment = plan
                break
        if selected_payment is None:
            return {"error": "Selected payment plan is not available"}

    handoff_id = f"ORDER-{customer_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    return {
        "status": "ready_for_order",
        "handoff_id": handoff_id,
        "customer_id": customer_id,
        "quote": quote,
        "selected_payment": selected_payment,
        "payment_options": payment_options["plans"],
        "warnings": readiness["warnings"],
        "handoff_notes": [
            f"客户已确认 {len(quote['items'])} 个商品项",
            f"应付金额 {quote['payable_amount']} 元",
            f"配送区域：{quote['delivery'].get('area')}",
        ],
    }


def recommend_checkout_path(
    customer_id: str,
    requirements: str,
    budget: Optional[int] = None,
    delivery_address: Optional[str] = None,
) -> dict:
    """从客户需求直接生成推荐商品、套餐、报价和成交下一步。"""
    recommendations = recommend_products(
        requirements,
        budget=budget,
        customer_id=customer_id,
        limit=1,
    )
    if "error" in recommendations:
        return recommendations
    if not recommendations["recommendations"]:
        return {"error": "No product recommendation available"}

    main_product = recommendations["recommendations"][0]["product"]
    include_warranty = main_product["price"] >= 8000
    include_speaker = "smart_home" in recommendations["need_tags"]
    bundle = build_purchase_bundle(
        main_product["product_id"],
        include_warranty=include_warranty,
        include_smart_speaker=include_speaker,
        budget=budget,
    )
    quote_items = [
        {"product_id": item["product_id"], "quantity": 1}
        for item in bundle["items"]
    ]
    quote = build_quote(
        customer_id,
        quote_items,
        delivery_address=delivery_address,
    )
    readiness = validate_purchase_readiness(
        customer_id,
        quote_items,
        delivery_address=delivery_address,
        customer_confirmed=False,
    )

    return {
        "customer_id": customer_id,
        "requirements": requirements,
        "recommendation": recommendations["recommendations"][0],
        "bundle": bundle,
        "quote": quote,
        "readiness": readiness,
        "next_step": "向客户确认商品、套餐、配送地址和最终金额",
    }


def summarize_post_purchase_opportunities(customer_id: str) -> dict:
    """基于已购商品生成复购、延保和配件机会。"""
    customer = get_customer_info(customer_id)
    if "error" in customer:
        return customer
    purchases = get_customer_purchases(customer_id)
    opportunities = []
    for purchase in purchases:
        if "电视" in purchase["product_name"]:
            opportunities.append(
                {
                    "serial_number": purchase["serial_number"],
                    "type": "warranty_or_upgrade",
                    "message": "可推荐延保服务、智能音箱联动或大屏升级方案",
                    "priority": "high" if customer["lifetime_value"] >= 20000 else "normal",
                }
            )
        if "音箱" in purchase["product_name"]:
            opportunities.append(
                {
                    "serial_number": purchase["serial_number"],
                    "type": "smart_home_bundle",
                    "message": "可推荐电视、灯光或其他智能家居联动设备",
                    "priority": "normal",
                }
            )
    return {
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "opportunity_count": len(opportunities),
        "opportunities": opportunities,
    }
