# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
from typing import Any, Dict, List

from .models import NormalizedGovernanceInputs


METRIC_PATTERN = re.compile(r"\b([a-zA-Z_:][a-zA-Z0-9_:]*)\b")
RESERVED = {
    "sum",
    "rate",
    "irate",
    "increase",
    "clamp_min",
    "clamp_max",
    "histogram_quantile",
    "avg",
    "min",
    "max",
    "count",
    "by",
    "without",
    "topk",
    "bottomk",
}


def _query_metrics(query: str) -> List[str]:
    metrics = []
    for token in METRIC_PATTERN.findall(query):
        if token in RESERVED:
            continue
        metrics.append(token)
    return sorted(set(metrics))


def build_traceability(
    inputs: NormalizedGovernanceInputs,
    dashboard_drift_report: Dict[str, Any],
    metric_drift_report: Dict[str, Any],
    stale_panel_report: Dict[str, Any],
) -> Dict[str, Any]:
    sli_links = []
    for mapping in inputs.mapping_items:
        sli_links.append(
            {
                "sli_name": mapping.sli_name,
                "metric": mapping.chosen_metric,
                "datasource": mapping.datasource,
                "confidence": mapping.confidence,
            }
        )

    panel_links = []
    for panel in inputs.panel_targets:
        panel_links.append(
            {
                "panel_id": panel.panel_id,
                "panel_title": panel.panel_title,
                "query": panel.query,
                "metrics": _query_metrics(panel.query),
            }
        )

    finding_links = []
    for category, report in [
        ("dashboard_drift", dashboard_drift_report),
        ("metric_drift", metric_drift_report),
        ("stale_panel", stale_panel_report),
    ]:
        for item in report.get("findings", []):
            finding_links.append(
                {
                    "category": category,
                    "severity": item.get("severity"),
                    "asset_refs": item.get("asset_refs", []),
                    "message": item.get("message"),
                }
            )

    return {
        "sli_to_metric": sli_links,
        "panel_to_query": panel_links,
        "finding_links": finding_links,
        "evidence_refs": [
            {
                "evidence_id": item.evidence_id,
                "source_type": item.source_type,
                "source_path": item.source_path,
                "locator": item.locator,
            }
            for item in inputs.evidence_items
        ],
    }
