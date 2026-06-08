# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .acceptance import build_acceptance_report
from .auto_repair import apply_auto_repair
from .connectivity_checker import run_connectivity_checks
from .exporter import write_outputs
from .input_normalizer import normalize_inputs
from .models import PipelineArtifacts, PipelineResult, RuntimeConfig
from .panel_quality_detector import detect_panel_quality
from .query_adapter import adapt_queries
from .traceability import build_traceability
from .validator import validate_pipeline


@dataclass
class PipelineOptions:
    out_dir: str = "output"
    focus_service: Optional[str] = None
    offline: bool = False
    grafana_url: str = ""
    grafana_token: str = ""
    datasource_uid: str = ""
    prom_url: str = ""
    prom_bearer: str = ""
    prom_username: str = ""
    prom_password: str = ""
    time_range: str = "now-6h,now"
    max_repair_rounds: int = 2


def run_pipeline(
    sli_spec: str,
    metric_mapping_spec: str,
    metrics_catalog: str,
    log_dict: str,
    trace_spans: str,
    existing_dashboard: str,
    options: PipelineOptions | None = None,
) -> PipelineResult:
    opts = options or PipelineOptions()
    runtime = RuntimeConfig(
        offline=opts.offline,
        grafana_url=opts.grafana_url,
        grafana_token=opts.grafana_token,
        datasource_uid=opts.datasource_uid,
        prom_url=opts.prom_url,
        prom_bearer=opts.prom_bearer,
        prom_username=opts.prom_username,
        prom_password=opts.prom_password,
        time_range=opts.time_range,
    )

    normalized = normalize_inputs(
        sli_spec_path=sli_spec,
        metric_mapping_spec_path=metric_mapping_spec,
        metrics_catalog_path=metrics_catalog,
        log_dict_path=log_dict,
        trace_spans_path=trace_spans,
        existing_dashboard_path=existing_dashboard,
        runtime=runtime,
        focus_service=opts.focus_service,
    )

    datasource_names = [item.datasource for item in normalized.mapping_items] + [item.datasource for item in normalized.panel_targets]
    connectivity_checks = run_connectivity_checks(datasource_names, normalized.runtime)

    dashboard = normalized.dashboard
    dashboard_adapted, target_validations = adapt_queries(normalized, dashboard)
    panel_findings = detect_panel_quality(target_validations)

    fix_actions = []
    current_dashboard = dashboard_adapted
    current_validations = target_validations
    current_findings = panel_findings

    for _ in range(max(1, opts.max_repair_rounds)):
        has_issue = any(item.status != "success" for item in current_validations)
        if not has_issue:
            break

        repaired_dashboard, round_actions = apply_auto_repair(
            inputs=normalized,
            dashboard=current_dashboard,
            validations=current_validations,
            findings=current_findings,
        )
        if not round_actions:
            break

        fix_actions.extend(round_actions)
        current_dashboard, current_validations = adapt_queries(normalized, repaired_dashboard)
        current_findings = detect_panel_quality(current_validations)

    acceptance = build_acceptance_report(current_validations, current_findings)
    pipeline_validation = validate_pipeline(connectivity_checks, current_validations, acceptance)
    traceability = build_traceability(
        mappings=normalized.mapping_items,
        validations=current_validations,
        findings=current_findings,
        fixes=fix_actions,
        evidence_items=normalized.evidence_items,
    )

    evidence_enriched = [
        {
            "evidence_id": item.evidence_id,
            "source_type": item.source_type,
            "source_path": item.source_path,
            "locator": item.locator,
            "summary": item.summary,
        }
        for item in normalized.evidence_items
    ]

    artifacts = PipelineArtifacts(
        dashboard_assembled=current_dashboard,
        connectivity_checks=connectivity_checks,
        target_validations=current_validations,
        panel_findings=current_findings,
        fix_actions=fix_actions,
        acceptance=acceptance,
        validation=pipeline_validation,
        traceability=traceability,
        evidence_enriched=evidence_enriched,
    )

    output_dir = write_outputs(opts.out_dir, normalized.repo_slug, artifacts)
    return PipelineResult(
        output_dir=output_dir,
        panel_count=len(current_dashboard.get("panels", [])),
        target_count=len(current_validations),
        overall_pass=acceptance.overall_pass and pipeline_validation.passed,
    )
