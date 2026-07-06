# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


BASE_DEPENDENCIES = {
    "pydantic": "pydantic",
}

PROVIDER_DEPENDENCIES = {
    "httpx": "httpx",
}

ANALYSIS_DEPENDENCIES = {
    "imageio": "imageio",
    "imageio_ffmpeg": "imageio-ffmpeg",
    "PIL": "pillow",
}


def _forced_missing() -> set[str]:
    raw = ",".join(
        item
        for item in [
            # Used by regression tests to simulate a fresh machine without
            # mutating the current Python environment.
            os.environ.get("VIRAL_REWRITE_FORCE_MISSING_DEPS", ""),
        ]
        if item
    )
    return {item.strip() for item in raw.split(",") if item.strip()}


def _missing_from(dependencies: dict[str, str]) -> list[str]:
    forced = _forced_missing()
    missing: list[str] = []
    for module_name, package_name in dependencies.items():
        if module_name in forced or package_name in forced:
            missing.append(package_name)
            continue
        if importlib.util.find_spec(module_name) is None:
            missing.append(package_name)
    return missing


def missing_core_dependencies(*, include_provider: bool = True) -> list[str]:
    dependencies = dict(BASE_DEPENDENCIES)
    if include_provider:
        dependencies.update(PROVIDER_DEPENDENCIES)
    return _missing_from(dependencies)


def missing_analysis_dependencies() -> list[str]:
    return _missing_from(ANALYSIS_DEPENDENCIES)


def print_dependency_help(
    missing: list[str],
    *,
    base_dir: Path,
    provider_only: bool = False,
    analysis_only: bool = False,
    language: str = "zh",
) -> None:
    if language == "en":
        if analysis_only:
            print("\nMissing local video-understanding dependencies, so template frame extraction cannot start yet.")
        elif provider_only:
            print("\nMissing real video generation dependencies, so Seedance cannot be called yet.")
        else:
            print("\nMissing runtime dependencies, so the video rewrite workflow cannot start yet.")
        print(f"Missing: {', '.join(missing)}")
        print("Run this in the skill root before analysis or generation:")
        print(f"{sys.executable} -m pip install -r requirements.txt")
        print(f"Directory: {base_dir}")
        print("Do not install dependencies in the middle of a user generation flow; run this setup step first.")
        return

    if analysis_only:
        print("\n缺少本地视频理解依赖，暂时不能开始模板抽帧。")
    elif provider_only:
        print("\n缺少真实视频生成依赖，暂时不能调用 Seedance。")
    else:
        print("\n缺少运行依赖，暂时不能启动视频复刻流程。")
    print(f"缺少：{', '.join(missing)}")
    print("请先在 skill 根目录执行：")
    print(f"{sys.executable} -m pip install -r requirements.txt")
    print(f"执行目录：{base_dir}")
    print("不要在用户生成流程中途临时安装依赖；请先完成这一步环境准备。")


def ensure_core_dependencies(*, base_dir: Path, include_provider: bool = True, language: str = "zh") -> None:
    missing = missing_core_dependencies(include_provider=include_provider)
    if not missing:
        return
    base_missing = [item for item in missing if item in BASE_DEPENDENCIES.values()]
    print_dependency_help(missing, base_dir=base_dir, provider_only=include_provider and not base_missing, language=language)
    raise SystemExit(1)


def ensure_analysis_dependencies(*, base_dir: Path, language: str = "zh") -> None:
    missing = missing_analysis_dependencies()
    if not missing:
        return
    print_dependency_help(missing, base_dir=base_dir, analysis_only=True, language=language)
    raise SystemExit(1)
