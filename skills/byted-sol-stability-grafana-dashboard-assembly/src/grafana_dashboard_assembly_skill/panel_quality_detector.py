# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
from typing import Dict, List

from .models import PanelFinding, TargetValidation


def _grouping_label_count(query: str) -> int:
    total = 0
    for match in re.finditer(r"by\s*\(([^)]*)\)", query):
        parts = [item.strip() for item in match.group(1).split(",") if item.strip()]
        total += len(parts)
    return total


def detect_panel_quality(validations: List[TargetValidation]) -> List[PanelFinding]:
    findings: List[PanelFinding] = []

    for item in validations:
        if not item.has_data:
            findings.append(
                PanelFinding(
                    panel_id=item.panel_id,
                    panel_title=item.panel_title,
                    severity="warning",
                    finding_type="no_data",
                    message="query has no data in selected range",
                    target_index=item.target_index,
                )
            )
        if not item.labels_ok:
            findings.append(
                PanelFinding(
                    panel_id=item.panel_id,
                    panel_title=item.panel_title,
                    severity="warning",
                    finding_type="wrong_labels",
                    message="query labels do not satisfy required dimensions",
                    target_index=item.target_index,
                )
            )
        if not item.aggregation_ok:
            findings.append(
                PanelFinding(
                    panel_id=item.panel_id,
                    panel_title=item.panel_title,
                    severity="warning",
                    finding_type="misleading_aggregation",
                    message="aggregation semantics do not match sli intent",
                    target_index=item.target_index,
                )
            )
        if item.status == "error":
            findings.append(
                PanelFinding(
                    panel_id=item.panel_id,
                    panel_title=item.panel_title,
                    severity="blocker",
                    finding_type="query_error",
                    message="query is not executable",
                    target_index=item.target_index,
                )
            )

        grouping = _grouping_label_count(item.query)
        if grouping >= 4:
            findings.append(
                PanelFinding(
                    panel_id=item.panel_id,
                    panel_title=item.panel_title,
                    severity="warning",
                    finding_type="result_density_risk",
                    message="query grouping is too dense and may create noisy panel output",
                    target_index=item.target_index,
                )
            )

    by_panel: Dict[int, int] = {}
    for finding in findings:
        by_panel[finding.panel_id] = by_panel.get(finding.panel_id, 0) + 1

    for panel_id, count in by_panel.items():
        if count >= 3:
            title = next((item.panel_title for item in validations if item.panel_id == panel_id), "panel")
            findings.append(
                PanelFinding(
                    panel_id=panel_id,
                    panel_title=title,
                    severity="warning",
                    finding_type="panel_quality_risk",
                    message="panel has multiple quality findings and needs manual confirmation",
                )
            )

    return findings
