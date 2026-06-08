# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .dashboard_builder import build_grafana_dashboard
from .exporter import write_outputs
from .ia_generator import build_dashboard_ia
from .input_normalizer import normalize_inputs
from .models import PipelineResult
from .panel_compiler import compile_panel_specs
from .traceability import build_traceability
from .validator import validate_design


@dataclass
class PipelineOptions:
    out_dir: str = "output"
    dashboard_title: Optional[str] = None
    focus_service: Optional[str] = None
    offline: bool = False


def run_pipeline(
    sli_model: str,
    arch_model: str,
    repo: str,
    options: PipelineOptions | None = None,
) -> PipelineResult:
    opts = options or PipelineOptions()

    normalized = normalize_inputs(
        sli_model_path=sli_model,
        arch_model_dir=arch_model,
        repo=repo,
        focus_service=opts.focus_service,
        offline=opts.offline,
    )

    ia = build_dashboard_ia(normalized, dashboard_title=opts.dashboard_title)
    panel_specs = compile_panel_specs(normalized, ia)
    grafana_doc = build_grafana_dashboard(ia, panel_specs)
    validation = validate_design(ia, panel_specs)
    traceability = build_traceability(panel_specs, normalized.evidence_items)

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

    output_dir = write_outputs(
        out_base_dir=opts.out_dir,
        repo_slug=normalized.repo_slug,
        ia=ia,
        panel_specs=panel_specs,
        grafana_dashboard=grafana_doc.to_dict(),
        traceability=traceability,
        validation=validation,
        evidence_enriched=evidence_enriched,
    )

    placeholder_panels = sum(1 for panel in panel_specs if panel.confidence == "placeholder")

    return PipelineResult(
        output_dir=output_dir,
        panel_count=len(panel_specs),
        placeholder_panel_count=placeholder_panels,
        page_count=len(ia.pages),
        validation_passed=validation.passed,
    )
