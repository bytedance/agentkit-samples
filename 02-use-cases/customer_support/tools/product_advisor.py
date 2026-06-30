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

from typing import Optional

from tools.crm_mock import get_customer_info, get_customer_purchases


PRODUCT_CATALOG = [
    {
        "product_id": "TV-OLED-G5-65",
        "name": "LG OLED evo AI TV G5 65",
        "category": "tv",
        "brand": "LG",
        "price": 22999,
        "size_inch": 65,
        "panel": "OLED",
        "resolution": "4K",
        "refresh_rate": 120,
        "brightness_nits": 1500,
        "warranty_years": 3,
        "energy_grade": "A+",
        "tags": ["cinema", "premium", "oled", "living_room"],
        "strengths": ["暗场细节优秀", "色彩准确", "适合高端影音"],
        "tradeoffs": ["价格较高", "强光客厅亮度不如高端 Mini LED"],
        "recommended_distance_m": [2.5, 3.5],
        "stock_status": "in_stock",
        "margin_score": 72,
    },
    {
        "product_id": "TV-SONY-A95L-65",
        "name": "Sony XR A95L OLED 65",
        "category": "tv",
        "brand": "Sony",
        "price": 25999,
        "size_inch": 65,
        "panel": "OLED",
        "resolution": "4K",
        "refresh_rate": 120,
        "brightness_nits": 1200,
        "warranty_years": 2,
        "energy_grade": "A+",
        "tags": ["cinema", "premium", "color_accuracy"],
        "strengths": ["画质调校自然", "运动画面处理好", "电影观感稳定"],
        "tradeoffs": ["预算要求高", "保修期短于部分竞品"],
        "recommended_distance_m": [2.5, 3.5],
        "stock_status": "in_stock",
        "margin_score": 68,
    },
    {
        "product_id": "TV-TCL-Q10K-65",
        "name": "TCL Q10K Pro Mini LED 65",
        "category": "tv",
        "brand": "TCL",
        "price": 14999,
        "size_inch": 65,
        "panel": "Mini LED",
        "resolution": "4K",
        "refresh_rate": 144,
        "brightness_nits": 2000,
        "warranty_years": 5,
        "energy_grade": "A+",
        "tags": ["gaming", "bright_room", "value", "living_room"],
        "strengths": ["亮度高", "高刷适合游戏", "保修期长"],
        "tradeoffs": ["暗场纯净度不如 OLED", "机身相对厚重"],
        "recommended_distance_m": [2.5, 3.5],
        "stock_status": "in_stock",
        "margin_score": 86,
    },
    {
        "product_id": "TV-HISENSE-U8Q-65",
        "name": "Hisense U8Q ULED Mini LED 65",
        "category": "tv",
        "brand": "Hisense",
        "price": 12999,
        "size_inch": 65,
        "panel": "Mini LED",
        "resolution": "4K",
        "refresh_rate": 144,
        "brightness_nits": 2500,
        "warranty_years": 3,
        "energy_grade": "A+",
        "tags": ["gaming", "bright_room", "value"],
        "strengths": ["峰值亮度高", "游戏接口完整", "价格相对克制"],
        "tradeoffs": ["品牌生态弱于部分国际品牌"],
        "recommended_distance_m": [2.5, 3.5],
        "stock_status": "in_stock",
        "margin_score": 82,
    },
    {
        "product_id": "TV-TCL-Q9L-65",
        "name": "TCL Q9L Pro Game Mini LED 65",
        "category": "tv",
        "brand": "TCL",
        "price": 10999,
        "size_inch": 65,
        "panel": "Mini LED",
        "resolution": "4K",
        "refresh_rate": 144,
        "brightness_nits": 1800,
        "warranty_years": 3,
        "energy_grade": "A+",
        "tags": ["gaming", "value", "console"],
        "strengths": ["低延迟", "VRR/ALLM 完整", "适合主机游戏"],
        "tradeoffs": ["影音质感不如 OLED"],
        "recommended_distance_m": [2.5, 3.5],
        "stock_status": "in_stock",
        "margin_score": 88,
    },
    {
        "product_id": "TV-XIAOMI-MASTER-75",
        "name": "Xiaomi TV Master 75",
        "category": "tv",
        "brand": "Xiaomi",
        "price": 7999,
        "size_inch": 75,
        "panel": "LED",
        "resolution": "4K",
        "refresh_rate": 120,
        "brightness_nits": 900,
        "warranty_years": 1,
        "energy_grade": "A",
        "tags": ["value", "large_screen", "family"],
        "strengths": ["大尺寸价格友好", "系统生态丰富", "适合家庭客厅"],
        "tradeoffs": ["画质上限不如 Mini LED/OLED", "保修期较短"],
        "recommended_distance_m": [3.0, 4.0],
        "stock_status": "in_stock",
        "margin_score": 76,
    },
    {
        "product_id": "TV-XIAOMI-A2-55",
        "name": "Xiaomi A2 55 4K",
        "category": "tv",
        "brand": "Xiaomi",
        "price": 3299,
        "size_inch": 55,
        "panel": "LED",
        "resolution": "4K",
        "refresh_rate": 60,
        "brightness_nits": 450,
        "warranty_years": 1,
        "energy_grade": "A",
        "tags": ["entry", "budget", "bedroom"],
        "strengths": ["价格低", "基础 4K 观影够用", "适合卧室"],
        "tradeoffs": ["刷新率低", "亮度和分区控光一般"],
        "recommended_distance_m": [2.0, 3.0],
        "stock_status": "in_stock",
        "margin_score": 64,
    },
    {
        "product_id": "SPK-SMART-PRO",
        "name": "智能音箱 Pro",
        "category": "speaker",
        "brand": "VolcHome",
        "price": 899,
        "size_inch": None,
        "panel": None,
        "resolution": None,
        "refresh_rate": None,
        "brightness_nits": None,
        "warranty_years": 1,
        "energy_grade": "A",
        "tags": ["smart_home", "voice", "bundle"],
        "strengths": ["语音控制稳定", "适合搭配电视做智能家居入口"],
        "tradeoffs": ["低频表现不适合重度音乐用户"],
        "recommended_distance_m": None,
        "stock_status": "in_stock",
        "margin_score": 70,
    },
    {
        "product_id": "WARRANTY-PLUS-TV",
        "name": "电视延保服务 2 年",
        "category": "warranty",
        "brand": "VolcCare",
        "price": 699,
        "size_inch": None,
        "panel": None,
        "resolution": None,
        "refresh_rate": None,
        "brightness_nits": None,
        "warranty_years": 2,
        "energy_grade": None,
        "tags": ["warranty", "bundle", "risk_reduction"],
        "strengths": ["降低大件商品维修不确定性", "适合高频使用家庭"],
        "tradeoffs": ["预算极低时可后置考虑"],
        "recommended_distance_m": None,
        "stock_status": "in_stock",
        "margin_score": 92,
    },
]

