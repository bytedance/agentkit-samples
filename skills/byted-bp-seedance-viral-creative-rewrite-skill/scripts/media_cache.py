# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import httpx


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cache_key_for_url(url: str) -> str:
    return _sha256(url)[:12]


def cache_remote_file(
    url: str,
    *,
    cache_root: Path,
    subdir: str,
    ext: str,
    filename_hint: Optional[str] = None,
) -> str:
    target_dir = cache_root / subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    url_hash = cache_key_for_url(url)
    name = f"{filename_hint}_{url_hash}" if filename_hint else url_hash
    if not name.endswith(ext):
        name = f"{name}{ext}"

    out_path = target_dir / name
    if out_path.exists() and out_path.stat().st_size > 0:
        return str(out_path)

    with httpx.Client(timeout=httpx.Timeout(300.0, connect=30.0)) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
            with tmp_path.open("wb") as handle:
                for chunk in resp.iter_bytes():
                    handle.write(chunk)
            tmp_path.replace(out_path)

    return str(out_path)
