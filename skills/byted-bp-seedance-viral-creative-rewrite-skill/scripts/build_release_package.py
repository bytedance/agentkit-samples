#!/usr/bin/env python3
# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
"""Build a clean release zip from a strict file whitelist."""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DIST_DIR = BASE_DIR.parent / "dist"
PACKAGE_NAME = "byted-bp-seedance-viral-creative-rewrite-skill"

ROOT_FILES = [
    "SKILL.md",
    "README.md",
    "requirements.txt",
    ".env.example",
    ".gitignore",
    "LICENSE",
    "VERSION",
]
TREE_DIRS = [
    "agents",
    "references",
]
SCRIPT_FILES = [
    "build_release_package.py",
    "confirm_generation.py",
    "dependency_check.py",
    "env_loader.py",
    "ensure_runtime.py",
    "extract_video_frames.py",
    "media_cache.py",
    "media_links.py",
    "apply_brief_patch.py",
    "provider_errors.py",
    "render_brief.py",
    "render_detailed_analysis.py",
    "render_generation_result.py",
    "render_missing_key_guidance.py",
    "render_opening.py",
    "run_rewrite_video.py",
    "schemas.py",
    "seedance_runtime.py",
    "services.py",
    "setup_links.py",
]
EXAMPLE_FILES = [
    "README.md",
    "request.example.json",
    "rehearsal_prepared.example.json",
    "rehearsal_result.example.json",
    "source_product.jpg",
]


def copy_required_file(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f"missing required file: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def build_staging(dist_dir: Path) -> Path:
    package_dir = dist_dir / PACKAGE_NAME
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)

    for name in ROOT_FILES:
        copy_required_file(BASE_DIR / name, package_dir / name)

    for dirname in TREE_DIRS:
        src = BASE_DIR / dirname
        if not src.exists():
            raise FileNotFoundError(f"missing required directory: {src}")
        shutil.copytree(src, package_dir / dirname)

    scripts_dir = package_dir / "scripts"
    for name in SCRIPT_FILES:
        copy_required_file(BASE_DIR / "scripts" / name, scripts_dir / name)

    examples_dir = package_dir / "assets" / "examples"
    for name in EXAMPLE_FILES:
        copy_required_file(BASE_DIR / "assets" / "examples" / name, examples_dir / name)

    forbidden = [
        ".env",
        ".venv",
        "output",
        "assets/cache",
        "assets/examples/source_video.mp4",
        "scripts/storage_runtime.py",
        "scripts/ark_runtime.py",
        "scripts/execute_adjusted_pineapple.py",
        "__pycache__",
    ]
    for relative in forbidden:
        if (package_dir / relative).exists():
            raise RuntimeError(f"forbidden release artifact copied: {relative}")

    return package_dir


def zip_package(package_dir: Path, dist_dir: Path) -> Path:
    zip_path = dist_dir / f"{PACKAGE_NAME}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(dist_dir))
    return zip_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build clean viral creative rewrite skill release package.")
    parser.add_argument("--dist-dir", default=str(DEFAULT_DIST_DIR), help="Directory for staging folder and zip")
    parser.add_argument("--no-zip", action="store_true", help="Only build the staging directory")
    args = parser.parse_args()

    dist_dir = Path(args.dist_dir).expanduser().resolve()
    dist_dir.mkdir(parents=True, exist_ok=True)
    package_dir = build_staging(dist_dir)
    print(f"staging: {package_dir}")
    if not args.no_zip:
        zip_path = zip_package(package_dir, dist_dir)
        print(f"zip: {zip_path}")


if __name__ == "__main__":
    main()
