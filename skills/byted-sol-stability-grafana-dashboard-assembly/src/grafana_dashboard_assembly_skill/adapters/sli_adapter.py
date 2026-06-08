# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _pick_json_file(root: Path) -> Path:
    preferred = ["sli-spec.json", "sli-spec.all.json", "sli-spec.v2.all.json"]
    for name in preferred:
        candidate = root / name
        if candidate.exists() and candidate.is_file():
            return candidate
    files = sorted(path for path in root.glob("*.json") if path.is_file())
    if not files:
        raise ValueError(f"no json file found in sli spec directory: {root}")
    return files[0]


def load_sli_spec(path: str) -> Any:
    target = Path(path)
    if not target.exists():
        raise ValueError(f"sli spec path not found: {target}")
    if target.is_dir():
        target = _pick_json_file(target)
    return json.loads(target.read_text(encoding="utf-8"))
