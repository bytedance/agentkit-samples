# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
from typing import Dict, List, Set

from .models import GovernanceFinding, MetricMappingItem, NormalizedGovernanceInputs


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


def _extract_metric_names(query: str) -> Set[str]:
    names = set()
    for token in METRIC_PATTERN.findall(query):
        if token not in RESERVED:
            names.add(token)
    return names


def _catalog_lookup(inputs: NormalizedGovernanceInputs) -> Dict[str, Set[str]]:
    lookup: Dict[str, Set[str]] = {}
    for item in inputs.catalog_metrics:
        lookup[item.name] = set(item.dimensions)
    return lookup


def detect_metric_drift(inputs: NormalizedGovernanceInputs) -> Dict[str, object]:
    findings: List[GovernanceFinding] = []
    catalog = _catalog_lookup(inputs)

    for mapping in inputs.mapping_items:
        if not mapping.chosen_metric:
            continue

        if mapping.chosen_metric not in catalog:
            findings.append(
                GovernanceFinding(
                    category="metric_drift",
                    finding_type="metric_sunset_or_missing",
                    severity="error",
                    message=f"mapped metric not found in catalog: {mapping.chosen_metric}",
                    recommendation="replace metric using schema-aware repair and refresh mapping",
                    owner="unassigned",
                    asset_refs=[mapping.sli_name, mapping.chosen_metric],
                )
            )
            continue

        required = set(mapping.dimensions)
        available = catalog[mapping.chosen_metric]
        if required and not required.issubset(available):
            missing = sorted(required - available)
            findings.append(
                GovernanceFinding(
                    category="metric_drift",
                    finding_type="label_schema_drift",
                    severity="warning",
                    message=f"label drift on {mapping.chosen_metric}: missing {', '.join(missing)}",
                    recommendation="update query label set or instrumentation labels to restore contract",
                    owner="unassigned",
                    asset_refs=[mapping.chosen_metric],
                )
            )

        if mapping.confidence < 0.5 and mapping.missing_gap == "none":
            findings.append(
                GovernanceFinding(
                    category="metric_drift",
                    finding_type="confidence_gap_conflict",
                    severity="warning",
                    message=f"low confidence mapping marked as none gap: {mapping.sli_name}",
                    recommendation="mark drift gap explicitly and trigger query repair suggestion",
                    owner="unassigned",
                    asset_refs=[mapping.sli_name, mapping.chosen_metric],
                )
            )

    for panel in inputs.panel_targets:
        query = panel.query.lower()
        if any(token in query for token in ["absent(", "missing_metric", "no_data_metric"]):
            findings.append(
                GovernanceFinding(
                    category="metric_drift",
                    finding_type="no_data_query_pattern",
                    severity="warning",
                    message=f"panel {panel.panel_id} query indicates no-data risk",
                    recommendation="validate metric liveliness window and migrate to active metric",
                    owner="unassigned",
                    asset_refs=[f"panel:{panel.panel_id}"],
                )
            )
        unknown_metrics = [name for name in _extract_metric_names(panel.query) if name not in catalog]
        if unknown_metrics:
            findings.append(
                GovernanceFinding(
                    category="metric_drift",
                    finding_type="query_uses_unknown_metric",
                    severity="warning",
                    message=f"panel {panel.panel_id} references unknown metrics: {', '.join(sorted(set(unknown_metrics)))}",
                    recommendation="re-generate query from latest mapping/catalog",
                    owner="unassigned",
                    asset_refs=[f"panel:{panel.panel_id}"],
                )
            )

    return {
        "summary": {
            "total_findings": len(findings),
            "errors": sum(1 for item in findings if item.severity == "error"),
            "warnings": sum(1 for item in findings if item.severity == "warning"),
        },
        "findings": [item.to_dict() for item in findings],
    }
