# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from .exporter import write_outputs
from .pipeline import run_pipeline


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Extract architecture topology and paths")
    p.add_argument("--repo", required=True, help="Repository path")
    p.add_argument("--product-doc", action="append", default=[], help="Product document path")
    p.add_argument("--arch-diagram", action="append", default=[], help="Architecture diagram path")
    p.add_argument("--out-dir", default="output")
    p.add_argument("--focus-service")
    p.add_argument("--offline", action="store_true")
    return p


def run_cli(argv: List[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_path = Path(args.repo)
    if not repo_path.exists() or not repo_path.is_dir():
        raise SystemExit(f"repo path not found: {repo_path}")

    model = run_pipeline(
        repo=str(repo_path),
        product_docs=args.product_doc,
        arch_diagrams=args.arch_diagram,
    )

    outdir = write_outputs(model=model, out_base_dir=args.out_dir, repo_slug=repo_path.name)
    report = {
        "output_dir": outdir,
        "service_nodes": len(model.service_graph.get("nodes", [])),
        "request_paths": len(model.request_paths),
        "async_paths": len(model.async_paths),
        "failure_points": len(model.failure_points),
        "observability_gaps": len(model.observability_hook_points),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
