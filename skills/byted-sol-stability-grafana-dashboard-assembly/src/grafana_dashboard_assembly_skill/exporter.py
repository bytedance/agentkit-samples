# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict

from .models import PipelineArtifacts


def _slug(text: str) -> str:
    chars = [c.lower() if c.isalnum() else "-" for c in text.strip()]
    slug = "".join(chars)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "dashboard"


def write_outputs(out_base_dir: str, repo_slug: str, artifacts: PipelineArtifacts) -> str:
    outdir = Path(out_base_dir) / _slug(repo_slug)
    outdir.mkdir(parents=True, exist_ok=True)

    (outdir / "dashboard-assembled.json").write_text(
        json.dumps(artifacts.dashboard_assembled, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    validation_report: Dict[str, object] = {
        "pipeline_validation": artifacts.validation.to_dict(),
        "connectivity_checks": [asdict(item) for item in artifacts.connectivity_checks],
        "target_validations": [asdict(item) for item in artifacts.target_validations],
        "panel_findings": [asdict(item) for item in artifacts.panel_findings],
    }
    (outdir / "validation-report.json").write_text(
        json.dumps(validation_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (outdir / "autofix-report.json").write_text(
        json.dumps({"fix_actions": [asdict(item) for item in artifacts.fix_actions]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (outdir / "acceptance-report.json").write_text(
        json.dumps(artifacts.acceptance.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (outdir / "traceability.json").write_text(
        json.dumps(artifacts.traceability, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (outdir / "evidence-index.enriched.json").write_text(
        json.dumps(artifacts.evidence_enriched, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return str(outdir)
