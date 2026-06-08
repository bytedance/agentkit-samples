# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_log_dict(path: str) -> Any:
    target = Path(path)
    if not target.exists() or not target.is_file():
        raise ValueError(f"log dict path not found: {target}")
    return json.loads(target.read_text(encoding="utf-8"))
