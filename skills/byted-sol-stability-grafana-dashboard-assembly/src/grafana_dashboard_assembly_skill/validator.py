# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import List

from .models import AcceptanceReport, ConnectivityCheck, TargetValidation, ValidationIssue, ValidationReport


KNOWN_DATASOURCES = {"prometheus", "loki", "tempo", "internal_tsdb", "mixed", "grafana"}


def validate_pipeline(
    connectivity_checks: List[ConnectivityCheck],
    target_validations: List[TargetValidation],
    acceptance: AcceptanceReport,
) -> ValidationReport:
    issues: List[ValidationIssue] = []

    for item in connectivity_checks:
        if not item.exists:
            issues.append(ValidationIssue(level="error", rule="datasource_exists", message=f"unknown datasource {item.datasource}"))
        if item.status != "ok":
            issues.append(
                ValidationIssue(
                    level="error",
                    rule="datasource_connectivity",
                    message=f"datasource {item.datasource} connectivity failed: {item.message}",
                )
            )

    for item in target_validations:
        if not item.query.strip():
            issues.append(
                ValidationIssue(
                    level="error",
                    rule="query_required",
                    message=f"empty query at panel={item.panel_id} target={item.target_index}",
                )
            )
        if item.datasource not in KNOWN_DATASOURCES:
            issues.append(
                ValidationIssue(
                    level="error",
                    rule="query_datasource_enum",
                    message=f"invalid datasource at panel={item.panel_id} target={item.target_index}: {item.datasource}",
                )
            )

    recomputed_success = round(
        (sum(1 for item in target_validations if item.status == "success") / len(target_validations)),
        3,
    ) if target_validations else 0.0
    if recomputed_success != acceptance.success_rate:
        issues.append(
            ValidationIssue(
                level="error",
                rule="acceptance_consistency",
                message="acceptance success_rate does not match target validations",
            )
        )

    summary = {
        "total_connectivity_checks": len(connectivity_checks),
        "total_target_validations": len(target_validations),
        "errors": sum(1 for issue in issues if issue.level == "error"),
        "warnings": sum(1 for issue in issues if issue.level == "warning"),
    }
    return ValidationReport(passed=summary["errors"] == 0, summary=summary, issues=issues)
