# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
import json
from typing import Dict, List

from .models import DashboardIA, PanelSpec, ValidationReport


def _slug(text: str) -> str:
    chars = [c.lower() if c.isalnum() else "-" for c in text.strip()]
    slug = "".join(chars)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "repo"


def write_outputs(
    out_base_dir: str,
    repo_slug: str,
    ia: DashboardIA,
    panel_specs: List[PanelSpec],
    grafana_dashboard: Dict[str, object],
    traceability: Dict[str, object],
    validation: ValidationReport,
    evidence_enriched: List[Dict[str, object]],
) -> str:
    outdir = Path(out_base_dir) / _slug(repo_slug)
    outdir.mkdir(parents=True, exist_ok=True)

    (outdir / "dashboard-ia.json").write_text(
        json.dumps(ia.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (outdir / "panel-specs.json").write_text(
        json.dumps([panel.to_dict() for panel in panel_specs], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (outdir / "grafana-dashboard.json").write_text(
        json.dumps(grafana_dashboard, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (outdir / "traceability.json").write_text(
        json.dumps(traceability, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (outdir / "validation-report.json").write_text(
        json.dumps(validation.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (outdir / "evidence-index.enriched.json").write_text(
        json.dumps(evidence_enriched, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return str(outdir)
