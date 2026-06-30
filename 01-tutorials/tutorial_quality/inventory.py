from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable

try:
    from .models import Finding, TutorialInventory
except ImportError:  # pragma: no cover - supports direct script execution
    from models import Finding, TutorialInventory


IGNORED_DIRS = {
    ".git",
    ".ipynb_checkpoints",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "images",
    "img",
}
DATA_SUFFIXES = {".csv", ".json", ".jsonl", ".parquet", ".tsv", ".txt"}
IMAGE_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
MARKER_NAMES = {
    ".env.example",
    ".env.template",
    "agent.py",
    "app.py",
    "client.py",
    "main.py",
    "pyproject.toml",
    "requirements.txt",
}


def is_ignored(path: Path) -> bool:
    return any(part in IGNORED_DIRS for part in path.parts)


def iter_candidate_dirs(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_dir():
            continue
        relative = path.relative_to(root)
        if is_ignored(relative):
            continue
        yield path


def has_tutorial_marker(path: Path) -> bool:
    for child in path.iterdir():
        if not child.is_file():
            continue
        if child.name in MARKER_NAMES:
            return True
        if child.suffix == ".ipynb":
            return True
    return False


def classify_tutorial_dir(path: Path) -> TutorialInventory:
    notebooks: list[Path] = []
    python_files: list[Path] = []
    readme_files: list[Path] = []
    requirements_files: list[Path] = []
    pyproject_files: list[Path] = []
    env_templates: list[Path] = []
    data_files: list[Path] = []
    image_files: list[Path] = []

    for child in sorted(path.iterdir()):
        if not child.is_file():
            continue
        suffix = child.suffix.lower()
        name_lower = child.name.lower()
        if suffix == ".ipynb":
            notebooks.append(child)
        elif suffix == ".py":
            python_files.append(child)
        elif name_lower.startswith("readme") and suffix == ".md":
            readme_files.append(child)
        elif child.name == "requirements.txt":
            requirements_files.append(child)
        elif child.name == "pyproject.toml":
            pyproject_files.append(child)
        elif child.name in {".env.example", ".env.template"}:
            env_templates.append(child)
        elif suffix in DATA_SUFFIXES:
            data_files.append(child)
        elif suffix in IMAGE_SUFFIXES:
            image_files.append(child)

    return TutorialInventory(
        path=path,
        notebooks=tuple(notebooks),
        python_files=tuple(python_files),
        readme_files=tuple(readme_files),
        requirements_files=tuple(requirements_files),
        pyproject_files=tuple(pyproject_files),
        env_templates=tuple(env_templates),
        data_files=tuple(data_files),
        image_files=tuple(image_files),
    )


def collect_tutorial_inventory(root: Path) -> list[TutorialInventory]:
    root = root.resolve()
    inventories: list[TutorialInventory] = []
    if has_tutorial_marker(root):
        inventories.append(classify_tutorial_dir(root))
    for path in iter_candidate_dirs(root):
        if has_tutorial_marker(path):
            inventories.append(classify_tutorial_dir(path))
    return inventories


def summarize_tutorials(inventories: Iterable[TutorialInventory]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for inventory in inventories:
        counter["tutorials"] += 1
        counter[f"kind:{inventory.kind}"] += 1
        counter["notebooks"] += len(inventory.notebooks)
        counter["python_files"] += len(inventory.python_files)
        counter["data_files"] += len(inventory.data_files)
        if inventory.has_readme:
            counter["with_readme"] += 1
        if inventory.has_dependencies:
            counter["with_dependencies"] += 1
        if inventory.env_templates:
            counter["with_env_template"] += 1
    return dict(counter)


def find_inventory_findings(
    inventories: Iterable[TutorialInventory],
) -> list[Finding]:
    findings: list[Finding] = []
    for inventory in inventories:
        if inventory.has_executable_content and not inventory.has_readme:
            findings.append(
                Finding(
                    inventory.path,
                    "missing-readme",
                    "tutorial directory has executable content but no README",
                )
            )
        if inventory.python_files and not inventory.has_dependencies:
            findings.append(
                Finding(
                    inventory.path,
                    "missing-dependencies",
                    "python tutorial has no requirements.txt or pyproject.toml",
                )
            )
        if inventory.python_files and not inventory.has_entrypoint:
            findings.append(
                Finding(
                    inventory.path,
                    "missing-entrypoint",
                    "python tutorial has no obvious agent/app/client/main/server entrypoint",
                )
            )
        if inventory.env_templates and not inventory.has_readme:
            findings.append(
                Finding(
                    inventory.path,
                    "undocumented-env-template",
                    "environment template is not documented by a nearby README",
                )
            )
    return findings
