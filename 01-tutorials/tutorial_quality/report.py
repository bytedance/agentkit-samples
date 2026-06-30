from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

try:
    from .env_audit import summarize_env_templates
    from .models import Finding, TutorialInventory
except ImportError:  # pragma: no cover - supports direct script execution
    from env_audit import summarize_env_templates
    from models import Finding, TutorialInventory


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    rendered = []
    rendered.append("| " + " | ".join(headers) + " |")
    rendered.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        rendered.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(rendered)


def finding_summary(findings: list[Finding]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for finding in findings:
        counter[f"severity:{finding.severity}"] += 1
        counter[f"code:{finding.code}"] += 1
    counter["total"] = len(findings)
    return dict(counter)


def group_findings_by_code(findings: list[Finding]) -> dict[str, list[Finding]]:
    grouped: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        grouped[finding.code].append(finding)
    return dict(sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])))


def render_inventory_section(
    root: Path,
    inventories: list[TutorialInventory],
    summary: dict[str, int],
) -> str:
    rows = [
        ["Tutorial directories", summary.get("tutorials", 0)],
        ["Notebook files", summary.get("notebooks", 0)],
        ["Python files", summary.get("python_files", 0)],
        ["Data files", summary.get("data_files", 0)],
        ["With README", summary.get("with_readme", 0)],
        ["With dependencies", summary.get("with_dependencies", 0)],
        ["With env template", summary.get("with_env_template", 0)],
    ]
    lines = ["## Inventory", "", markdown_table(["Metric", "Value"], rows), ""]

    tutorial_rows: list[list[object]] = []
    for inventory in inventories:
        markers = []
        if inventory.has_readme:
            markers.append("README")
        if inventory.has_dependencies:
            markers.append("deps")
        if inventory.has_entrypoint:
            markers.append("entry")
        tutorial_rows.append(
            [
                inventory.path.relative_to(root),
                inventory.kind,
                len(inventory.notebooks),
                len(inventory.python_files),
                ", ".join(markers) if markers else "-",
            ]
        )
    lines.extend(
        [
            "### Tutorial Directories",
            "",
            markdown_table(
                ["Path", "Kind", "Notebooks", "Python files", "Markers"],
                tutorial_rows,
            ),
            "",
        ]
    )
    return "\n".join(lines)


def render_findings_section(root: Path, findings: list[Finding]) -> str:
    if not findings:
        return "## Findings\n\nNo tutorial quality findings.\n"

    summary = finding_summary(findings)
    severity_rows = [
        ["Error", summary.get("severity:error", 0)],
        ["Warning", summary.get("severity:warning", 0)],
        ["Info", summary.get("severity:info", 0)],
        ["Total", summary.get("total", 0)],
    ]
    lines = ["## Findings", "", markdown_table(["Severity", "Count"], severity_rows), ""]

    grouped = group_findings_by_code(findings)
    code_rows = [[code, len(items)] for code, items in grouped.items()]
    lines.extend(["### By Code", "", markdown_table(["Code", "Count"], code_rows), ""])

    lines.extend(["### Details", ""])
    for code, items in grouped.items():
        lines.append(f"#### {code}")
        lines.append("")
        for finding in items[:20]:
            lines.append(f"- `{finding.relative_path(root)}`: {finding.message}")
        if len(items) > 20:
            lines.append(f"- ... {len(items) - 20} more")
        lines.append("")
    return "\n".join(lines)


def render_env_section(root: Path) -> str:
    summary = summarize_env_templates(root)
    rows = []
    for template in summary["templates"]:
        rows.append(
            [
                template["path"],
                template["key_count"],
                ", ".join(template["keys"]) if template["keys"] else "-",
            ]
        )
    if not rows:
        return "## Environment Templates\n\nNo environment templates found.\n"

    lines = [
        "## Environment Templates",
        "",
        markdown_table(["Path", "Keys", "Names"], rows),
        "",
    ]
    shared_keys = summary["shared_keys"]
    if shared_keys:
        lines.extend(["### Shared Keys", ""])
        for key, files in shared_keys.items():
            lines.append(f"- `{key}`: {', '.join(files)}")
        lines.append("")
    return "\n".join(lines)


def render_markdown_report(
    *,
    root: Path,
    inventories: list[TutorialInventory],
    inventory_summary: dict[str, int],
    findings: list[Finding],
) -> str:
    sections = [
        "# Tutorial Quality Report",
        "",
        f"Root: `{root}`",
        "",
        render_inventory_section(root, inventories, inventory_summary),
        render_env_section(root),
        render_findings_section(root, findings),
    ]
    return "\n".join(sections).rstrip() + "\n"
