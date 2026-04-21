#!/usr/bin/env python3
# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
审核页 / 导出服务共用的产物目录解析：与 review_import_data.json 所在目录对齐。

未指定 --output-dir 时：在 output/ 根目录与各一级子目录中收集 review_import_data.json，
取修改时间最新的一份，避免子目录任务仍命中过期的 output/review_import_data.json。
"""

from __future__ import annotations

from pathlib import Path

from project_paths import get_project_root


def output_base(output_dir_override: str = "") -> Path:
    if not output_dir_override:
        return get_project_root() / "output"

    out_str = str(output_dir_override).strip()
    proj_root = get_project_root()

    cand = Path(out_str)
    if cand.is_absolute():
        resolved = cand.resolve()
        return resolved

    resolved = (proj_root / out_str).resolve()
    return resolved


def review_import_data_path(output_dir_override: str = "") -> Path:
    """
    查找 review_import_data.json。
    - 已指定 output/<任务>：仅在该目录及其直接子目录中解析（与旧行为一致）。
    - 仅默认 output/：根文件与子目录内文件一并候选，按 mtime 取最新。
    """
    base = output_base(output_dir_override)
    direct = base / "review_import_data.json"
    user_scoped = bool(str(output_dir_override).strip())

    if user_scoped:
        if direct.exists():
            return direct
        if base.is_dir():
            for child in sorted(
                base.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True
            ):
                cand = child / "review_import_data.json"
                if child.is_dir() and cand.exists():
                    return cand
        return direct

    candidates: list[Path] = []
    if direct.is_file():
        candidates.append(direct)
    if base.is_dir():
        for child in base.iterdir():
            if child.is_dir():
                cand = child / "review_import_data.json"
                if cand.is_file():
                    candidates.append(cand)
    if not candidates:
        return direct
    return max(candidates, key=lambda p: p.stat().st_mtime)


def infer_task_output_dir(output_dir_override: str = "") -> Path:
    """review_import_data.json 所在目录；若无此文件则回退到 output_base。"""
    rdp = review_import_data_path(output_dir_override)
    if rdp.exists():
        return rdp.parent
    return output_base(output_dir_override)


def safe_task_dir_name(name: str) -> str:
    """素材文件名（无扩展名）安全化，用作 output/<任务名> 单段目录名。"""
    s = (name or "").strip()
    if not s or s in (".", ".."):
        return "task"
    s = s.replace("\x00", "").replace("/", "_").replace("\\", "_")
    return s[:200] if s else "task"


def allocate_unique_task_output_dir(
    *,
    output_root: Path,
    raw_task_name: str,
    suffix_digits: int = 2,
    max_tries: int = 999,
) -> Path:
    """
    为本次素材处理分配唯一的 output 子目录：
      output/<name>/ 若已存在，则 output/<name>_01, _02 ...
    """
    base = safe_task_dir_name(raw_task_name)
    cand = output_root / base
    if not cand.exists():
        return cand

    width = max(2, int(suffix_digits))
    for i in range(1, int(max_tries) + 1):
        cand2 = output_root / f"{base}_{i:0{width}d}"
        if not cand2.exists():
            return cand2

    raise RuntimeError(
        f"unable to allocate unique output dir under {output_root} for task={base!r}"
    )


def infer_prepare_output_dir(step6_filename: str) -> Path:
    """
    prepare_export_data 未指定 --output-dir 时：在 output/ 根目录与各一级子目录中查找 step6，
    按文件 mtime 取最新的一份所在目录（与流水线写入子目录后的布局一致）。
    """
    base = get_project_root() / "output"
    candidates: list[Path] = []
    direct = base / step6_filename
    if direct.is_file():
        candidates.append(direct)
    if base.is_dir():
        for child in base.iterdir():
            if child.is_dir():
                cand = child / step6_filename
                if cand.is_file():
                    candidates.append(cand)
    if not candidates:
        return base
    best = max(candidates, key=lambda p: p.stat().st_mtime)
    return best.parent