NEED_KEYWORDS = {
    "gaming": ["游戏", "主机", "ps5", "xbox", "高刷", "低延迟", "电竞"],
    "cinema": ["电影", "观影", "影院", "画质", "色彩", "oled"],
    "bright_room": ["采光", "客厅", "白天", "阳光", "亮"],
    "large_screen": ["大屏", "75", "85", "大尺寸", "家庭"],
    "budget": ["便宜", "预算", "性价比", "入门", "划算"],
    "bedroom": ["卧室", "房间", "出租屋"],
    "smart_home": ["智能家居", "语音", "音箱", "联动"],
}

OBJECTION_RULES = {
    "expensive": {
        "keywords": ["贵", "太贵", "便宜点", "超预算", "价格高"],
        "response_points": [
            "先确认客户的硬预算上限，不直接否定客户感受",
            "解释差价对应的核心体验差异，例如亮度、刷新率、保修期",
            "提供一个降档但保留关键需求的替代款",
        ],
    },
    "brand_trust": {
        "keywords": ["品牌", "质量", "靠谱不", "售后", "保修"],
        "response_points": [
            "说明保修年限和适用范围",
            "优先推荐保修期更长或售后风险更低的商品",
            "避免承诺政策外的免费维修",
        ],
    },
    "choice_overload": {
        "keywords": ["不知道", "纠结", "哪个好", "怎么选"],
        "response_points": [
            "把选择压缩到 2 个候选",
            "用使用场景而不是参数堆叠解释差异",
            "明确告诉客户在当前需求下更推荐哪一款",
        ],
    },
}


