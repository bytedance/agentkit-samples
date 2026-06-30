from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from .models import Finding
except ImportError:  # pragma: no cover - supports direct script execution
    from models import Finding


ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"/Users/[^\\s'\"]+"),
    re.compile(r"[A-Za-z]:\\\\[^\\s'\"]+"),
)
SECRET_LIKE_PATTERNS = (
    re.compile(r"(?i)(access[_-]?key|secret[_-]?key|api[_-]?key|token)\s*="),
    re.compile(r"AKLT[A-Za-z0-9]{12,}"),
)


def cell_source(cell: dict[str, Any]) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(str(part) for part in source)
    return str(source)


def output_text(output: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key in ("text", "ename", "evalue"):
        value = output.get(key)
        if isinstance(value, list):
            chunks.extend(str(part) for part in value)
        elif value:
            chunks.append(str(value))

    data = output.get("data", {})
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                chunks.extend(str(part) for part in value)
            elif value:
                chunks.append(str(value))
    return "".join(chunks)


def has_absolute_path(text: str) -> bool:
    return any(pattern.search(text) for pattern in ABSOLUTE_PATH_PATTERNS)


def has_secret_like_text(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_LIKE_PATTERNS)


def audit_notebook(path: Path, max_output_chars: int = 20_000) -> list[Finding]:
    findings: list[Finding] = []
    try:
        notebook = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [Finding(path, "invalid-notebook-json", str(exc), severity="error")]
    except OSError as exc:
        return [Finding(path, "read-error", str(exc), severity="error")]

    cells = notebook.get("cells", [])
    if not cells:
        findings.append(Finding(path, "empty-notebook", "notebook contains no cells"))

    for cell_index, cell in enumerate(cells, start=1):
        source = cell_source(cell)
        if has_absolute_path(source):
            findings.append(
                Finding(path, "absolute-path", f"cell {cell_index} has local path")
            )
        if has_secret_like_text(source):
            findings.append(
                Finding(path, "secret-like-source", f"cell {cell_index} has secret-like text")
            )

        outputs = cell.get("outputs", [])
        output_size = sum(len(output_text(output)) for output in outputs)
        if output_size > max_output_chars:
            findings.append(
                Finding(
                    path,
                    "large-output",
                    f"cell {cell_index} output has {output_size} characters",
                )
            )
        for output in outputs:
            if has_secret_like_text(output_text(output)):
                findings.append(
                    Finding(
                        path,
                        "secret-like-output",
                        f"cell {cell_index} output has secret-like text",
                    )
                )
    return findings


def collect_notebook_findings(
    root: Path, max_output_chars: int = 20_000
) -> list[Finding]:
    findings: list[Finding] = []
    for notebook in sorted(root.rglob("*.ipynb")):
        if ".ipynb_checkpoints" in notebook.parts:
            continue
        findings.extend(audit_notebook(notebook, max_output_chars=max_output_chars))
    return findings
