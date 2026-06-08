# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Dict, List

from .models import GovernanceFinding, NormalizedGovernanceInputs


def detect_stale_panels(inputs: NormalizedGovernanceInputs) -> Dict[str, object]:
    findings: List[GovernanceFinding] = []
    usage = {item.dashboard_uid: item for item in inputs.usage_stats}
    dashboard_uid = str(inputs.dashboard.get("uid") or "dashboard")
    dashboard_usage = usage.get(dashboard_uid)
    panel_views = dashboard_usage.panel_views if dashboard_usage else {}

    for panel in inputs.panel_targets:
        panel_key = str(panel.panel_id)
        panel_view_count = int(panel_views.get(panel_key, 0))
        query = panel.query.lower()

        if panel_view_count == 0:
            findings.append(
                GovernanceFinding(
                    category="stale_panel",
                    finding_type="unvisited_panel",
                    severity="warning",
                    message=f"panel {panel.panel_id} has no usage records",
                    recommendation="review panel relevance and archive if redundant",
                    owner="unassigned",
                    asset_refs=[f"panel:{panel.panel_id}"],
                )
            )

        if any(token in query for token in ["absent(", "vector(0)", "no_data_metric", "missing_metric"]):
            findings.append(
                GovernanceFinding(
                    category="stale_panel",
                    finding_type="long_empty_pattern",
                    severity="warning",
                    message=f"panel {panel.panel_id} query indicates persistent empty data",
                    recommendation="replace with active metric or remove stale panel",
                    owner="unassigned",
                    asset_refs=[f"panel:{panel.panel_id}"],
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