def _normalize_text(text: Optional[str]) -> str:
    return (text or "").strip().lower()


def _product_by_id(product_id: str) -> Optional[dict]:
    for product in PRODUCT_CATALOG:
        if product["product_id"] == product_id:
            return product
    return None


def _infer_need_tags(requirements: str) -> list[str]:
    normalized = _normalize_text(requirements)
    tags = []
    for tag, keywords in NEED_KEYWORDS.items():
        if any(keyword.lower() in normalized for keyword in keywords):
            tags.append(tag)
    return tags or ["value"]


def _budget_score(product: dict, budget: Optional[int]) -> int:
    if budget is None:
        return 20
    price = product["price"]
    if price <= budget:
        return 35
    over_ratio = (price - budget) / max(budget, 1)
    if over_ratio <= 0.1:
        return 15
    if over_ratio <= 0.25:
        return 5
    return -30


def _need_match_score(product: dict, need_tags: list[str]) -> int:
    product_tags = set(product["tags"])
    matched = product_tags.intersection(need_tags)
    return len(matched) * 18


def _room_fit_score(product: dict, viewing_distance_m: Optional[float]) -> int:
    distance_range = product.get("recommended_distance_m")
    if viewing_distance_m is None or not distance_range:
        return 0
    minimum, maximum = distance_range
    if minimum <= viewing_distance_m <= maximum:
        return 15
    if abs(viewing_distance_m - minimum) <= 0.4 or abs(viewing_distance_m - maximum) <= 0.4:
        return 5
    return -10


def _history_score(customer_id: Optional[str], product: dict) -> int:
    if not customer_id:
        return 0
    purchases = get_customer_purchases(customer_id)
    if not purchases:
        return 0
    owned_categories = {
        "tv" if "电视" in purchase["product_name"] else "speaker"
        for purchase in purchases
    }
    if product["category"] == "warranty" and "tv" in owned_categories:
        return 10
    if product["category"] in owned_categories:
        return -5
    return 6


def _score_product(
    product: dict,
    need_tags: list[str],
    budget: Optional[int],
    viewing_distance_m: Optional[float],
    customer_id: Optional[str],
) -> tuple[int, list[str]]:
    reasons = []
    score = 0
    budget_points = _budget_score(product, budget)
    need_points = _need_match_score(product, need_tags)
    room_points = _room_fit_score(product, viewing_distance_m)
    history_points = _history_score(customer_id, product)
    score += budget_points + need_points + room_points + history_points
    score += product["margin_score"] // 10

    if need_points > 0:
        reasons.append("匹配客户核心使用场景")
    if budget is not None and product["price"] <= budget:
        reasons.append("价格在预算内")
    elif budget is not None:
        reasons.append("价格略高，需要解释体验差异")
    if room_points > 0:
        reasons.append("观看距离匹配")
    if product["warranty_years"] >= 3:
        reasons.append("保修期较长，售后风险更低")
    if product["stock_status"] != "in_stock":
        score -= 80
        reasons.append("当前库存不足")
    return score, reasons


def list_available_products(category: Optional[str] = None, max_price: Optional[int] = None) -> dict:
    """列出当前可售商品，可按品类和价格过滤。"""
    products = []
    for product in PRODUCT_CATALOG:
        if product["stock_status"] != "in_stock":
            continue
        if category and product["category"] != category:
            continue
        if max_price is not None and product["price"] > max_price:
            continue
        products.append(_public_product_view(product))
    return {"count": len(products), "products": products}


def recommend_products(
    requirements: str,
    budget: Optional[int] = None,
    customer_id: Optional[str] = None,
    viewing_distance_m: Optional[float] = None,
    limit: int = 3,
) -> dict:
    """根据客户需求、预算、观看距离和历史购买生成商品推荐。"""
    if not _normalize_text(requirements):
        return {"error": "requirements is required"}
    if budget is not None and budget <= 0:
        return {"error": "budget must be greater than 0"}
    if customer_id and get_customer_info(customer_id).get("error"):
        return {"error": "Customer not found"}

    need_tags = _infer_need_tags(requirements)
    ranked = []
    for product in PRODUCT_CATALOG:
        if product["category"] not in {"tv", "speaker"}:
            continue
        score, reasons = _score_product(
            product,
            need_tags,
            budget,
            viewing_distance_m,
            customer_id,
        )
        ranked.append(
            {
                "product": _public_product_view(product),
                "score": score,
                "reasons": reasons,
                "matched_need_tags": sorted(set(product["tags"]).intersection(need_tags)),
            }
        )
    ranked.sort(key=lambda item: (-item["score"], item["product"]["price"]))
    return {
        "need_tags": need_tags,
        "budget": budget,
        "recommendations": ranked[:limit],
    }


