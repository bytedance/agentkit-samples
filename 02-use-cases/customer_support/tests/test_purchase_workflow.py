from __future__ import annotations

import sys
from pathlib import Path

import pytest


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from tools import purchase_workflow as workflow


def test_build_quote_applies_best_coupon_and_delivery_policy():
    quote = workflow.build_quote(
        "CUST001",
        [
            {"product_id": "TV-TCL-Q10K-65", "quantity": 1},
            {"product_id": "WARRANTY-PLUS-TV", "quantity": 1},
        ],
        requested_delivery_date="2099-01-01",
    )

    assert quote["customer_name"] == "张明"
    assert quote["subtotal"] == 15698
    assert quote["coupon"]["coupon_id"] == "TV500"
    assert quote["discount"] == 500
    assert quote["delivery"]["area"] == "北京市朝阳区"
    assert quote["delivery_fee"] == 0
    assert quote["payable_amount"] == 15198
    assert "确认优惠和最终应付金额" in quote["confirmation_required"]


def test_build_quote_rejects_invalid_items_and_unsupported_delivery_date():
    invalid = workflow.build_quote(
        "CUST001",
        [{"product_id": "missing", "quantity": 1}],
    )
    bad_date = workflow.build_quote(
        "CUST001",
        [{"product_id": "TV-TCL-Q10K-65", "quantity": 1}],
        requested_delivery_date="bad-date",
    )

    assert invalid == {
        "error": "Invalid quote items",
        "invalid_product_ids": ["missing"],
    }
    assert bad_date["delivery"] == {
        "available": False,
        "reason": "requested_date must use YYYY-MM-DD format",
    }


@pytest.mark.parametrize(
    ("amount", "months"),
    [
        (2000, [3]),
        (8000, [3, 6, 12]),
        (15000, [3, 6, 12, 24]),
    ],
)
def test_suggest_payment_plans_filters_by_amount(amount, months):
    result = workflow.suggest_payment_plans(amount)

    assert [plan["months"] for plan in result["plans"]] == months
    assert result["recommended_plan"]["months"] == 3


def test_suggest_payment_plans_validates_amount():
    assert workflow.suggest_payment_plans(0) == {
        "error": "payable_amount must be greater than 0"
    }


def test_validate_purchase_readiness_blocks_without_confirmation():
    result = workflow.validate_purchase_readiness(
        "CUST001",
        [{"product_id": "TV-TCL-Q10K-65", "quantity": 1}],
        customer_confirmed=False,
    )

    assert result["ready"] is False
    assert result["blockers"] == ["客户尚未确认商品、地址和金额"]
    assert "大件电视未包含延保，可询问客户是否需要" in result["warnings"]
    assert "高金额订单建议提供分期选项" in result["warnings"]


def test_validate_purchase_readiness_passes_when_confirmed_and_deliverable():
    result = workflow.validate_purchase_readiness(
        "CUST001",
        [
            {"product_id": "TV-TCL-Q10K-65", "quantity": 1},
            {"product_id": "WARRANTY-PLUS-TV", "quantity": 1},
        ],
        customer_confirmed=True,
    )

    assert result["ready"] is True
    assert result["blockers"] == []
    assert result["quote"]["payable_amount"] == 15198


def test_create_order_handoff_returns_not_ready_until_customer_confirms():
    result = workflow.create_order_handoff(
        "CUST001",
        [{"product_id": "TV-TCL-Q10K-65", "quantity": 1}],
        customer_confirmed=False,
    )

    assert result["status"] == "not_ready"
    assert result["blockers"] == ["客户尚未确认商品、地址和金额"]
    assert result["quote"]["customer_id"] == "CUST001"


def test_create_order_handoff_selects_payment_plan_when_ready():
    result = workflow.create_order_handoff(
        "CUST001",
        [
            {"product_id": "TV-TCL-Q10K-65", "quantity": 1},
            {"product_id": "WARRANTY-PLUS-TV", "quantity": 1},
        ],
        customer_confirmed=True,
        payment_months=12,
    )

    assert result["status"] == "ready_for_order"
    assert result["handoff_id"].startswith("ORDER-CUST001-")
    assert result["selected_payment"]["months"] == 12
    assert result["quote"]["payable_amount"] == 15198
    assert "应付金额 15198 元" in result["handoff_notes"]


def test_create_order_handoff_rejects_unavailable_payment_plan():
    result = workflow.create_order_handoff(
        "CUST001",
        [{"product_id": "TV-XIAOMI-A2-55", "quantity": 1}],
        customer_confirmed=True,
        payment_months=24,
    )

    assert result == {"error": "Selected payment plan is not available"}


def test_recommend_checkout_path_builds_recommendation_bundle_and_quote():
    result = workflow.recommend_checkout_path(
        "CUST001",
        "客厅游戏电视，预算 15000，采光强",
        budget=15000,
    )

    assert result["recommendation"]["product"]["category"] == "tv"
    assert result["bundle"]["main_product"]["product_id"] in {
        "TV-HISENSE-U8Q-65",
        "TV-TCL-Q10K-65",
    }
    assert result["quote"]["customer_id"] == "CUST001"
    assert result["readiness"]["ready"] is False
    assert result["next_step"] == "向客户确认商品、套餐、配送地址和最终金额"


def test_summarize_post_purchase_opportunities_from_purchase_history():
    result = workflow.summarize_post_purchase_opportunities("CUST001")

    assert result["customer_name"] == "张明"
    assert result["opportunity_count"] == 2
    assert result["opportunities"][0]["type"] == "warranty_or_upgrade"
    assert result["opportunities"][0]["priority"] == "high"
    assert result["opportunities"][1]["type"] == "smart_home_bundle"


def test_purchase_workflow_rejects_unknown_customer():
    assert workflow.build_quote(
        "CUST404",
        [{"product_id": "TV-TCL-Q10K-65", "quantity": 1}],
    ) == {"error": "Customer not found"}
    assert workflow.summarize_post_purchase_opportunities("CUST404") == {
        "error": "Customer not found"
    }
