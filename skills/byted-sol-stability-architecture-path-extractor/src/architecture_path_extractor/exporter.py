# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
import json
from typing import Dict, List

from .models import TopologyModel


def _slug(text: str) -> str:
    chars = [c.lower() if c.isalnum() else "-" for c in text.strip()]
    slug = "".join(chars)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "repo"


def write_outputs(model: TopologyModel, out_base_dir: str, repo_slug: str) -> str:
    outdir = Path(out_base_dir) / _slug(repo_slug)
    outdir.mkdir(parents=True, exist_ok=True)

    (outdir / "topology-model.json").write_text(
        json.dumps(model.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    core_lines = ["# Core Links", ""]
    core_lines.append("## Core User Links")
    for p in model.request_paths:
        core_lines.append(f"- {p['name']}: {' -> '.join(p['hops'])}")
    core_lines.append("")
    core_lines.append("## Control Plane Links")
    core_lines.append("- config-change -> resource-dispatch -> permission-check -> rate-limit/quota -> audit")
    core_lines.append("")
    core_lines.append("## Data Plane Links")
    for p in model.request_paths:
        if "data" in p["name"] or "core" in p["name"]:
            core_lines.append(f"- {p['name']}: {' -> '.join(p['hops'])}")
    (outdir / "core-links.md").write_text("\n".join(core_lines), encoding="utf-8")

    risk_lines = ["# Dependency Risk", ""]
    for f in model.failure_points:
        risk_lines.append(f"- {f['component']}: {f['risk']} ({f['impact']})")
    (outdir / "dependency-risk.md").write_text("\n".join(risk_lines), encoding="utf-8")

    gap_lines = ["# Observability Gaps", ""]
    for g in model.observability_hook_points:
        gap_lines.append(f"- {g['component']} [{g['gap_type']}]: {g['missing_signal']} -> {g['suggestion']}")
    (outdir / "observability-gaps.md").write_text("\n".join(gap_lines), encoding="utf-8")

    evidence: List[Dict[str, str]] = []
    for e in model.service_graph.get("edges", []):
        evidence.append({"kind": "edge", "source": e.get("evidence", "")})
    for p in model.request_paths + model.async_paths:
        for src in p.get("evidence", []):
            evidence.append({"kind": "path", "source": str(src)})
    (outdir / "evidence-index.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return str(outdir)
