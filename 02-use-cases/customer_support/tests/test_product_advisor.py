from __future__ import annotations

import sys
from pathlib import Path

import pytest


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from tools import product_advisor as advisor


def test_list_available_products_filters_by_category_and_price():
    result = advisor.list_available_products(category="tv", max_price=8000)

    assert result["count"] == 2
    assert [product["product_id"] for product in result["products"]] == [
        "TV-XIAOMI-MASTER-75",
        "TV-XIAOMI-A2-55",
    ]
    assert all(product["price"] <= 8000 for product in result["products"])


def test_recommend_products_prioritizes_gaming_with_budget_and_room_fit():
    result = advisor.recommend_products(
        "客厅玩 PS5，希望高刷低延迟，采光比较强",
        budget=15000,
        customer_id="CUST001",
        viewing_distance_m=3.0,
        limit=3,
    )

    assert result["need_tags"] == ["gaming", "bright_room"]
    assert result["recommendations"][0]["product"]["product_id"] == "TV-HISENSE-U8Q-65"
    assert result["recommendations"][0]["matched_need_tags"] == [
        "bright_room",
        "gaming",
    ]
    assert any(
        item["product"]["product_id"] == "TV-TCL-Q10K-65"
        and "保修期较长，售后风险更低" in item["reasons"]
        for item in result["recommendations"]
    )


def test_recommend_products_handles_budget_pressure_with_entry_model():
    result = advisor.recommend_products(
        "卧室看剧，预算有限，想要便宜一点",
        budget=4000,
        viewing_distance_m=2.4,
        limit=2,
    )

    assert result["need_tags"] == ["budget", "bedroom"]
    assert result["recommendations"][0]["product"]["product_id"] == "TV-XIAOMI-A2-55"
    assert result["recommendations"][0]["score"] > result["recommendations"][1]["score"]


def test_recommend_products_validates_inputs():
    assert advisor.recommend_products(" ") == {"error": "requirements is required"}
    assert advisor.recommend_products("游戏电视", budget=0) == {
        "error": "budget must be greater than 0"
    }
    assert advisor.recommend_products("游戏电视", customer_id="CUST404") == {
        "error": "Customer not found"
    }


def test_compare_products_returns_key_differences_and_summary():
    result = advisor.compare_products(["TV-TCL-Q10K-65", "TV-XIAOMI-MASTER-75"])

    assert [product["product_id"] for product in result["products"]] == [
        "TV-TCL-Q10K-65",
        "TV-XIAOMI-MASTER-75",
    ]
    assert result["summary"] == {
        "lowest_price": "TV-XIAOMI-MASTER-75",
        "longest_warranty": "TV-TCL-Q10K-65",
        "highest_refresh_rate": "TV-TCL-Q10K-65",
    }
    assert "游戏玩家" in result["products"][0]["best_for"]


def test_compare_products_validates_product_ids():
    assert advisor.compare_products(["TV-TCL-Q10K-65"]) == {
        "error": "at least two product_ids are required"
    }
    assert advisor.compare_products(["TV-TCL-Q10K-65", "missing"]) == {
        "error": "Product not found",
        "missing_product_ids": ["missing"],
    }


@pytest.mark.parametrize(
    ("distance", "fit"),
    [
        (2.0, "too_close"),
        (3.0, "good"),
        (4.2, "too_far"),
    ],
)
def test_estimate_room_fit_checks_distance(distance, fit):
    result = advisor.estimate_room_fit(
        "TV-TCL-Q10K-65",
        viewing_distance_m=distance,
        room_brightness="bright",
    )

    assert result["fit"] == fit
    assert result["recommended_distance_m"] == [2.5, 3.5]
    assert result["brightness_warning"] is None


def test_estimate_room_fit_warns_when_brightness_is_not_enough():
    result = advisor.estimate_room_fit(
        "TV-XIAOMI-A2-55",
        viewing_distance_m=2.4,
        room_brightness="bright",
    )

    assert result["fit"] == "good"
    assert result["brightness_warning"] == "房间采光强时，该型号亮度可能不够从容"


def test_build_purchase_bundle_calculates_savings_and_budget_status():
    result = advisor.build_purchase_bundle(
        "TV-TCL-Q10K-65",
        include_warranty=True,
        include_smart_speaker=True,
        budget=16000,
    )

    assert [item["product_id"] for item in result["items"]] == [
        "TV-TCL-Q10K-65",
        "WARRANTY-PLUS-TV",
        "SPK-SMART-PRO",
    ]
    assert result["total_price"] == 16597
    assert result["bundle_savings"] == 300
    assert result["payable_price"] == 16297
    assert result["budget_status"] == "over_budget"
    assert "延保降低大件电视后续维修不确定性" in result["selling_points"]


def test_build_purchase_bundle_validates_main_product():
    assert advisor.build_purchase_bundle("missing") == {"error": "Product not found"}
    assert advisor.build_purchase_bundle("SPK-SMART-PRO") == {
        "error": "bundle main product must be a tv"
    }


def test_handle_purchase_objection_for_price_returns_alternatives_and_guardrails():
    result = advisor.handle_purchase_objection(
        "这个太贵了，有没有便宜点但适合游戏的",
        product_id="TV-TCL-Q10K-65",
        budget=12000,
    )

    assert result["objection_type"] == "expensive"
    assert result["product"]["product_id"] == "TV-TCL-Q10K-65"
    assert result["alternatives"]
    assert result["alternatives"][0]["product"]["price"] <= 12000
    assert "不要用虚假限时优惠逼单" in result["guardrails"]


def test_handle_purchase_objection_for_choice_overload():
    result = advisor.handle_purchase_objection("我不知道哪个好，选择太多了")

    assert result["objection_type"] == "choice_overload"
    assert result["product"] is None
    assert "把选择压缩到 2 个候选" in result["response_points"]


def test_summarize_customer_purchase_profile_finds_cross_sell_opportunities():
    result = advisor.summarize_customer_purchase_profile("CUST001")

    assert result["customer_name"] == "张明"
    assert result["owned_product_count"] == 2
    assert result["lifetime_value"] == 28500.00
    assert "可根据电视保修期推荐延保或升级换新方案" in result["opportunities"]
    assert "高价值客户，推荐中高端方案并强调长期服务保障" in result["opportunities"]
    assert result["recommended_opening"].startswith("张明，我会结合您已有设备")


def test_summarize_customer_purchase_profile_rejects_unknown_customer():
    assert advisor.summarize_customer_purchase_profile("CUST404") == {
        "error": "Customer not found"
    }
