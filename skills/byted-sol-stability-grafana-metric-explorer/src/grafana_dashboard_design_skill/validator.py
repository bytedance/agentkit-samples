# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import List, Set

from .models import DashboardIA, PanelSpec, ValidationIssue, ValidationReport


REQUIRED_PAGES = {
    "overview",
    "core-links",
    "service-layers",
    "dependencies",
    "error-analysis",
    "change-rollout-capacity",
}


def _required_panel_fields(spec: PanelSpec) -> List[str]:
    missing: List[str] = []
    if not spec.title:
        missing.append("title")
    if not spec.chart_type:
        missing.append("chart_type")
    if not spec.metric_formula:
        missing.append("metric_formula")
    if not spec.dimensions:
        missing.append("dimensions")
    if not spec.refresh_interval:
        missing.append("refresh_interval")
    if not spec.thresholds:
        missing.append("thresholds")
    if not spec.drilldown.target:
        missing.append("drilldown")
    if not spec.sli_link:
        missing.append("sli_link")
    if not spec.path_link:
        missing.append("path_link")
    return missing


def validate_design(ia: DashboardIA, panel_specs: List[PanelSpec]) -> ValidationReport:
    issues: List[ValidationIssue] = []

    page_ids = {page.page_id for page in ia.pages}
    for page_id in sorted(REQUIRED_PAGES - page_ids):
        issues.append(
            ValidationIssue(
                level="error",
                rule="required_pages",
                message=f"missing required page: {page_id}",
            )
        )

    overview = next((page for page in ia.pages if page.page_id == "overview"), None)
    if overview is None:
        issues.append(
            ValidationIssue(level="error", rule="overview", message="overview page is required")
        )
    else:
        zones = {section.zone_type for section in overview.sections}
        if "health" not in zones or "diagnostic" not in zones:
            issues.append(
                ValidationIssue(
                    level="error",
                    rule="overview_health_diagnostic_split",
                    message="overview must include both health and diagnostic zones",
                )
            )

    health_panels = [panel for panel in panel_specs if panel.zone_type == "health"]
    diagnostic_panels = [panel for panel in panel_specs if panel.zone_type == "diagnostic"]
    event_panels = [panel for panel in panel_specs if panel.zone_type == "event_overlay"]

    if not health_panels:
        issues.append(
            ValidationIssue(level="error", rule="health_panels", message="at least one health panel is required")
        )
    if not diagnostic_panels:
        issues.append(
            ValidationIssue(
                level="error",
                rule="diagnostic_panels",
                message="at least one diagnostic panel is required",
            )
        )

    for panel in panel_specs:
        missing_fields = _required_panel_fields(panel)
        if missing_fields:
            issues.append(
                ValidationIssue(
                    level="error",
                    rule="panel_required_fields",
                    message=f"panel {panel.panel_id} missing fields: {', '.join(missing_fields)}",
                )
            )

    if not event_panels:
        issues.append(
            ValidationIssue(
                level="warning",
                rule="event_overlay",
                message="no event overlay panel found for change/alert timeline",
            )
        )

    formulas = [panel.metric_formula for panel in panel_specs]
    has_rate = any("rate(" in formula for formula in formulas)
    has_volume = any("sum(" in formula for formula in formulas)
    if not (has_rate and has_volume):
        issues.append(
            ValidationIssue(
                level="warning",
                rule="alert_rate_volume",
                message="expected both rate and volume style formulas for alert design",
            )
        )

    sli_links = {panel.sli_link for panel in panel_specs}
    if not sli_links:
        issues.append(
            ValidationIssue(
                level="error",
                rule="sli_mapping",
                message="panel specs must map to at least one sli",
            )
        )

    summary = {
        "total_panels": len(panel_specs),
        "health_panels": len(health_panels),
        "diagnostic_panels": len(diagnostic_panels),
        "event_overlay_panels": len(event_panels),
        "errors": sum(1 for issue in issues if issue.level == "error"),
        "warnings": sum(1 for issue in issues if issue.level == "warning"),
    }

    passed = summary["errors"] == 0
    return ValidationReport(passed=passed, summary=summary, issues=issues)
