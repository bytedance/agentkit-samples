# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class InputBundle:
    repo_path: Path
    product_docs: List[Path] = field(default_factory=list)
    arch_diagrams: List[Path] = field(default_factory=list)


def build_input_bundle(repo: str, product_docs: List[str], arch_diagrams: List[str]) -> InputBundle:
    repo_path = Path(repo)
    if not repo_path.exists() or not repo_path.is_dir():
        raise ValueError(f"repo path not found: {repo_path}")

    docs = [Path(x) for x in product_docs if Path(x).exists() and Path(x).is_file()]
    diagrams = [Path(x) for x in arch_diagrams if Path(x).exists() and Path(x).is_file()]
    return InputBundle(repo_path=repo_path, product_docs=docs, arch_diagrams=diagrams)
