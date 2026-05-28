from __future__ import annotations

import sys
import types
from pathlib import Path


PACKAGE_NAME = "_byted_volcengine_vmp_scripts"


def ensure_package() -> str:
    """
    为“直接执行脚本文件”场景提供稳定导入方式（不修改 sys.path）。

    用法：
    - 在 `python scripts/query_metrics.py ...` 这种运行方式下，`__package__` 为空，
      相对导入不可用；这里通过注入一个“临时包”并设置 `__path__` 指向当前目录，
      让 `from _byted_volcengine_vmp_scripts.xxx import ...` 能工作。
    """
    if PACKAGE_NAME in sys.modules:
        return PACKAGE_NAME

    pkg = types.ModuleType(PACKAGE_NAME)
    pkg.__path__ = [str(Path(__file__).resolve().parent)]
    sys.modules[PACKAGE_NAME] = pkg
    return PACKAGE_NAME

