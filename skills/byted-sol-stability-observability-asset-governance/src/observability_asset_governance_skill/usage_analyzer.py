# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Dict, List

from .models import GovernanceFinding, NormalizedGovernanceInputs


def analyze_usage(inputs: NormalizedGovernanceInputs) -> Dict[str, object]:
    findings: List[GovernanceFinding] = []

    for stat in inputs.usage_stats:
        if stat.views == 0:
            findings.append(
                GovernanceFinding(
                    category="usage_analysis",
                    finding_type="unused_dashboard",
                    severity="warning",
                    message=f"dashboard has zero views: {stat.dashboard_title}",
                    recommendation="mark for archive review or validate routing/oncall links",
                    owner="unassigned",
                    asset_refs=[stat.dashboard_uid],
                )
            )
        if stat.favorites == 0 and stat.oncall_visits > 0:
            findings.append(
                GovernanceFinding(
                    category="usage_analysis",
                    finding_type="oncall_low_subscription",
                    severity="info",
                    message=f"oncall relies on dashboard but favorites remain low: {stat.dashboard_title}",
                    recommendation="improve discoverability and pin dashboard in oncall runbook",
                    owner="unassigned",
                    asset_refs=[stat.dashboard_uid],
                )
            )
        if stat.oncall_visits == 0 and stat.views > 0:
            findings.append(
                GovernanceFinding(
                    category="usage_analysis",
                    finding_type="non_oncall_usage_only",
                    severity="info",
                    message=f"dashboard appears used outside oncall workflows: {stat.dashboard_title}",
                    recommendation="verify incident-response ownership and escalation linkage",
                    owner="unassigned",
                    asset_refs=[stat.dashboard_uid],
                )
            )

    return {
        "summary": {
            "total_dashboards": len(inputs.usage_stats),
            "total_findings": len(findings),
            "errors": 0,
            "warnings": sum(1 for item in findings if item.severity == "warning"),
            "infos": sum(1 for item in findings if item.severity == "info"),
        },
        "findings": [item.to_dict() for item in findings],
    }
