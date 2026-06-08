# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Dict, List

from .models import MetricMappingItem, NormalizedGovernanceInputs


def build_incremental_update_plan(inputs: NormalizedGovernanceInputs) -> Dict[str, object]:
    existing_titles = {panel.panel_title.lower() for panel in inputs.panel_targets}
    actions: List[Dict[str, object]] = []

    capability_tokens = [item.name.lower() for item in inputs.architecture_capabilities]

    for sli in inputs.sli_items:
        name_lower = sli.sli_name.lower()
        mapped: MetricMappingItem | None = next((item for item in inputs.mapping_items if item.sli_name == sli.sli_name), None)

        has_panel = any(name_lower[:12] in title for title in existing_titles)
        if has_panel:
            continue

        path_hint = next((token for token in capability_tokens if token in name_lower), "default_path")
        actions.append(
            {
                "sli_name": sli.sli_name,
                "path_hint": path_hint,
                "suggested_panel_title": f"[AUTO] {sli.sli_name}",
                "suggested_query": (mapped.query_template if mapped and mapped.query_template else "sum(rate(request_success_total[5m]))"),
                "datasource": (mapped.datasource if mapped else "prometheus"),
                "confidence": round((mapped.confidence if mapped else 0.4), 3),
            }
        )

    return {
        "summary": {
            "total_actions": len(actions),
        },
        "actions": actions,
    }
