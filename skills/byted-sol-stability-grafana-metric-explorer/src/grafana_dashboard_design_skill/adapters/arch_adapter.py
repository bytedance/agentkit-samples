# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Dict, List


REQUIRED_FILES = [
    "topology-model.json",
    "core-links.md",
    "dependency-risk.md",
    "observability-gaps.md",
    "evidence-index.json",
]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_arch_model(path: str) -> Dict[str, Any]:
    root = Path(path)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"arch model directory not found: {root}")

    missing: List[str] = []
    for filename in REQUIRED_FILES:
        if not (root / filename).exists():
            missing.append(filename)
    if missing:
        raise ValueError(f"arch model missing required files: {', '.join(missing)}")

    return {
        "topology_model": _read_json(root / "topology-model.json"),
        "core_links_md": _read_text(root / "core-links.md"),
        "dependency_risk_md": _read_text(root / "dependency-risk.md"),
        "observability_gaps_md": _read_text(root / "observability-gaps.md"),
        "evidence_index": _read_json(root / "evidence-index.json"),
    }
