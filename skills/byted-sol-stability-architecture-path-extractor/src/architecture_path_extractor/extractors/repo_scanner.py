# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
from typing import List


def scan_repo_files(repo_path: Path) -> List[Path]:
    files: List[Path] = []
    for p in repo_path.rglob("*"):
        if p.is_dir():
            continue
        rel = p.relative_to(repo_path)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if "node_modules" in rel.parts:
            continue
        files.append(p)
    return files
