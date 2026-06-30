from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

try:
    from .models import Finding
except ImportError:  # pragma: no cover - supports direct script execution
    from models import Finding


SPECIFIER_PATTERN = re.compile(r"(===|==|~=|!=|<=|>=|<|>)")
EXTERNAL_PREFIXES = ("git+", "http://", "https://", "-e ")


def strip_inline_comment(line: str) -> str:
    in_single = False
    in_double = False
    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif (
            char == "#"
            and not in_single
            and not in_double
            and (index == 0 or line[index - 1].isspace())
        ):
            return line[:index].strip()
    return line.strip()


def split_requirement(line: str) -> tuple[str, str]:
    cleaned = strip_inline_comment(line)
    if cleaned.startswith("-e "):
        cleaned = cleaned[3:].strip()
    if cleaned.startswith(("git+", "http://", "https://")):
        return cleaned, ""
    match = SPECIFIER_PATTERN.search(cleaned)
    if match:
        return cleaned[: match.start()].strip(), cleaned[match.start() :].strip()
    return cleaned, ""


def normalize_requirement_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def meaningful_requirement_lines(path: Path) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = strip_inline_comment(raw)
        if not line or line.startswith(("-r ", "--")):
            continue
        lines.append((number, line))
    return lines


def audit_requirements(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        lines = meaningful_requirement_lines(path)
    except OSError as exc:
        return [Finding(path, "read-error", str(exc), severity="error")]

    if not lines:
        return [Finding(path, "empty-requirements", "requirements.txt is empty")]

    seen: dict[str, list[int]] = defaultdict(list)
    for line_number, line in lines:
        name, specifier = split_requirement(line)
        normalized_name = normalize_requirement_name(name)
        seen[normalized_name].append(line_number)
        if line.startswith(EXTERNAL_PREFIXES):
            findings.append(
                Finding(
                    path,
                    "external-dependency",
                    "dependency uses an external source",
                    line_number=line_number,
                )
            )
        if not specifier and not line.startswith(EXTERNAL_PREFIXES):
            findings.append(
                Finding(
                    path,
                    "unpinned-dependency",
                    f"{line!r} has no version constraint",
                    line_number=line_number,
                )
            )

    for name, line_numbers in seen.items():
        if len(line_numbers) <= 1:
            continue
        first_line = line_numbers[0]
        for duplicate_line in line_numbers[1:]:
            findings.append(
                Finding(
                    path,
                    "duplicate-dependency",
                    f"{name!r} also appears on line {first_line}",
                    line_number=duplicate_line,
                )
            )
    return findings


def collect_requirements_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for requirements_file in sorted(root.rglob("requirements.txt")):
        if "__pycache__" in requirements_file.parts:
            continue
        findings.extend(audit_requirements(requirements_file))
    return findings
