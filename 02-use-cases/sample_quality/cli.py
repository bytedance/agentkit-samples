from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from dependency_audit import collect_dependency_issues
from inventory import collect_sample_inventory, find_inventory_issues, summarize_inventory


def default_use_cases_root() -> Path:
    return Path(__file__).resolve().parents[1]


def print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def command_inventory(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    inventories = collect_sample_inventory(root)
    if args.format == "json":
        print_json(
            {
                "root": str(root),
                "summary": summarize_inventory(inventories),
                "samples": [inventory.to_dict(root) for inventory in inventories],
            }
        )
    else:
        summary = summarize_inventory(inventories)
        print(f"Root: {root}")
        print(f"Samples: {summary.get('samples', 0)}")
        print(f"Python files: {summary.get('python_files', 0)}")
        print(f"Notebook files: {summary.get('notebook_files', 0)}")
        for inventory in inventories:
            rel = inventory.path.relative_to(root)
            markers = []
            if inventory.has_readme:
                markers.append("readme")
            if inventory.has_dependency_file:
                markers.append("deps")
            if inventory.has_entrypoint:
                markers.append("entry")
            print(f"- {rel} ({inventory.primary_kind}; {', '.join(markers) or 'no markers'})")
    return 0


def command_check(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    inventories = collect_sample_inventory(root)
    findings = []
    findings.extend(find_inventory_issues(inventories))
    findings.extend(collect_dependency_issues(root))

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
            print("No sample quality issues found.")
    return 1 if findings and args.strict else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit 02-use-cases sample projects.")
    parser.add_argument(
        "--root",
        type=Path,
        default=default_use_cases_root(),
        help="Path to the 02-use-cases directory.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("inventory", help="Print sample inventory.").set_defaults(
        func=command_inventory
    )
    check_parser = subparsers.add_parser("check", help="Print sample quality findings.")
    check_parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with status 1 when findings are present.",
    )
    check_parser.set_defaults(func=command_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
