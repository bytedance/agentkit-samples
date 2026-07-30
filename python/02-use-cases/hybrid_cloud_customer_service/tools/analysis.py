"""Deterministic synthetic transaction and complaint analysis."""

from __future__ import annotations


def transaction_summary() -> dict[str, object]:
    by_product = {"稳健理财": 528_300, "债券增强": 411_250, "现金管理": 345_100}
    return {"count": 237, "total_profit": sum(by_product.values()), "by_product": by_product}


def complaint_trend() -> dict[str, object]:
    return {
        "quarterly": {"Q1": 234, "Q2": 142, "Q3": 89, "Q4": 118},
        "next_quarter_forecast": "95-110",
        "top_topics": ["到账延迟", "费率透明度"],
    }
