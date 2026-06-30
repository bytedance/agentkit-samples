from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable

try:
    from .models import Finding, SampleInventory
except ImportError:  # pragma: no cover - supports direct script execution
    from models import Finding, SampleInventory


IGNORED_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "assets",
    "img",
    "images",
    "node_modules",
    "pre_build",
    "tests",
}
IMAGE_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
YAML_SUFFIXES = {".yaml", ".yml"}
SAMPLE_MARKERS = {
    ".env.example",
    ".env.template",
    "agent.py",
    "agent.yaml",
    "app.py",
    "client.py",
    "main.py",
    "pyproject.toml",
    "requirements.txt",
    "server.py",
}


def is_ignored(path: Path) -> bool:
    return any(part in IGNORED_DIR_NAMES for part in path.parts)


def iter_candidate_directories(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_dir():
            continue
        if is_ignored(path.relative_to(root)):
            continue
        yield path


def contains_sample_marker(path: Path) -> bool:
    for child in path.iterdir():
        if not child.is_file():
            continue
        if child.name in SAMPLE_MARKERS:
            return True
        if child.suffix == ".ipynb":
            return True
    return False


def classify_files(path: Path) -> SampleInventory:
    python_files: list[Path] = []
    readme_files: list[Path] = []
    requirements_files: list[Path] = []
    pyproject_files: list[Path] = []
    env_templates: list[Path] = []
    image_files: list[Path] = []
    notebook_files: list[Path] = []
    yaml_files: list[Path] = []

    for child in sorted(path.iterdir()):
        if not child.is_file():
            continue
        name_lower = child.name.lower()
        suffix = child.suffix.lower()
        if suffix == ".py":
            python_files.append(child)
        elif name_lower.startswith("readme") and suffix == ".md":
            readme_files.append(child)
        elif child.name == "requirements.txt":
            requirements_files.append(child)
        elif child.name == "pyproject.toml":
            pyproject_files.append(child)
        elif child.name in {".env.example", ".env.template"}:
            env_templates.append(child)
        elif suffix in IMAGE_SUFFIXES:
            image_files.append(child)
        elif suffix == ".ipynb":
            notebook_files.append(child)
        elif suffix in YAML_SUFFIXES:
            yaml_files.append(child)

    return SampleInventory(
        path=path,
        python_files=tuple(python_files),
        readme_files=tuple(readme_files),
        requirements_files=tuple(requirements_files),
        pyproject_files=tuple(pyproject_files),
        env_templates=tuple(env_templates),
        image_files=tuple(image_files),
        notebook_files=tuple(notebook_files),
        yaml_files=tuple(yaml_files),
    )


def collect_sample_inventory(root: Path) -> list[SampleInventory]:
    """Collect sample directories under a use-cases root."""
    root = root.resolve()
    inventories: list[SampleInventory] = []
    for path in iter_candidate_directories(root):
        if contains_sample_marker(path):
            inventories.append(classify_files(path))
    return inventories


def summarize_inventory(inventories: Iterable[SampleInventory]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for inventory in inventories:
        counter["samples"] += 1
        counter[f"kind:{inventory.primary_kind}"] += 1
        if inventory.has_readme:
            counter["with_readme"] += 1
        if inventory.has_dependency_file:
            counter["with_dependency_file"] += 1
        if inventory.has_entrypoint:
            counter["with_entrypoint"] += 1
        if inventory.env_templates:
            counter["with_env_template"] += 1
        counter["python_files"] += len(inventory.python_files)
        counter["notebook_files"] += len(inventory.notebook_files)
    return dict(counter)


def find_inventory_issues(inventories: Iterable[SampleInventory]) -> list[Finding]:
    findings: list[Finding] = []
    for inventory in inventories:
        if inventory.has_python and not inventory.has_entrypoint:
            findings.append(
                Finding(
                    inventory.path,
                    "missing-entrypoint",
                    "python sample has no agent.py, app.py, client.py, main.py, or server.py",
                )
            )
        if (inventory.has_python or inventory.has_notebook) and not inventory.has_readme:
            findings.append(
                Finding(
                    inventory.path,
                    "missing-readme",
                    "sample has runnable content but no README file",
                )
            )
        if inventory.has_python and not inventory.has_dependency_file:
            findings.append(
                Finding(
                    inventory.path,
                    "missing-dependencies",
                    "python sample has no requirements.txt or pyproject.toml",
                )
            )
        if inventory.env_templates and not inventory.has_readme:
            findings.append(
                Finding(
                    inventory.path,
                    "undocumented-env",
                    "environment template exists but there is no README next to it",
                )
            )
    return findings
