# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
from typing import List
import json
import re

from ..models import Signal


_MQ_RE = re.compile(r"kafka|rabbitmq|sqs|pubsub|queue|topic", re.IGNORECASE)
_DB_RE = re.compile(r"postgres|mysql|mongodb|redis|dynamodb|sqlite", re.IGNORECASE)


def parse_dependency_signals(files: List[Path]) -> List[Signal]:
    signals: List[Signal] = []
    for f in files:
        name = f.name.lower()
        if name == "package.json":
            try:
                payload = json.loads(f.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            deps = payload.get("dependencies", {})
            for dep in deps.keys():
                kind = "third_party"
                if _MQ_RE.search(dep):
                    kind = "mq"
                elif _DB_RE.search(dep):
                    kind = "db_or_cache"
                signals.append(Signal(kind=kind, source_file=str(f), value=dep, evidence=dep))
            continue

        if name in {"pnpm-workspace.yaml", "requirements.txt", "poetry.lock", "pom.xml", "go.mod"}:
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line in text.splitlines():
                raw = line.strip()
                if not raw:
                    continue
                if _MQ_RE.search(raw):
                    signals.append(Signal(kind="mq", source_file=str(f), value=raw, evidence=raw))
                elif _DB_RE.search(raw):
                    signals.append(Signal(kind="db_or_cache", source_file=str(f), value=raw, evidence=raw))
                elif "packages:" in raw or raw.startswith("-"):
                    signals.append(Signal(kind="workspace", source_file=str(f), value=raw, evidence=raw))
    return signals
