from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Finding:
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
        if self.line_number is None:
            return str(path)
        return f"{path}:{self.line_number}"

    def format(self, root: Path) -> str:
        return f"{self.severity.upper()} {self.relative_path(root)} [{self.code}] {self.message}"

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        payload = asdict(self)
        payload["path"] = self.relative_path(root) if root else str(self.path)
        return payload


@dataclass(frozen=True)
class TutorialInventory:
    path: Path
    notebooks: tuple[Path, ...] = field(default_factory=tuple)
    python_files: tuple[Path, ...] = field(default_factory=tuple)
    readme_files: tuple[Path, ...] = field(default_factory=tuple)
    requirements_files: tuple[Path, ...] = field(default_factory=tuple)
    pyproject_files: tuple[Path, ...] = field(default_factory=tuple)
    env_templates: tuple[Path, ...] = field(default_factory=tuple)
    data_files: tuple[Path, ...] = field(default_factory=tuple)
    image_files: tuple[Path, ...] = field(default_factory=tuple)

    @property
    def has_readme(self) -> bool:
        return bool(self.readme_files)

    @property
    def has_dependencies(self) -> bool:
        return bool(self.requirements_files or self.pyproject_files)

    @property
    def has_executable_content(self) -> bool:
        return bool(self.notebooks or self.python_files)

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
    def kind(self) -> str:
        if self.notebooks and self.python_files:
            return "mixed"
        if self.notebooks:
            return "notebook"
        if self.python_files:
            return "python"
        return "resource"

    def to_dict(self, root: Path | None = None) -> dict[str, Any]:
        def render_paths(paths: tuple[Path, ...]) -> list[str]:
            rendered: list[str] = []
            for path in paths:
                if root is not None:
                    try:
                        rendered.append(str(path.relative_to(root)))
                        continue
                    except ValueError:
                        pass
                rendered.append(str(path))
            return rendered

        path = self.path
        if root is not None:
            try:
                path = self.path.relative_to(root)
            except ValueError:
                path = self.path
        return {
            "path": str(path),
            "kind": self.kind,
            "has_readme": self.has_readme,
            "has_dependencies": self.has_dependencies,
            "has_entrypoint": self.has_entrypoint,
            "notebooks": render_paths(self.notebooks),
            "python_files": render_paths(self.python_files),
            "readme_files": render_paths(self.readme_files),
            "requirements_files": render_paths(self.requirements_files),
            "pyproject_files": render_paths(self.pyproject_files),
            "env_templates": render_paths(self.env_templates),
            "data_files": render_paths(self.data_files),
            "image_files": render_paths(self.image_files),
        }
