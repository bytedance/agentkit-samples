from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

try:
    from .models import Finding
except ImportError:  # pragma: no cover - supports direct script execution
    from models import Finding


ENV_TEMPLATE_NAMES = {".env.example", ".env.template"}
KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SAFE_PLACEHOLDERS = {
    "",
    "<your-access-key>",
    "<your-api-key>",
    "<your-app-id>",
    "<your-app-secret>",
    "<your-client-id>",
    "<your-client-secret>",
    "<your-secret-key>",
    "<your-token>",
    "change-me",
    "changeme",
    "example",
    "replace-me",
    "todo",
    "xxx",
    "your-access-key",
    "your-api-key",
    "your-app-id",
    "your-app-secret",
    "your-client-id",
    "your-client-secret",
    "your-secret-key",
    "your-token",
}
SENSITIVE_KEY_HINTS = (
    "ACCESS_KEY",
    "API_KEY",
    "APP_SECRET",
    "CLIENT_SECRET",
    "PASSWORD",
    "SECRET",
    "TOKEN",
)


def strip_export_prefix(line: str) -> str:
    stripped = line.lstrip()
    if stripped.startswith("export "):
        return stripped[len("export ") :].lstrip()
    return stripped


def strip_env_value_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def split_env_assignment(line: str) -> tuple[str, str] | None:
    stripped = strip_export_prefix(line)
    if not stripped.strip() or stripped.lstrip().startswith("#"):
        return None
    if "=" not in stripped:
        return stripped.strip(), ""
    key, value = stripped.split("=", 1)
    return key.strip(), strip_env_value_quotes(value)


def is_sensitive_key(key: str) -> bool:
    upper_key = key.upper()
    return any(hint in upper_key for hint in SENSITIVE_KEY_HINTS)


def is_safe_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in SAFE_PLACEHOLDERS:
        return True
    if normalized.startswith("${") and normalized.endswith("}"):
        return True
    if normalized.startswith("<") and normalized.endswith(">"):
        return True
    return False


def looks_like_real_secret(value: str) -> bool:
    if is_safe_placeholder(value):
        return False
    if len(value.strip()) < 8:
        return False
    if " " in value.strip():
        return False
    return True


def audit_env_template(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [Finding(path, "read-error", str(exc), severity="error")]

    seen: dict[str, int] = {}
    assigned_keys = 0
    for line_number, raw_line in enumerate(lines, start=1):
        assignment = split_env_assignment(raw_line)
        if assignment is None:
            continue
        key, value = assignment
        if not key:
            findings.append(
                Finding(path, "empty-env-key", "environment key is empty", line_number=line_number)
            )
            continue
        if not KEY_PATTERN.match(key):
            findings.append(
                Finding(
                    path,
                    "invalid-env-key",
                    f"{key!r} is not a portable environment variable name",
                    line_number=line_number,
                )
            )
        if key in seen:
            findings.append(
                Finding(
                    path,
                    "duplicate-env-key",
                    f"{key!r} also appears on line {seen[key]}",
                    line_number=line_number,
                )
            )
        else:
            seen[key] = line_number

        assigned_keys += 1
        if is_sensitive_key(key) and looks_like_real_secret(value):
            findings.append(
                Finding(
                    path,
                    "secret-like-env-value",
                    f"{key!r} has a non-placeholder value",
                    severity="error",
                    line_number=line_number,
                )
            )
        if value and value != value.strip():
            findings.append(
                Finding(
                    path,
                    "env-value-whitespace",
                    f"{key!r} value has leading or trailing whitespace",
                    line_number=line_number,
                )
            )

    if assigned_keys == 0:
        findings.append(
            Finding(path, "empty-env-template", "environment template has no assignments")
        )
    return findings


def collect_env_templates(root: Path) -> list[Path]:
    templates: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name in ENV_TEMPLATE_NAMES:
            templates.append(path)
    return templates


def collect_env_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for template in collect_env_templates(root):
        findings.extend(audit_env_template(template))
    return findings


def summarize_env_templates(root: Path) -> dict[str, object]:
    templates = collect_env_templates(root)
    key_to_files: dict[str, list[str]] = defaultdict(list)
    template_summaries: list[dict[str, object]] = []
    for template in templates:
        keys: list[str] = []
        for line in template.read_text(encoding="utf-8").splitlines():
            assignment = split_env_assignment(line)
            if assignment is None:
                continue
            key, _ = assignment
            if key:
                keys.append(key)
                key_to_files[key].append(str(template.relative_to(root)))
        template_summaries.append(
            {
                "path": str(template.relative_to(root)),
                "key_count": len(keys),
                "keys": keys,
            }
        )

    shared_keys = {
        key: files for key, files in sorted(key_to_files.items()) if len(files) > 1
    }
    return {
        "template_count": len(templates),
        "templates": template_summaries,
        "shared_keys": shared_keys,
    }
