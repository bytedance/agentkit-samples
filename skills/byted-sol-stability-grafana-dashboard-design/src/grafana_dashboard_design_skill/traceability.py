# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Dict, List

from .models import EvidenceItem, PanelSpec, TraceLink


def build_traceability(
    panel_specs: List[PanelSpec],
    evidence_items: List[EvidenceItem],
) -> Dict[str, List[Dict[str, object]]]:
    evidence_by_id = {item.evidence_id: item for item in evidence_items}
    links: List[TraceLink] = []

    for panel in panel_specs:
        evidence_ids = [ev_id for ev_id in panel.evidence_refs if ev_id in evidence_by_id]
        if not evidence_ids and evidence_items:
            evidence_ids = [evidence_items[0].evidence_id]
        links.append(
            TraceLink(
                target_type="panel_spec",
                target_id=panel.panel_id,
                evidence_ids=evidence_ids,
                rationale=f"panel {panel.panel_id} derived from sli={panel.sli_link} path={panel.path_link}",
            )
        )

    return {
        "trace_links": [
            {
                "target_type": item.target_type,
                "target_id": item.target_id,
                "evidence_ids": item.evidence_ids,
                "rationale": item.rationale,
            }
            for item in links
        ],
        "evidence_items": [
            {
                "evidence_id": item.evidence_id,
                "source_type": item.source_type,
                "source_path": item.source_path,
                "locator": item.locator,
                "summary": item.summary,
            }
            for item in evidence_items
        ],
    }
