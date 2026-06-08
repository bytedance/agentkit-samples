# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from .exporter import write_outputs
from .modeler import build_sli_specs


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build structured SLI specs")
    p.add_argument("--input", required=True, help="Path to capability text file")
    p.add_argument("--owner", required=True, help="Owner of the SLI")
    p.add_argument("--reference", action="append", default=[], help="Optional reference files")
    p.add_argument("--out-dir", default="output")
    return p


def run_cli(argv: List[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    input_path = Path(args.input)
    if not input_path.exists() or input_path.is_dir():
        raise SystemExit(f"input file not found: {input_path}")

    text = input_path.read_text(encoding="utf-8")
    result = build_sli_specs(text, owner=args.owner, reference_paths=args.reference)
    output_dir = write_outputs(result, out_base_dir=args.out_dir)

    report = {
        "output_dir": output_dir,
        "total_specs": len(result.specs),
        "notes": result.notes,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
