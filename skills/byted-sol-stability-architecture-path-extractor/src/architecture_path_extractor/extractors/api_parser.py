# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
from typing import List
import re

from ..models import Signal


_ROUTE_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\b\s+(/[a-zA-Z0-9_\-/{}/:]*)")
_EXPRESS_RE = re.compile(r"\b(app|router)\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)")


def parse_api_signals(files: List[Path]) -> List[Signal]:
    signals: List[Signal] = []
    for f in files:
        if f.suffix.lower() not in {".py", ".ts", ".js", ".go", ".yaml", ".yml", ".json"}:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for m in _ROUTE_RE.finditer(text):
            method = m.group(1)
            path = m.group(2)
            signals.append(Signal(kind="api_route", source_file=str(f), value=f"{method} {path}", evidence=m.group(0)))

        for m in _EXPRESS_RE.finditer(text):
            method = m.group(2).upper()
            path = m.group(3)
            signals.append(Signal(kind="api_route", source_file=str(f), value=f"{method} {path}", evidence=m.group(0)))

        if "openapi" in text.lower() and "paths:" in text.lower():
            signals.append(Signal(kind="openapi", source_file=str(f), value="openapi-spec", evidence="openapi + paths"))

    return signals
