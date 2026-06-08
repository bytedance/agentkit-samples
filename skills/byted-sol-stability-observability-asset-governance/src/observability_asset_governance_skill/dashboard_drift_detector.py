# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
from typing import Dict, List

from .models import GovernanceFinding, NormalizedGovernanceInputs, PanelTarget, SLIItem


TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")


def _tokens(text: str) -> set[str]:
    return {token for token in TOKEN_PATTERN.findall(text.lower()) if len(token) >= 3}


def _match_score(sli: SLIItem, panel: PanelTarget) -> float:
    sli_tokens = _tokens(f"{sli.sli_name} {sli.sli_type} {sli.measurement}")
    panel_tokens = _tokens(f"{panel.panel_title} {panel.query}")
    if not sli_tokens:
        return 0.0
    overlap = sli_tokens & panel_tokens
    return len(overlap) / len(sli_tokens)


def detect_dashboard_drift(inputs: NormalizedGovernanceInputs) -> Dict[str, object]:
    findings: List[GovernanceFinding] = []

    for sli in inputs.sli_items:
        best = 0.0
        for panel in inputs.panel_targets:
            best = max(best, _match_score(sli, panel))
        if best < 0.2:
            findings.append(
                GovernanceFinding(
                    category="dashboard_drift",
                    finding_type="missing_sli_panel_binding",
                    severity="error",
                    message=f"no panel binding found for SLI: {sli.sli_name}",
                    recommendation="add or update panel/query to reflect current SLI intent",
                    owner="unassigned",
                    asset_refs=[sli.sli_name],
                )
            )

    for panel in inputs.panel_targets:
        query = panel.query.lower()
        if "unknown_" in query or "placeholder" in query:
            findings.append(
                GovernanceFinding(
                    category="dashboard_drift",
                    finding_type="placeholder_query_detected",
                    severity="warning",
                    message=f"panel {panel.panel_id} still uses placeholder query",
                    recommendation="replace with mapped query_template from latest metric mapping",
                    owner="unassigned",
                    asset_refs=[f"panel:{panel.panel_id}"],
                )
            )
        if panel.datasource not in {"prometheus", "loki", "tempo", "internal_tsdb", "grafana"}:
            findings.append(
                GovernanceFinding(
                    category="dashboard_drift",
                    finding_type="unknown_datasource",
                    severity="error",
                    message=f"panel {panel.panel_id} uses unsupported datasource {panel.datasource}",
                    recommendation="normalize datasource to supported value and rebind panel target",
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
