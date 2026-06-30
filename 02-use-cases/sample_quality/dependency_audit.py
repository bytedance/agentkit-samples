from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

try:
    from .models import Finding, RequirementEntry
except ImportError:  # pragma: no cover - supports direct script execution
    from models import Finding, RequirementEntry


SPECIFIER_PATTERN = re.compile(r"(===|==|~=|!=|<=|>=|<|>)")
EXTERNAL_PREFIXES = ("git+", "http://", "https://", "-e ")
STANDARD_LIBRARY_HINTS = {
    "asyncio",
    "collections",
    "contextlib",
    "dataclasses",
    "datetime",
    "functools",
    "hashlib",
    "itertools",
    "json",
    "logging",
    "os",
    "pathlib",
    "re",
    "sys",
    "time",
    "typing",
    "urllib",
    "uuid",
}


def strip_inline_comment(line: str) -> str:
    in_single = False
    in_double = False
    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            return line[:index].strip()
    return line.strip()


def normalize_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def split_requirement(line: str) -> tuple[str, str]:
    cleaned = strip_inline_comment(line)
    if cleaned.startswith("-e "):
        cleaned = cleaned[3:].strip()
    if cleaned.startswith(("git+", "http://", "https://")):
        return cleaned, ""

    match = SPECIFIER_PATTERN.search(cleaned)
    if match:
        return cleaned[: match.start()].strip(), cleaned[match.start() :].strip()
    return cleaned.strip(), ""


def parse_requirements(path: Path) -> list[RequirementEntry]:
    entries: list[RequirementEntry] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = strip_inline_comment(raw_line)
        if not stripped or stripped.startswith(("-r ", "--")):
            continue
        name, specifier = split_requirement(stripped)
        entries.append(
            RequirementEntry(
                path=path,
                line_number=line_number,
                raw=stripped,
                name=normalize_name(name),
                specifier=specifier,
                is_editable=stripped.startswith("-e "),
                is_external_url=stripped.startswith(EXTERNAL_PREFIXES),
            )
        )
    return entries


def audit_requirements_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        entries = parse_requirements(path)
    except OSError as exc:
        return [Finding(path, "read-error", str(exc), severity="error")]

    if not entries:
        return [Finding(path, "empty-requirements", "requirements.txt is empty")]

    by_name: dict[str, list[RequirementEntry]] = defaultdict(list)
    for entry in entries:
        by_name[entry.name].append(entry)
        if not entry.specifier and not entry.is_external_url:
            findings.append(
                Finding(
                    path,
                    "unpinned-dependency",
                    f"{entry.raw!r} has no version specifier",
                    line_number=entry.line_number,
                )
            )
        if entry.is_external_url:
            findings.append(
                Finding(
                    path,
                    "external-dependency",
                    "dependency is installed from a URL or editable source",
                    line_number=entry.line_number,
                )
            )
        if entry.name in STANDARD_LIBRARY_HINTS:
            findings.append(
                Finding(
                    path,
                    "stdlib-dependency",
                    f"{entry.name!r} looks like a Python standard-library module",
                    line_number=entry.line_number,
                )
            )

    for name, duplicates in by_name.items():
        if len(duplicates) <= 1:
            continue
        first = duplicates[0]
        for duplicate in duplicates[1:]:
            findings.append(
                Finding(
                    path,
                    "duplicate-dependency",
                    f"{name!r} also appears on line {first.line_number}",
                    line_number=duplicate.line_number,
                )
            )
    return findings


def collect_dependency_issues(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for requirements_file in sorted(root.rglob("requirements.txt")):
        if any(part in {"__pycache__", ".pytest_cache"} for part in requirements_file.parts):
            continue
        findings.extend(audit_requirements_file(requirements_file))
    return findings
