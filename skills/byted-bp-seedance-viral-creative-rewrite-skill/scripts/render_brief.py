#!/usr/bin/env python3
# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
"""Render the canonical prepared-brief frontstage response."""

from __future__ import annotations

import argparse
from pathlib import Path

from schemas import PreparedRewrite
from services import _print_compact_decision_brief, normalize_prepared_for_generation


def print_compact_brief(prepared: PreparedRewrite) -> None:
    prepared = normalize_prepared_for_generation(prepared)
    _print_compact_decision_brief(prepared, language=prepared.request.ui_language)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the compact prepared brief for review.")
    parser.add_argument("--prepared-input-json", required=True, help="Prepared JSON path")
    parser.add_argument("--show-full-prompt", action="store_true", help="Also print the full generation prompt")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prepared_path = Path(args.prepared_input_json).expanduser().resolve()
    prepared = normalize_prepared_for_generation(PreparedRewrite.model_validate_json(prepared_path.read_text(encoding="utf-8")))
    print_compact_brief(prepared)
    if args.show_full_prompt:
        title = "Full generation prompt" if prepared.request.ui_language == "en" else "完整生成提示词"
        print(f"\n{title}")
        print(prepared.prompt_preview.full_prompt)


if __name__ == "__main__":
    main()
