# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from .pipeline import PipelineOptions, run_pipeline


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Dashboard IA, panel specs, and Grafana JSON")
    parser.add_argument("--sli-model", required=True, help="Path to SLI model JSON or directory")
    parser.add_argument("--arch-model", required=True, help="Path to architecture model directory")
    parser.add_argument("--repo", required=True, help="Path to source repository")
    parser.add_argument("--out-dir", default="output", help="Output base directory")
    parser.add_argument("--dashboard-title", help="Optional dashboard title override")
    parser.add_argument("--focus-service", help="Optional focus service")
    parser.add_argument("--offline", action="store_true", help="Use local inputs only")
    return parser


def run_cli(argv: List[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    sli_model = Path(args.sli_model)
    arch_model = Path(args.arch_model)
    repo = Path(args.repo)

    if not sli_model.exists():
        raise SystemExit(f"sli model path not found: {sli_model}")
    if not arch_model.exists() or not arch_model.is_dir():
        raise SystemExit(f"arch model directory not found: {arch_model}")
    if not repo.exists() or not repo.is_dir():
        raise SystemExit(f"repo path not found: {repo}")

    result = run_pipeline(
        sli_model=str(sli_model),
        arch_model=str(arch_model),
        repo=str(repo),
        options=PipelineOptions(
            out_dir=args.out_dir,
            dashboard_title=args.dashboard_title,
            focus_service=args.focus_service,
            offline=args.offline,
        ),
    )

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
