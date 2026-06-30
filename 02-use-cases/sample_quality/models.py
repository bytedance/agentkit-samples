from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Finding:
    """A structured issue found while scanning a sample."""

    path: Path
    code: str
    message: str
    severity: str = "warning"
    line_number: int | None = None

    def relative_path(self, root: Path) -> str:
        try:
            path = self.path.relative_to(root)
        except ValueError:
            path = self.path
        if self.line_number is not None:
            return f"{path}:{self.line_number}"
        return str(path)

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        payload = asdict(self)
        payload["path"] = self.relative_path(root) if root else str(self.path)
        return payload

    def format(self, root: Path) -> str:
        location = self.relative_path(root)
        return f"{self.severity.upper()} {location} [{self.code}] {self.message}"


@dataclass(frozen=True)
class RequirementEntry:
    """A parsed line from a requirements.txt file."""

    path: Path
    line_number: int
    raw: str
    name: str
    specifier: str
    is_editable: bool = False
    is_external_url: bool = False

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        path = self.path
        if root is not None:
            try:
                path = self.path.relative_to(root)
            except ValueError:
                path = self.path
        return {
            "path": str(path),
            "line_number": self.line_number,
            "raw": self.raw,
            "name": self.name,
            "specifier": self.specifier,
            "is_editable": self.is_editable,
            "is_external_url": self.is_external_url,
        }


@dataclass(frozen=True)
class SampleInventory:
    """File-level inventory for one sample directory."""

    path: Path
    python_files: tuple[Path, ...] = field(default_factory=tuple)
    readme_files: tuple[Path, ...] = field(default_factory=tuple)
    requirements_files: tuple[Path, ...] = field(default_factory=tuple)
    pyproject_files: tuple[Path, ...] = field(default_factory=tuple)
    env_templates: tuple[Path, ...] = field(default_factory=tuple)
    image_files: tuple[Path, ...] = field(default_factory=tuple)
    notebook_files: tuple[Path, ...] = field(default_factory=tuple)
    yaml_files: tuple[Path, ...] = field(default_factory=tuple)

    @property
    def has_python(self) -> bool:
        return bool(self.python_files)

    @property
    def has_dependency_file(self) -> bool:
        return bool(self.requirements_files or self.pyproject_files)

    @property
    def has_readme(self) -> bool:
        return bool(self.readme_files)

    @property
    def has_notebook(self) -> bool:
        return bool(self.notebook_files)

    @property
    def has_entrypoint(self) -> bool:
        entry_names = {
            "agent.py",
            "app.py",
            "client.py",
            "main.py",
            "server.py",
        }
        return any(path.name in entry_names for path in self.python_files)

    @property
    def primary_kind(self) -> str:
        if self.has_python and self.has_notebook:
            return "hybrid"
        if self.has_python:
            return "python"
        if self.has_notebook:
            return "notebook"
        return "asset"

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        def paths(values: tuple[Path, ...]) -> list[str]:
            output: list[str] = []
            for value in values:
                if root is not None:
                    try:
                        output.append(str(value.relative_to(root)))
                        continue
                    except ValueError:
                        pass
                output.append(str(value))
            return output

        path = self.path
        if root is not None:
            try:
                path = self.path.relative_to(root)
            except ValueError:
                path = self.path

        return {
            "path": str(path),
            "kind": self.primary_kind,
            "has_readme": self.has_readme,
            "has_dependency_file": self.has_dependency_file,
            "has_entrypoint": self.has_entrypoint,
            "python_files": paths(self.python_files),
            "readme_files": paths(self.readme_files),
            "requirements_files": paths(self.requirements_files),
            "pyproject_files": paths(self.pyproject_files),
            "env_templates": paths(self.env_templates),
            "image_files": paths(self.image_files),
            "notebook_files": paths(self.notebook_files),
            "yaml_files": paths(self.yaml_files),
        }
