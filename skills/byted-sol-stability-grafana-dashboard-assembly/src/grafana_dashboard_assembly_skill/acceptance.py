# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import List

from .models import AcceptanceReport, PanelFinding, TargetValidation


def build_acceptance_report(validations: List[TargetValidation], findings: List[PanelFinding]) -> AcceptanceReport:
    total = len(validations)
    success = sum(1 for item in validations if item.status == "success")
    success_rate = round((success / total), 3) if total else 0.0

    empty_panels = {item.panel_id for item in findings if item.finding_type == "no_data"}
    error_query_count = sum(1 for item in validations if item.status == "error")

    manual_items = []
    for finding in findings:
        if finding.severity in {"warning", "blocker"}:
            manual_items.append(f"panel {finding.panel_id} {finding.finding_type}: {finding.message}")

    blocker_count = sum(1 for finding in findings if finding.severity == "blocker")
    overall_pass = (
        success_rate >= 0.95
        and error_query_count == 0
        and len(empty_panels) <= 1
        and blocker_count == 0
    )

    return AcceptanceReport(
        success_rate=success_rate,
        empty_panels_count=len(empty_panels),
        error_query_count=error_query_count,
        manual_confirmation_items=manual_items,
        overall_pass=overall_pass,
    )
