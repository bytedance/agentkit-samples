#!/usr/bin/env python3
# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
"""Single frontstage entrypoint for the confirmed-generation gate."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from env_loader import load_env_file, missing_env
from run_rewrite_video import REQUIRED_ARK_ENV
from schemas import PreparedRewrite
from services import generation_contract_blocking_message, normalize_prepared_for_generation


BASE_DIR = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit a confirmed prepared brief, or render full missing-key guidance.")
    parser.add_argument("--prepared-input-json", required=True, help="Confirmed prepared JSON path")
    parser.add_argument("--env-file", default=".env", help="Env file path")
    parser.add_argument("--ui-language", choices=["auto", "zh", "en"], default="auto", help="User-facing language")
    parser.add_argument("--output-json", help="Optional result JSON path when generation runs")
    parser.add_argument("--show-debug-artifacts", action="store_true", help="Forward debug artifact output to the runner")
    parser.add_argument("--show-full-prompt", action="store_true", help="Forward full-prompt output to the runner")
    return parser.parse_args()


def forward(command: list[str]) -> None:
    completed = subprocess.run(command, cwd=str(BASE_DIR), env=os.environ.copy(), text=True, capture_output=True, check=False)
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    raise SystemExit(completed.returncode)


def main() -> None:
    args = parse_args()
    load_env_file(args.env_file)
    prepared_path = str(Path(args.prepared_input_json).expanduser().resolve())
    prepared = normalize_prepared_for_generation(
        PreparedRewrite.model_validate_json(Path(prepared_path).read_text(encoding="utf-8"))
    )
    from run_rewrite_video import request_language

    language = request_language(prepared.request, args.ui_language)
    contract_issue = generation_contract_blocking_message(prepared, language=language)
    if contract_issue:
        raise SystemExit(contract_issue)

    if missing_env(REQUIRED_ARK_ENV):
        forward(
            [
                sys.executable,
                str(BASE_DIR / "scripts" / "render_missing_key_guidance.py"),
                "--prepared-input-json",
                prepared_path,
                "--env-file",
                args.env_file,
                "--ui-language",
                args.ui_language,
            ]
        )

    command = [
        sys.executable,
        str(BASE_DIR / "scripts" / "run_rewrite_video.py"),
        "--prepared-input-json",
        prepared_path,
        "--env-file",
        args.env_file,
        "--ui-language",
        args.ui_language,
        "--confirmed-brief",
    ]
    if args.output_json:
        command.extend(["--output-json", args.output_json])
    if args.show_debug_artifacts:
        command.append("--show-debug-artifacts")
    if args.show_full_prompt:
        command.append("--show-full-prompt")
    forward(command)


if __name__ == "__main__":
    main()