def compare_products(product_ids: list[str]) -> dict:
    """对比多个商品的关键参数和适合人群。"""
    if len(product_ids) < 2:
        return {"error": "at least two product_ids are required"}
    products = []
    missing = []
    for product_id in product_ids:
        product = _product_by_id(product_id)
        if product is None:
            missing.append(product_id)
        else:
            products.append(product)
    if missing:
        return {"error": "Product not found", "missing_product_ids": missing}

    comparison = []
    for product in products:
        comparison.append(
            {
                "product_id": product["product_id"],
                "name": product["name"],
                "price": product["price"],
                "panel": product["panel"],
                "refresh_rate": product["refresh_rate"],
                "brightness_nits": product["brightness_nits"],
                "warranty_years": product["warranty_years"],
                "best_for": _best_for(product),
                "tradeoffs": product["tradeoffs"],
            }
        )
    cheapest = min(products, key=lambda item: item["price"])
    longest_warranty = max(products, key=lambda item: item["warranty_years"])
    return {
        "products": comparison,
        "summary": {
            "lowest_price": cheapest["product_id"],
            "longest_warranty": longest_warranty["product_id"],
            "highest_refresh_rate": max(products, key=lambda item: item["refresh_rate"] or 0)[
                "product_id"
            ],
        },
    }


def estimate_room_fit(
    product_id: str,
    viewing_distance_m: float,
    room_brightness: str = "normal",
) -> dict:
    """判断电视尺寸、亮度和观看距离是否适合当前房间。"""
    product = _product_by_id(product_id)
    if product is None:
        return {"error": "Product not found"}
    if product["category"] != "tv":
        return {"error": "room fit is only available for tv products"}
    if viewing_distance_m <= 0:
        return {"error": "viewing_distance_m must be greater than 0"}

    distance_range = product["recommended_distance_m"]
    minimum, maximum = distance_range
    if viewing_distance_m < minimum:
        fit = "too_close"
        advice = "距离偏近，建议降低尺寸或确认是否能接受更强沉浸感"
    elif viewing_distance_m > maximum:
        fit = "too_far"
        advice = "距离偏远，建议考虑更大尺寸或提高预算"
    else:
        fit = "good"
        advice = "观看距离匹配，尺寸选择合理"

    brightness_warning = None
    if room_brightness == "bright" and product["brightness_nits"] < 1000:
        brightness_warning = "房间采光强时，该型号亮度可能不够从容"
    return {
        "product_id": product_id,
        "fit": fit,
        "recommended_distance_m": distance_range,
        "viewing_distance_m": viewing_distance_m,
        "advice": advice,
        "brightness_warning": brightness_warning,
    }


def build_purchase_bundle(
    main_product_id: str,
    include_warranty: bool = True,
    include_smart_speaker: bool = False,
    budget: Optional[int] = None,
) -> dict:
    """围绕主商品生成可解释的套餐建议。"""
    main_product = _product_by_id(main_product_id)
    if main_product is None:
        return {"error": "Product not found"}
    if main_product["category"] != "tv":
        return {"error": "bundle main product must be a tv"}

    items = [main_product]
    if include_warranty:
        warranty = _product_by_id("WARRANTY-PLUS-TV")
        if warranty:
            items.append(warranty)
    if include_smart_speaker:
        speaker = _product_by_id("SPK-SMART-PRO")
        if speaker:
            items.append(speaker)

    total_price = sum(item["price"] for item in items)
    savings = 0
    if include_warranty and include_smart_speaker:
        savings = 300
    elif include_warranty:
        savings = 100
    payable = total_price - savings
    budget_status = "within_budget"
    if budget is not None and payable > budget:
        budget_status = "over_budget"

    return {
        "main_product": _public_product_view(main_product),
        "items": [_public_product_view(item) for item in items],
        "total_price": total_price,
        "bundle_savings": savings,
        "payable_price": payable,
        "budget_status": budget_status,
        "selling_points": _bundle_selling_points(items),
    }


