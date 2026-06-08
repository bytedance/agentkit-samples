# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Dict


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pick_sli_json_file(root: Path) -> Path:
    preferred = [
        "sli-spec.json",
        "sli-spec.v2.all.json",
        "sli-spec.all.json",
    ]
    for name in preferred:
        candidate = root / name
        if candidate.exists() and candidate.is_file():
            return candidate
    json_files = sorted(path for path in root.glob("*.json") if path.is_file())
    if not json_files:
        raise ValueError(f"no json file found in sli model directory: {root}")
    return json_files[0]


def load_sli_model(path: str) -> Dict[str, Any]:
    target = Path(path)
    if not target.exists():
        raise ValueError(f"sli model path not found: {target}")
    if target.is_dir():
        target = _pick_sli_json_file(target)
    return _load_json(target)
