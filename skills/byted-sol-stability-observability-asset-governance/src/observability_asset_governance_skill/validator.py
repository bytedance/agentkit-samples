# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any, Dict, List

from .models import SEVERITY_VALUES, ValidationIssue, ValidationReport


def _findings(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    values = report.get("findings")
    if isinstance(values, list):
        return [item for item in values if isinstance(item, dict)]
    return []


def validate_outputs(
    governance_summary: Dict[str, Any],
    dashboard_drift_report: Dict[str, Any],
    metric_drift_report: Dict[str, Any],
    usage_analysis_report: Dict[str, Any],
    stale_panel_report: Dict[str, Any],
    duplicate_dashboard_report: Dict[str, Any],
    definition_conflict_report: Dict[str, Any],
    asset_registry: Dict[str, Any],
) -> ValidationReport:
    issues: List[ValidationIssue] = []

    reports = [
        dashboard_drift_report,
        metric_drift_report,
        usage_analysis_report,
        stale_panel_report,
        duplicate_dashboard_report,
        definition_conflict_report,
    ]

    flattened: List[Dict[str, Any]] = []
    for report in reports:
        flattened.extend(_findings(report))

    for item in flattened:
        severity = str(item.get("severity") or "").lower()
        if severity not in SEVERITY_VALUES:
            issues.append(ValidationIssue(level="error", rule="severity_enum", message=f"invalid severity: {severity or 'empty'}"))
        recommendation = str(item.get("recommendation") or "").strip()
        if not recommendation:
            issues.append(ValidationIssue(level="error", rule="recommendation_required", message="finding missing recommendation"))
        owner = str(item.get("owner") or "").strip()
        if not owner:
            issues.append(ValidationIssue(level="error", rule="owner_required", message="finding missing owner"))

    expected_total = len(flattened)
    actual_total = int(governance_summary.get("total_findings") or 0)
    if expected_total != actual_total:
        issues.append(
            ValidationIssue(
                level="error",
                rule="summary_recount",
                message=f"governance_summary total_findings mismatch expected={expected_total} actual={actual_total}",
            )
        )

    assets = asset_registry.get("assets")
    if not isinstance(assets, list):
        issues.append(ValidationIssue(level="error", rule="asset_registry_shape", message="asset_registry.assets must be a list"))
    else:
        for item in assets:
            if not isinstance(item, dict):
                issues.append(ValidationIssue(level="error", rule="asset_registry_entry_shape", message="asset entry must be object"))
                continue
            if not str(item.get("asset_type") or "").strip():
                issues.append(ValidationIssue(level="error", rule="asset_type_required", message="asset entry missing asset_type"))
            if not str(item.get("name") or "").strip():
                issues.append(ValidationIssue(level="error", rule="asset_name_required", message="asset entry missing name"))

    summary = {
        "errors": sum(1 for item in issues if item.level == "error"),
        "warnings": sum(1 for item in issues if item.level == "warning"),
        "total_findings": expected_total,
    }

    return ValidationReport(passed=summary["errors"] == 0, summary=summary, issues=issues)
