# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Set

from .models import GovernanceFinding, NormalizedGovernanceInputs


def detect_definition_conflicts(inputs: NormalizedGovernanceInputs) -> Dict[str, object]:
    findings: List[GovernanceFinding] = []
    dims_by_metric: Dict[str, Set[tuple[str, ...]]] = defaultdict(set)

    for mapping in inputs.mapping_items:
        if mapping.chosen_metric:
            dims_by_metric[mapping.chosen_metric].add(tuple(sorted(set(mapping.dimensions))))

    for metric in inputs.catalog_metrics:
        dims_by_metric[metric.name].add(tuple(sorted(set(metric.dimensions))))

    for metric_name, schemas in dims_by_metric.items():
        if len(schemas) < 2:
            continue
        findings.append(
            GovernanceFinding(
                category="definition_conflict",
                finding_type="metric_label_contract_conflict",
                severity="warning",
                message=f"metric {metric_name} has conflicting label definitions across assets",
                recommendation="standardize metric contract and align mappings/dashboard queries",
                owner="unassigned",
                asset_refs=[metric_name],
            )
        )

    return {
        "summary": {
            "total_findings": len(findings),
            "warnings": len(findings),
            "errors": 0,
        },
        "findings": [item.to_dict() for item in findings],
    }