def handle_purchase_objection(
    objection: str,
    product_id: Optional[str] = None,
    budget: Optional[int] = None,
) -> dict:
    """根据客户异议生成导购回应要点和替代建议。"""
    text = _normalize_text(objection)
    if not text:
        return {"error": "objection is required"}
    matched_key = "choice_overload"
    for key, rule in OBJECTION_RULES.items():
        if any(keyword in text for keyword in rule["keywords"]):
            matched_key = key
            break
    product = _product_by_id(product_id) if product_id else None
    alternatives = []
    if matched_key == "expensive" and budget:
        alternatives = recommend_products(
            objection,
            budget=budget,
            limit=2,
        ).get("recommendations", [])
    elif product:
        alternatives = recommend_products(
            "性价比 替代",
            budget=product["price"],
            limit=2,
        ).get("recommendations", [])

    return {
        "objection_type": matched_key,
        "response_points": OBJECTION_RULES[matched_key]["response_points"],
        "product": _public_product_view(product) if product else None,
        "alternatives": alternatives,
        "guardrails": [
            "不要贬低客户预算",
            "不要用虚假限时优惠逼单",
            "明确说明推荐理由和取舍",
        ],
    }


def summarize_customer_purchase_profile(customer_id: str) -> dict:
    """基于客户资料和购买历史生成导购画像。"""
    customer = get_customer_info(customer_id)
    if "error" in customer:
        return customer
    purchases = get_customer_purchases(customer_id)
    owned_serials = [purchase["serial_number"] for purchase in purchases]
    owns_tv = any("电视" in purchase["product_name"] for purchase in purchases)
    owns_speaker = any("音箱" in purchase["product_name"] for purchase in purchases)
    opportunities = []
    if owns_tv and not owns_speaker:
        opportunities.append("可推荐智能音箱作为电视语音控制和智能家居入口")
    if owns_tv:
        opportunities.append("可根据电视保修期推荐延保或升级换新方案")
    if customer["lifetime_value"] >= 20000:
        opportunities.append("高价值客户，推荐中高端方案并强调长期服务保障")

    return {
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "owned_serials": owned_serials,
        "owned_product_count": len(purchases),
        "lifetime_value": customer["lifetime_value"],
        "preferred_channels": customer["communication_preferences"],
        "opportunities": opportunities,
        "recommended_opening": _profile_opening(customer, opportunities),
    }


def _public_product_view(product: Optional[dict]) -> Optional[dict]:
    if product is None:
        return None
    keys = [
        "product_id",
        "name",
        "category",
        "brand",
        "price",
        "size_inch",
        "panel",
        "resolution",
        "refresh_rate",
        "brightness_nits",
        "warranty_years",
        "energy_grade",
        "tags",
        "strengths",
        "tradeoffs",
    ]
    return {key: product[key] for key in keys}


def _best_for(product: dict) -> list[str]:
    mapping = {
        "gaming": "游戏玩家",
        "cinema": "高端影音",
        "bright_room": "明亮客厅",
        "large_screen": "大屏家庭观影",
        "budget": "预算敏感客户",
        "bedroom": "卧室或小空间",
        "smart_home": "智能家居联动",
    }
    return [mapping[tag] for tag in product["tags"] if tag in mapping]


def _bundle_selling_points(items: list[dict]) -> list[str]:
    points = []
    categories = {item["category"] for item in items}
    if "warranty" in categories:
        points.append("延保降低大件电视后续维修不确定性")
    if "speaker" in categories:
        points.append("智能音箱可增强语音控制和家庭联动体验")
    if len(items) == 1:
        points.append("仅保留主商品，适合严格控制预算")
    return points


def _profile_opening(customer: dict, opportunities: list[str]) -> str:
    if opportunities:
        return f"{customer['name']}，我会结合您已有设备和预算，优先推荐更匹配的升级方案。"
    return f"{customer['name']}，我先了解您的使用场景和预算，再帮您缩小选择范围。"
