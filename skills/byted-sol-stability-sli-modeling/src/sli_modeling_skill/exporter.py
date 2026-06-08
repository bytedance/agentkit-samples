# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
import json
from typing import List

from .modeler import ModelerResult


def _slug(text: str) -> str:
    chars = [c.lower() if c.isalnum() else "-" for c in text.strip()]
    slug = "".join(chars)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "sli-spec"


def write_outputs(result: ModelerResult, out_base_dir: str) -> str:
    if not result.specs:
        raise ValueError("no sli specs to export")

    slug = _slug(result.specs[0].capability)
    outdir = Path(out_base_dir) / slug
    outdir.mkdir(parents=True, exist_ok=True)

    payload = [x.to_dict() for x in result.specs]
    (outdir / "sli-spec.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_lines: List[str] = ["# SLI Modeling Report", ""]
    for idx, spec in enumerate(payload, 1):
        report_lines.append(f"## Spec {idx}")
        for k, v in spec.items():
            report_lines.append(f"- {k}: `{v}`")
        report_lines.append("")
    if result.notes:
        report_lines.append("## Notes")
        for n in result.notes:
            report_lines.append(f"- {n}")

    (outdir / "sli-report.md").write_text("\n".join(report_lines), encoding="utf-8")
    return str(outdir)
