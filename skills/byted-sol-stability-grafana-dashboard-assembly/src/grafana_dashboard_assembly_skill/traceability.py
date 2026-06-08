# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any, Dict, List

from .models import EvidenceItem, FixAction, MetricMappingItem, PanelFinding, TargetValidation


def build_traceability(
    mappings: List[MetricMappingItem],
    validations: List[TargetValidation],
    findings: List[PanelFinding],
    fixes: List[FixAction],
    evidence_items: List[EvidenceItem],
) -> Dict[str, Any]:
    links: List[Dict[str, Any]] = []

    for item in validations:
        matched = [
            ev.evidence_id
            for ev in evidence_items
            if item.panel_title.lower() in ev.summary.lower() or any(token in ev.summary for token in [item.ref_id, str(item.panel_id)])
        ]
        if not matched and evidence_items:
            matched = [evidence_items[0].evidence_id]

        links.append(
            {
                "target_type": "panel_query",
                "target_id": f"{item.panel_id}:{item.target_index}",
                "evidence_ids": matched,
                "rationale": f"validated query for panel={item.panel_title} status={item.status}",
            }
        )

    for fix in fixes:
        links.append(
            {
                "target_type": "auto_fix",
                "target_id": f"{fix.panel_id}:{fix.target_index}:{fix.action}",
                "evidence_ids": [ev.evidence_id for ev in evidence_items[:3]],
                "rationale": f"applied {fix.action} due to {fix.reason}",
            }
        )

    for finding in findings:
        links.append(
            {
                "target_type": "panel_finding",
                "target_id": f"{finding.panel_id}:{finding.finding_type}",
                "evidence_ids": [ev.evidence_id for ev in evidence_items[:2]],
                "rationale": finding.message,
            }
        )

    return {
        "trace_links": links,
        "mapping_summary": [
            {
                "sli_name": item.sli_name,
                "chosen_metric": item.chosen_metric,
                "datasource": item.datasource,
                "confidence": item.confidence,
            }
            for item in mappings
        ],
        "evidence_items": [
            {
                "evidence_id": ev.evidence_id,
                "source_type": ev.source_type,
                "source_path": ev.source_path,
                "locator": ev.locator,
                "summary": ev.summary,
            }
            for ev in evidence_items
        ],
    }
