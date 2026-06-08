# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .asset_registry import build_asset_registry
from .dashboard_drift_detector import detect_dashboard_drift
from .definition_conflict_detector import detect_definition_conflicts
from .duplicate_dashboard_detector import detect_duplicate_dashboards
from .exporter import write_outputs
from .incremental_updater import build_incremental_update_plan
from .input_normalizer import normalize_inputs
from .metric_drift_detector import detect_metric_drift
from .models import PipelineArtifacts, PipelineResult, RuntimeConfig
from .stale_panel_detector import detect_stale_panels
from .traceability import build_traceability
from .usage_analyzer import analyze_usage
from .validator import validate_outputs


@dataclass
class PipelineOptions:
    out_dir: str = "output"
    focus_service: Optional[str] = None
    offline: bool = False
    grafana_url: str = ""
    grafana_token: str = ""
    prom_url: str = ""
    prom_bearer: str = ""
    prom_username: str = ""
    prom_password: str = ""


def _findings_count(report: Dict[str, Any]) -> int:
    findings = report.get("findings")
    if isinstance(findings, list):
        return len(findings)
    return 0


def _severity_count(report: Dict[str, Any], severity: str) -> int:
    findings = report.get("findings")
    if not isinstance(findings, list):
        return 0
    return sum(1 for item in findings if isinstance(item, dict) and str(item.get("severity") or "").lower() == severity)


def run_pipeline(
    sli_spec: str,
    architecture_spec: str,
    metric_mapping_spec: str,
    existing_dashboard: str,
    metrics_catalog: str | None = None,
    usage_stats: str | None = None,
    asset_registry: str | None = None,
    options: PipelineOptions | None = None,
) -> PipelineResult:
    opts = options or PipelineOptions()

    runtime = RuntimeConfig(
        offline=opts.offline,
        grafana_url=opts.grafana_url,
        grafana_token=opts.grafana_token,
        prom_url=opts.prom_url,
        prom_bearer=opts.prom_bearer,
        prom_username=opts.prom_username,
        prom_password=opts.prom_password,
    )

    inputs = normalize_inputs(
        sli_spec_path=sli_spec,
        architecture_spec_path=architecture_spec,
        metric_mapping_spec_path=metric_mapping_spec,
        existing_dashboard_path=existing_dashboard,
        metrics_catalog_path=metrics_catalog,
        usage_stats_path=usage_stats,
        asset_registry_path=asset_registry,
        runtime=runtime,
        focus_service=opts.focus_service,
    )

    dashboard_drift_report = detect_dashboard_drift(inputs)
    metric_drift_report = detect_metric_drift(inputs)
    usage_analysis_report = analyze_usage(inputs)
    stale_panel_report = detect_stale_panels(inputs)
    duplicate_dashboard_report = detect_duplicate_dashboards(inputs)
    definition_conflict_report = detect_definition_conflicts(inputs)
    incremental_update_plan = build_incremental_update_plan(inputs)
    registry_report = build_asset_registry(inputs)

    category_reports = {
        "dashboard_drift": dashboard_drift_report,
        "metric_drift": metric_drift_report,
        "usage_analysis": usage_analysis_report,
        "stale_panel": stale_panel_report,
        "duplicate_dashboard": duplicate_dashboard_report,
        "definition_conflict": definition_conflict_report,
    }

    total_findings = sum(_findings_count(report) for report in category_reports.values())
    governance_summary = {
        "repo_slug": inputs.repo_slug,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_findings": total_findings,
        "errors": sum(_severity_count(report, "error") for report in category_reports.values()),
        "warnings": sum(_severity_count(report, "warning") for report in category_reports.values()),
        "infos": sum(_severity_count(report, "info") for report in category_reports.values()),
        "category_counts": {name: _findings_count(report) for name, report in category_reports.items()},
        "total_assets": int((registry_report.get("summary") or {}).get("total_assets") or 0),
        "total_incremental_actions": int((incremental_update_plan.get("summary") or {}).get("total_actions") or 0),
    }

    validation_report = validate_outputs(
        governance_summary=governance_summary,
        dashboard_drift_report=dashboard_drift_report,
        metric_drift_report=metric_drift_report,
        usage_analysis_report=usage_analysis_report,
        stale_panel_report=stale_panel_report,
        duplicate_dashboard_report=duplicate_dashboard_report,
        definition_conflict_report=definition_conflict_report,
        asset_registry=registry_report,
    )

    traceability = build_traceability(
        inputs=inputs,
        dashboard_drift_report=dashboard_drift_report,
        metric_drift_report=metric_drift_report,
        stale_panel_report=stale_panel_report,
    )

    evidence_enriched = [
        {
            "evidence_id": item.evidence_id,
            "source_type": item.source_type,
            "source_path": item.source_path,
            "locator": item.locator,
            "summary": item.summary,
            "repo_slug": inputs.repo_slug,
        }
        for item in inputs.evidence_items
    ]

    artifacts = PipelineArtifacts(
        governance_summary=governance_summary,
        dashboard_drift_report=dashboard_drift_report,
        metric_drift_report=metric_drift_report,
        usage_analysis_report=usage_analysis_report,
        stale_panel_report=stale_panel_report,
        duplicate_dashboard_report=duplicate_dashboard_report,
        definition_conflict_report=definition_conflict_report,
        incremental_update_plan=incremental_update_plan,
        asset_registry=registry_report,
        validation_report=validation_report,
        traceability=traceability,
        evidence_enriched=evidence_enriched,
    )

    outdir = write_outputs(opts.out_dir, inputs.repo_slug, artifacts)
    return PipelineResult(output_dir=outdir, finding_count=total_findings, overall_pass=validation_report.passed)
