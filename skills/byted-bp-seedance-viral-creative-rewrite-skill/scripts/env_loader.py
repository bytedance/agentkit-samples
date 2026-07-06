# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


def load_env_file(path: str | Path = ".env", *, override: bool = False) -> Dict[str, str]:
    env_path = Path(path).expanduser()
    if not env_path.is_absolute():
        env_path = Path.cwd() / env_path
    if not env_path.exists():
        return {}

    loaded: Dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value
        loaded[key] = value
    return loaded


def missing_env(names: list[str]) -> list[str]:
    return [name for name in names if not (os.environ.get(name) or "").strip()]
