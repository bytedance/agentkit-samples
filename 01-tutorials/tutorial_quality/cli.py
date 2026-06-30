from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from env_audit import collect_env_findings
from inventory import collect_tutorial_inventory, find_inventory_findings, summarize_tutorials
from notebook_audit import collect_notebook_findings
from report import render_markdown_report
from requirements_audit import collect_requirements_findings


def default_tutorial_root() -> Path:
    return Path(__file__).resolve().parents[1]


def print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def command_inventory(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    inventories = collect_tutorial_inventory(root)
    summary = summarize_tutorials(inventories)

    if args.format == "json":
        print_json(
            {
                "root": str(root),
                "summary": summary,
                "tutorials": [inventory.to_dict(root) for inventory in inventories],
            }
        )
        return 0

    print(f"Root: {root}")
    print(f"Tutorial directories: {summary.get('tutorials', 0)}")
    print(f"Notebook files: {summary.get('notebooks', 0)}")
    print(f"Python files: {summary.get('python_files', 0)}")
    for inventory in inventories:
        markers = []
        if inventory.has_readme:
            markers.append("readme")
        if inventory.has_dependencies:
            markers.append("deps")
        if inventory.has_entrypoint:
            markers.append("entry")
        marker_text = ", ".join(markers) if markers else "no markers"
        print(f"- {inventory.path.relative_to(root)} ({inventory.kind}; {marker_text})")
    return 0


def command_check(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    inventories = collect_tutorial_inventory(root)
    findings = []
    findings.extend(find_inventory_findings(inventories))
    findings.extend(collect_env_findings(root))
    findings.extend(collect_requirements_findings(root))
    findings.extend(
        collect_notebook_findings(root, max_output_chars=args.max_output_chars)
    )

    if args.format == "json":
        print_json(
            {
                "root": str(root),
                "finding_count": len(findings),
                "findings": [finding.to_dict(root) for finding in findings],
            }
        )
    else:
        for finding in findings:
            print(finding.format(root))
        if not findings:
            print("No tutorial quality issues found.")
    return 1 if findings and args.strict else 0


def collect_all_findings(root: Path, max_output_chars: int) -> list[object]:
    inventories = collect_tutorial_inventory(root)
    findings = []
    findings.extend(find_inventory_findings(inventories))
    findings.extend(collect_env_findings(root))
    findings.extend(collect_requirements_findings(root))
    findings.extend(collect_notebook_findings(root, max_output_chars=max_output_chars))
    return findings


def command_report(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    inventories = collect_tutorial_inventory(root)
    findings = collect_all_findings(root, args.max_output_chars)
    report = render_markdown_report(
        root=root,
        inventories=inventories,
        inventory_summary=summarize_tutorials(inventories),
        findings=findings,
    )
    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(f"Wrote tutorial quality report to {args.output}")
    else:
        print(report, end="")
    return 1 if findings and args.strict else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit 01-tutorials assets and samples.")
    parser.add_argument(
        "--root",
        type=Path,
        default=default_tutorial_root(),
        help="Path to the 01-tutorials directory.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("inventory", help="Print tutorial inventory.").set_defaults(
        func=command_inventory
    )
    check_parser = subparsers.add_parser("check", help="Print tutorial quality findings.")
    check_parser.add_argument(
        "--max-output-chars",
        type=int,
        default=20_000,
        help="Maximum allowed notebook output size per cell.",
    )
    check_parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with status 1 when findings are present.",
    )
    check_parser.set_defaults(func=command_check)

    report_parser = subparsers.add_parser(
        "report",
        help="Render a Markdown quality report.",
    )
    report_parser.add_argument(
        "--max-output-chars",
        type=int,
        default=20_000,
        help="Maximum allowed notebook output size per cell.",
    )
    report_parser.add_argument(
        "--output",
        type=Path,
        help="Optional output Markdown file.",
    )
    report_parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with status 1 when findings are present.",
    )
    report_parser.set_defaults(func=command_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
