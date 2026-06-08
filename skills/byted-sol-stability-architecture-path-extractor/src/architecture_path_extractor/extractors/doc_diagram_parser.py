# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
from typing import List
import re

from ..models import Signal


_KEYWORD_RE = re.compile(
    r"login|auth|agent|model|tool|session|orchestrator|gateway|memory|retrieval|sandbox|browser|audit|quota|rate limit|配置|权限|限流|审计",
    re.IGNORECASE,
)


def parse_doc_diagram_signals(paths: List[Path], kind: str) -> List[Signal]:
    signals: List[Signal] = []
    for p in paths:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            hit = _KEYWORD_RE.search(line)
            if hit:
                signals.append(Signal(kind=kind, source_file=str(p), value=hit.group(0).lower(), evidence=line.strip()))
    return signals
