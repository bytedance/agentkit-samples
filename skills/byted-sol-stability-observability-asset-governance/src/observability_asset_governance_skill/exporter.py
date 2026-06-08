# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path

from .models import PipelineArtifacts


def _slug(text: str) -> str:
    chars = [c.lower() if c.isalnum() else "-" for c in text.strip()]
    slug = "".join(chars)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "governance"


def write_outputs(out_base_dir: str, repo_slug: str, artifacts: PipelineArtifacts) -> str:
    outdir = Path(out_base_dir) / _slug(repo_slug)
    outdir.mkdir(parents=True, exist_ok=True)

    outputs = {
        "governance-summary.json": artifacts.governance_summary,
        "dashboard-drift-report.json": artifacts.dashboard_drift_report,
        "metric-drift-report.json": artifacts.metric_drift_report,
        "usage-analysis-report.json": artifacts.usage_analysis_report,
        "stale-panel-report.json": artifacts.stale_panel_report,
        "duplicate-dashboard-report.json": artifacts.duplicate_dashboard_report,
        "definition-conflict-report.json": artifacts.definition_conflict_report,
        "incremental-update-plan.json": artifacts.incremental_update_plan,
        "asset-registry.json": artifacts.asset_registry,
        "validation-report.json": artifacts.validation_report.to_dict(),
        "traceability.json": artifacts.traceability,
        "evidence-index.enriched.json": artifacts.evidence_enriched,
    }

    for filename, payload in outputs.items():
        (outdir / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return str(outdir)
