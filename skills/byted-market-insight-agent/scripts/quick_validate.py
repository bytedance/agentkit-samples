#!/usr/bin/env python3
# Copyright 2024 ByteDance, Inc.
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
"""byted-market-insight-agent 静态自检脚本。

不进行任何外网调用，仅做以下检查：
- 关键文件与目录是否存在；
- Python 版本是否满足推荐要求；
- 关键环境变量是否已设置（仅提示，不强制）；
- 官方 SDK 是否可导入（可选依赖）。
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def check_python_version() -> bool:
    major, minor = sys.version_info[:2]
    ok = (major, minor) >= (3, 8)
    print(f"[CHECK] Python 版本: {major}.{minor} (要求 >= 3.8) -> {'OK' if ok else 'WARN'}")
    return ok


def check_files() -> bool:
    required = [
        ROOT_DIR / "SKILL.md",
        ROOT_DIR / "scripts" / "client.py",
        ROOT_DIR / "scripts" / "auth_resolver.py",
        ROOT_DIR / "scripts" / "providers" / "gateway_provider.py",
        ROOT_DIR / "scripts" / "providers" / "sdk_provider.py",
        ROOT_DIR / "references" / "usage.md",
        ROOT_DIR / "references" / "api-diff.md",
        ROOT_DIR / "persist",
    ]
    ok = True
    for path in required:
        exists = path.exists()
        kind = "目录" if path.is_dir() else "文件"
        print(f"[CHECK] {kind}: {path.relative_to(ROOT_DIR)!s} -> {'OK' if exists else 'MISSING'}")
        if not exists:
            ok = False
    return ok


def check_env() -> None:
    print("[INFO] 环境变量检查（未设置不影响静态自检，仅影响实际调用）:")
    missing_key = False
    for name in [
        "ARK_SKILL_API_BASE",
        "ARK_SKILL_API_KEY",
        "VOLCSTACK_ACCESS_KEY_ID",
        "VOLCSTACK_SECRET_ACCESS_KEY",
        "VOLCSTACK_REGION",
        "MARKET_INSIGHT_AUTO_PIP",
    ]:
        value = os.getenv(name)
        if value:
            print(f"  - {name}: 已设置（长度={len(value)}）")
        else:
            print(f"  - {name}: 未设置")
            if name in {
                "ARK_SKILL_API_BASE",
                "ARK_SKILL_API_KEY",
                "VOLCSTACK_ACCESS_KEY_ID",
                "VOLCSTACK_SECRET_ACCESS_KEY",
            }:
                missing_key = True
    if missing_key:
        print(
            "[HINT] 检测到部分关键环境变量未设置，可在 ~/.bashrc / ~/.bash_profile / ~/.zshrc / ~/.profile 中查找 export 语句（仅提示，不自动生效）。"
        )


def check_sdk_optional() -> None:
    print("[INFO] 官方 SDK 可选依赖检查：")
    spec_core = importlib.util.find_spec("volcenginesdkcore")
    spec_insight = importlib.util.find_spec("volcenginesdkinsight")
    if spec_core and spec_insight:
        print("  - volcengine SDK: 已检测到 (volcenginesdkcore / volcenginesdkinsight)")
    else:
        print(
            "  - volcengine SDK: 未检测到（运行时需要时将由 auth_resolver 自动尝试安装）"
        )


def main() -> int:
    print("=== byted-market-insight-agent 静态自检 ===")
    ok_py = check_python_version()
    ok_files = check_files()
    check_env()
    check_sdk_optional()

    all_ok = ok_py and ok_files
    print(f"[RESULT] 静态自检 {'通过' if all_ok else '存在问题，请根据上方提示修复后再打包'}")
    return 0 if all_ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
