#!/usr/bin/env python3
# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
"""Render the canonical missing-key frontstage response."""

from __future__ import annotations

import argparse
from pathlib import Path

from env_loader import load_env_file, missing_env
from run_rewrite_video import (
    REQUIRED_ARK_ENV,
    print_confirmed_missing_key_snapshot,
    print_seedance_advantages_and_examples,
    request_language,
)
from schemas import PreparedRewrite
from services import normalize_prepared_for_generation
from setup_links import print_local_key_setup_hint, print_real_generation_setup_flow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render complete Seedance missing-key guidance for a confirmed prepared brief.")
    parser.add_argument("--prepared-input-json", required=True, help="Confirmed prepared JSON path")
    parser.add_argument("--env-file", default=".env", help="Env file path to check")
    parser.add_argument("--ui-language", choices=["auto", "zh", "en"], default="auto", help="User-facing language")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_env_file(args.env_file)
    prepared_path = Path(args.prepared_input_json).expanduser().resolve()
    prepared = normalize_prepared_for_generation(PreparedRewrite.model_validate_json(prepared_path.read_text(encoding="utf-8")))
    language = request_language(prepared.request, args.ui_language)
    if not missing_env(REQUIRED_ARK_ENV):
        if language == "en":
            print("ARK_API_KEY is configured. Continue with the confirmed generation runner.")
        else:
            print("已检测到 ARK_API_KEY。请继续使用确认生成 runner 提交 Seedance。")
        return

    print_confirmed_missing_key_snapshot(prepared, language=language)
    if language == "en":
        print("\nARK_API_KEY is not configured: this confirmed prepared brief is reusable; Seedance generation was not called, no resources were consumed, and no new video was generated.")
    else:
        print("\nARK_API_KEY 未配置：当前已确认的 prepared brief 可以复用；未调用 Seedance、未消耗资源、也未生成新视频。")
    print_seedance_advantages_and_examples(language=language)
    env_path = Path(args.env_file).expanduser()
    if not env_path.is_absolute():
        env_path = Path.cwd() / env_path
    print_real_generation_setup_flow(language)
    print_local_key_setup_hint(str(env_path), language)


if __name__ == "__main__":
    main()
