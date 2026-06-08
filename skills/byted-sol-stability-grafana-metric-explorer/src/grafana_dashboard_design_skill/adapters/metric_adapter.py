# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
import re
from typing import List, Set


METRIC_PATTERN = re.compile(
    r"\b([a-zA-Z_:][a-zA-Z0-9_:]*?(?:_total|_count|_error_rate|_success_rate|_latency_ms|_duration_ms|_p99|_p95))\b"
)
SUPPORTED_SUFFIXES = {".py", ".ts", ".js", ".go", ".java", ".yml", ".yaml", ".json", ".md"}
MAX_SCAN_FILES = 600


def discover_code_metric_hints(repo_path: str) -> List[str]:
    root = Path(repo_path)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"repo path not found: {root}")

    collected: Set[str] = set()
    scanned = 0
    for path in root.rglob("*"):
        if scanned >= MAX_SCAN_FILES:
            break
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in METRIC_PATTERN.findall(text):
            collected.add(match)

    return sorted(collected)
