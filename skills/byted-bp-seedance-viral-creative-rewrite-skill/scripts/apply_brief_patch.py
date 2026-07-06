#!/usr/bin/env python3
# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
"""Apply a small brief patch and render the refreshed brief."""

from __future__ import annotations

import argparse
from pathlib import Path

from render_brief import print_compact_brief
from run_rewrite_video import apply_prepared_patch, write_json
from schemas import PreparedRewrite


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch a prepared brief without media re-analysis, then render the refreshed brief.")
    parser.add_argument("--prepared-input-json", required=True, help="Prepared JSON path")
    parser.add_argument("--patch-json", required=True, help="Patch JSON path")
    parser.add_argument("--prepared-json", required=True, help="Output patched prepared JSON path")
    parser.add_argument("--show-full-prompt", action="store_true", help="Also print the full generation prompt")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prepared_path = Path(args.prepared_input_json).expanduser().resolve()
    patch_path = Path(args.patch_json).expanduser().resolve()
    output_path = Path(args.prepared_json).expanduser().resolve()
    prepared = PreparedRewrite.model_validate_json(prepared_path.read_text(encoding="utf-8"))
    patched = apply_prepared_patch(prepared, patch_path)
    write_json(output_path, patched.model_dump())
    language = patched.request.ui_language
    print(f"Patched prepared JSON saved: {output_path}" if language == "en" else f"已保存修改后的 prepared JSON：{output_path}")
    print_compact_brief(patched)
    if args.show_full_prompt:
        title = "Full generation prompt" if language == "en" else "完整生成提示词"
        print(f"\n{title}")
        print(patched.prompt_preview.full_prompt)


if __name__ == "__main__":
    main()
