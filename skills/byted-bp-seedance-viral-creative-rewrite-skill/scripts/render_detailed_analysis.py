#!/usr/bin/env python3
# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
"""Render the canonical detailed-analysis frontstage response."""

from __future__ import annotations

import argparse
from pathlib import Path

from schemas import PreparedRewrite
from services import normalize_prepared_for_generation, print_analysis_details


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render full detailed analysis for a prepared creative rewrite brief.")
    parser.add_argument("--prepared-input-json", required=True, help="Prepared JSON path")
    parser.add_argument("--show-full-prompt", action="store_true", help="Also print the full generation prompt")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prepared_path = Path(args.prepared_input_json).expanduser().resolve()
    prepared = normalize_prepared_for_generation(PreparedRewrite.model_validate_json(prepared_path.read_text(encoding="utf-8")))
    print_analysis_details(prepared, show_full_prompt=args.show_full_prompt)


if __name__ == "__main__":
    main()
