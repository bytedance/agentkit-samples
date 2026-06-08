# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Dict, List

from .models import NormalizedGovernanceInputs, RegistryEntry


def build_asset_registry(inputs: NormalizedGovernanceInputs) -> Dict[str, object]:
    merged: Dict[str, RegistryEntry] = {}

    for entry in inputs.registry_entries:
        key = f"{entry.asset_type}:{entry.asset_id or entry.name}"
        merged[key] = entry.with_last_seen()

    dashboard_uid = str(inputs.dashboard.get("uid") or "dashboard")
    dashboard_title = str(inputs.dashboard.get("title") or "dashboard")
    dashboard_entry = RegistryEntry(
        asset_id=dashboard_uid,
        asset_type="dashboard",
        name=dashboard_title,
        service=inputs.repo_slug,
        owner="unassigned",
        source="governance_detected",
    ).with_last_seen()
    merged[f"dashboard:{dashboard_uid}"] = dashboard_entry

    for panel in inputs.panel_targets:
        panel_entry = RegistryEntry(
            asset_id=f"{dashboard_uid}:{panel.panel_id}:{panel.target_index}",
            asset_type="query",
            name=f"panel-{panel.panel_id}-{panel.ref_id}",
            service=inputs.repo_slug,
            owner="unassigned",
            source="governance_detected",
        ).with_last_seen()
        merged[f"query:{panel_entry.asset_id}"] = panel_entry

    for sli in inputs.sli_items:
        sli_entry = RegistryEntry(
            asset_id=sli.sli_name,
            asset_type="sli",
            name=sli.sli_name,
            service=inputs.repo_slug,
            owner="unassigned",
            source="governance_detected",
        ).with_last_seen()
        merged[f"sli:{sli_entry.asset_id}"] = sli_entry

    entries: List[RegistryEntry] = [merged[key] for key in sorted(merged)]
    return {
        "summary": {
            "total_assets": len(entries),
            "unassigned_owners": sum(1 for item in entries if item.owner == "unassigned"),
        },
        "assets": [
            {
                "asset_id": item.asset_id,
                "asset_type": item.asset_type,
                "name": item.name,
                "service": item.service,
                "owner": item.owner,
                "status": item.status,
                "source": item.source,
                "last_seen": item.last_seen,
            }
            for item in entries
        ],
    }
