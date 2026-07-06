#!/usr/bin/env python3
# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
"""Prepare the local Python runtime used by this skill.

This script is intentionally stdlib-only so the host agent can run it with any
available Python before importing the skill's runtime dependencies.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
REQUIREMENTS = BASE_DIR / "requirements.txt"
VENV_DIR = BASE_DIR / ".venv"
if os.name == "nt":
    VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
else:
    VENV_PYTHON = VENV_DIR / "bin" / "python"
REQUIRED_MODULES = ["pydantic", "httpx", "imageio", "imageio_ffmpeg", "PIL"]


def tr(language: str, zh: str, en: str) -> str:
    return en if language == "en" else zh


def run(cmd: list[str], *, cwd: Path = BASE_DIR) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(cmd, cwd=str(cwd), env=env, text=True, capture_output=True, check=False)


def module_available(python: Path, module: str) -> bool:
    result = run(
        [
            str(python),
            "-c",
            "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec(sys.argv[1]) else 1)",
            module,
        ]
    )
    return result.returncode == 0


def runtime_missing(python: Path) -> list[str]:
    if not python.exists():
        return list(REQUIRED_MODULES)
    missing = [module for module in REQUIRED_MODULES if not module_available(python, module)]
    if "imageio_ffmpeg" not in missing:
        ffmpeg = run([str(python), "-c", "import imageio_ffmpeg; imageio_ffmpeg.get_ffmpeg_exe()"])
        if ffmpeg.returncode != 0:
            missing.append("ffmpeg executable from imageio-ffmpeg")
    return missing


def create_venv(language: str) -> None:
    if VENV_PYTHON.exists():
        return
    print(tr(language, "正在创建 skill 本地 Python 运行环境：.venv", "Creating the skill local Python runtime: .venv"))
    result = run([sys.executable, "-m", "venv", str(VENV_DIR)])
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(
            tr(
                language,
                "创建 .venv 失败。请确认当前目录可写，或允许 agent 在 skill 目录创建本地运行环境。",
                "Failed to create .venv. Make sure the skill directory is writable, or allow the agent to create the local runtime.",
            )
        )


def install_requirements(language: str) -> None:
    print(tr(language, "正在安装 skill 运行依赖到 .venv。", "Installing skill runtime dependencies into .venv."))
    result = run([str(VENV_PYTHON), "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(
            tr(
                language,
                "安装依赖失败。如果是网络或沙箱限制，请允许 agent 联网后重试启动依赖准备。",
                "Dependency installation failed. If this is due to network or sandbox restrictions, allow the agent to retry runtime setup with network access.",
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the viral creative rewrite skill runtime.")
    parser.add_argument("--ui-language", choices=["zh", "en"], default="zh")
    parser.add_argument("--check-only", action="store_true", help="Only check the prepared runtime; do not create or install")
    parser.add_argument("--print-python", action="store_true", help="Print the runtime Python path on the last line")
    args = parser.parse_args()

    language = args.ui_language
    missing = runtime_missing(VENV_PYTHON)
    if missing and args.check_only:
        print(tr(language, "skill 本地运行环境未准备好。", "The skill local runtime is not ready."))
        print(tr(language, "缺少：", "Missing: ") + ", ".join(missing))
        raise SystemExit(1)
    if missing:
        create_venv(language)
        install_requirements(language)
        missing = runtime_missing(VENV_PYTHON)
    if missing:
        print(tr(language, "skill 本地运行环境仍不完整。", "The skill local runtime is still incomplete."))
        print(tr(language, "缺少：", "Missing: ") + ", ".join(missing))
        raise SystemExit(1)

    print(tr(language, "skill 本地运行环境已就绪。", "The skill local runtime is ready."))
    print(f"PYTHON={VENV_PYTHON}")
    if args.print_python:
        print(VENV_PYTHON)


if __name__ == "__main__":
    main()
