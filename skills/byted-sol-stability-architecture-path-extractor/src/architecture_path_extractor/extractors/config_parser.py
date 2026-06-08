# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
from typing import List
import re

from ..models import Signal


_SERVICE_RE = re.compile(r"^\s{2,}([a-zA-Z0-9_-]+):\s*$")
_DEPEND_RE = re.compile(r"depends_on|redis|postgres|mysql|kafka|rabbitmq|mongo", re.IGNORECASE)


def parse_config_signals(files: List[Path]) -> List[Signal]:
    signals: List[Signal] = []
    for f in files:
        name = f.name.lower()
        if name not in {"docker-compose.yml", "docker-compose.yaml"} and not name.endswith((".yaml", ".yml", ".env")):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for line in text.splitlines():
            m = _SERVICE_RE.search(line)
            if m:
                svc = m.group(1)
                signals.append(Signal(kind="service", source_file=str(f), value=svc, evidence=line.strip()))
            if _DEPEND_RE.search(line):
                signals.append(Signal(kind="dependency_hint", source_file=str(f), value=line.strip(), evidence=line.strip()))
    return signals
