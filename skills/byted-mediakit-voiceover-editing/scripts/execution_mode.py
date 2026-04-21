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
执行模式解析：apig > cloud > local。

- apig: ARK_SKILL_API_BASE + ARK_SKILL_API_KEY 均存在
- cloud: VOLC_ACCESS_KEY_* 或 apig 变量 + ASR_API_KEY 等均存在
- local: 无需任何云端环境变量，使用本地 Qwen-ASR / Demucs / ffmpeg

缺参处理（非交互，v1.0.9）：
  - 打印 .env 路径与缺失变量列表，建议用户在 .env 中补全后重试
  - 不使用 input() 交互（避免 Agent / IDE 上下文中阻塞或粘贴异常）
  - 显式指定模式 + 缺参 → 提示 + exit 1（不降级，不改 .env）
  - 自动检测 APIG 缺参 → 降级到 cloud；cloud 也缺 → exit 1
  - cloud 缺参 → exit 1（不降到 local，local 只能显式选择）
若使用 --mode，切换模式是否写入 .env 见 persist_mode_to_env。
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Optional


class ExecutionMode(str, Enum):
    APIG = "apig"
    CLOUD = "cloud"
    LOCAL = "local"


# ─── 自动加载 .env（保证 resolve_mode 自包含，不依赖调用方） ───
_DOTENV_LOADED = False


def _ensure_dotenv_loaded() -> None:
    """确保 .env 已加载到 os.environ（仅首次调用生效，override=False）"""
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    try:
        from dotenv import load_dotenv

        env_path = _get_env_file_path()
        if env_path.is_file():
            load_dotenv(dotenv_path=env_path, override=False)
    except ImportError:
        pass  # dotenv 不可用时仅靠进程环境


_CLOUD_ENV_VARS_VOD = [
    "VOLC_ACCESS_KEY_ID",
    "VOLC_ACCESS_KEY_SECRET",
    "VOLC_SPACE_NAME",
]
_CLOUD_ENV_VARS_ASR = ["ASR_API_KEY", "ASR_BASE_URL"]
_APIG_ENV_VARS = ["ARK_SKILL_API_BASE", "ARK_SKILL_API_KEY"]

_ENV_HELP = {
    "ARK_SKILL_API_BASE": "SkillHub 网关 OpenAPI 根 URL（通常由容器注入）",
    "ARK_SKILL_API_KEY": "SkillHub 网关 Bearer Token（通常由容器注入）",
    "VOLC_ACCESS_KEY_ID": "火山引擎 Access Key ID  →  https://console.volcengine.com/iam/keymanage",
    "VOLC_ACCESS_KEY_SECRET": "火山引擎 Access Key Secret  →  同上",
    "VOLC_SPACE_NAME": "火山引擎 VOD 点播空间名称  →  https://console.volcengine.com/vod",
    "ASR_API_KEY": "豆包语音转写 API Key  →  https://console.volcengine.com/speech/new/experience/asr",
    "ASR_BASE_URL": "豆包语音转写 Base URL（默认 https://openspeech.bytedance.com/api/v3/auc/bigmodel）",
}


def _env_set(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def _check_vars(names: list[str]) -> list[str]:
    return [n for n in names if not _env_set(n)]


def _get_env_file_path() -> Path:
    return Path(__file__).resolve().parents[1] / ".env"


def _apply_execution_mode_preference(
    mode: ExecutionMode, *, persist_to_dotenv: bool
) -> None:
    """当前进程始终设置 EXECUTION_MODE；是否写入 .env 由 persist_to_dotenv 决定。"""
    os.environ["EXECUTION_MODE"] = mode.value
    if persist_to_dotenv:
        _write_mode_to_env(mode)


def _write_mode_to_env(mode: ExecutionMode) -> None:
    """将 EXECUTION_MODE 写入 .env 文件，后续脚本可直接读取"""
    env_file = _get_env_file_path()
    if not env_file.exists():
        env_file.write_text(f"EXECUTION_MODE={mode.value}\n", encoding="utf-8")
        return
    content = env_file.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=False)
    found = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("EXECUTION_MODE") and "=" in stripped:
            new_lines.append(f"EXECUTION_MODE={mode.value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.insert(0, f"EXECUTION_MODE={mode.value}")
    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _write_var_to_env(env_file: Path, key: str, value: str) -> None:
    """将单个 KEY=VALUE 写入 .env（存在则替换，否则追加）"""
    if not env_file.exists():
        env_file.write_text(f"{key}={value}\n", encoding="utf-8")
        return
    content = env_file.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=False)
    found = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(key) and "=" in stripped:
            prefix = stripped.split("=", 1)[0].strip()
            if prefix == key:
                new_lines.append(f"{key}={value}")
                found = True
                continue
        new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def step_log(mode: ExecutionMode, step: str, message: str) -> None:
    """统一步骤日志：【local】step1: xxx"""
    print(f"【{mode.value}】{step}: {message}", flush=True)


# ---------------------------------------------------------------------------
# 统一的 local 模式检测函数（供所有脚本导入，替代各自重复的 _detect_local_mode）
# ---------------------------------------------------------------------------

_CACHED_LOCAL_MODE: bool | None = None


def detect_local_mode() -> bool:
    """检测当前是否为 local 模式（基于环境变量自动检测，结果缓存）。

    所有脚本应统一从此处导入，不再各自重复实现。
    """
    global _CACHED_LOCAL_MODE
    if _CACHED_LOCAL_MODE is not None:
        return _CACHED_LOCAL_MODE
    _ensure_dotenv_loaded()
    try:
        _CACHED_LOCAL_MODE = resolve_mode(interactive=False) == ExecutionMode.LOCAL
    except Exception:
        _CACHED_LOCAL_MODE = os.getenv("EXECUTION_MODE", "").strip().lower() == "local"
    return _CACHED_LOCAL_MODE


def detect_execution_mode() -> ExecutionMode:
    """检测当前执行模式并返回 ExecutionMode 枚举值（非交互，结果不缓存）。"""
    try:
        return resolve_mode(interactive=False)
    except Exception:
        env_val = os.getenv("EXECUTION_MODE", "").strip().lower()
        try:
            return ExecutionMode(env_val)
        except ValueError:
            return ExecutionMode.LOCAL


def resolve_mode(
    requested: Optional[str] = None,
    *,
    interactive: bool = True,
) -> ExecutionMode:
    """
    解析执行模式。

    1. requested 参数（来自 --mode CLI 参数）→ 绝对锁定
    2. EXECUTION_MODE 环境变量（.env 或 export）→ 绝对锁定（包括 local/cloud/apig）
    3. 自动检测：apig > cloud > local（仅当上述均未设置时）
    4. 均不满足 → 打印提示 + 自动降级

    注意：不再使用 input() 交互。缺参时打印提示信息并自动降级。
    """
    persist_mode_to_env = not (requested and str(requested).strip())

    # 自动加载 .env（保证 SkillHub 等场景下 .env 中的 EXECUTION_MODE 可见）
    _ensure_dotenv_loaded()

    # 1. CLI 显式指定（最高优先级，local 也直接返回）
    if requested:
        mode = ExecutionMode(requested.lower())
        if mode == ExecutionMode.LOCAL:
            return mode
        missing = _validate_mode(mode)
        if not missing:
            return mode
        return _handle_missing_vars(
            mode,
            missing,
            interactive=interactive,
            persist_mode_to_env=persist_mode_to_env,
            explicit=True,
        )

    # 2. 显式 EXECUTION_MODE（.env 或进程环境）→ 绝对锁定，优先于自动检测
    #    用户通过 .env 或 export 指定的模式，即使存在 ARK_* 也不会被"自动升级"
    env_mode_explicit = os.getenv("EXECUTION_MODE", "").strip().lower()
    if env_mode_explicit:
        try:
            explicit_mode = ExecutionMode(env_mode_explicit)
            if explicit_mode == ExecutionMode.LOCAL:
                return explicit_mode
            missing = _validate_mode(explicit_mode)
            if not missing:
                return explicit_mode
            return _handle_missing_vars(
                explicit_mode,
                missing,
                interactive=interactive,
                persist_mode_to_env=persist_mode_to_env,
                explicit=True,
            )
        except ValueError:
            pass  # 无效值，继续自动检测

    # 3. 自动检测: apig > cloud（始终执行，不被 .env EXECUTION_MODE 阻断）
    apig_ok = not _check_vars(_APIG_ENV_VARS)
    if apig_ok:
        supplementary_missing = _check_vars(["VOLC_SPACE_NAME"] + _CLOUD_ENV_VARS_ASR)
        if not supplementary_missing:
            return ExecutionMode.APIG
        return _handle_missing_vars(
            ExecutionMode.APIG,
            supplementary_missing,
            interactive=interactive,
            persist_mode_to_env=persist_mode_to_env,
        )

    cloud_missing = _check_vars(_CLOUD_ENV_VARS_VOD + _CLOUD_ENV_VARS_ASR)
    if not cloud_missing:
        return ExecutionMode.CLOUD

    # 4. 均不满足 → 提示并降级
    return _handle_missing_vars(
        ExecutionMode.CLOUD,
        cloud_missing,
        interactive=interactive,
        persist_mode_to_env=persist_mode_to_env,
    )


def _validate_mode(mode: ExecutionMode) -> list[str]:
    if mode == ExecutionMode.APIG:
        core = _check_vars(_APIG_ENV_VARS)
        if core:
            return core
        return _check_vars(["VOLC_SPACE_NAME"] + _CLOUD_ENV_VARS_ASR)
    if mode == ExecutionMode.CLOUD:
        return _check_vars(_CLOUD_ENV_VARS_VOD + _CLOUD_ENV_VARS_ASR)
    return []


def _handle_missing_vars(
    intended_mode: ExecutionMode,
    missing: list[str],
    *,
    interactive: bool = True,
    persist_mode_to_env: bool = True,
    explicit: bool = False,
) -> ExecutionMode:
    """处理缺失环境变量。

    策略（v1.0.9）:
    - explicit=True（用户显式指定）→ 打印缺失列表 + exit 1，不降级，不改 .env
    - explicit=False（自动检测 apig）→ 降级到 cloud；cloud 也缺 → exit 1
    - cloud 缺变量 → exit 1（不降到 local，local 只能显式选择）
    """
    env_file = _get_env_file_path()

    # 打印缺参提示
    print()
    print("=" * 60)
    print(f"⚠️  当前 {intended_mode.value} 模式缺少以下环境变量:")
    for var in missing:
        desc = _ENV_HELP.get(var, "")
        print(f"   • {var}: {desc}")
    print()
    print("📝 请在 .env 文件中补全上述变量后重试:")
    print(f"   {env_file}")
    print()

    # 显式指定 → 不降级，直接退出
    if explicit:
        print(f"[错误] 您显式指定了 {intended_mode.value} 模式，但所需环境变量不全。")
        print("=" * 60)
        raise SystemExit(1)

    # 自动检测 apig → 有限降级到 cloud
    if intended_mode == ExecutionMode.APIG:
        cloud_missing = _check_vars(_CLOUD_ENV_VARS_VOD + _CLOUD_ENV_VARS_ASR)
        if not cloud_missing:
            _apply_execution_mode_preference(
                ExecutionMode.CLOUD,
                persist_to_dotenv=persist_mode_to_env,
            )
            print("→ APIG 补充变量不全，但 cloud 变量齐全，自动降级到 cloud 模式")
            print("=" * 60)
            return ExecutionMode.CLOUD
        # cloud 也不齐 → exit（不降到 local）
        print("[错误] apig 补充变量不全，cloud 变量也不全。")
        print()
        print("您有两个选择:")
        print(f"  ① 补全变量 → 在 {env_file} 中填写所需项，然后重新运行")
        print("  ② 切换到 local 模式（本地 ASR + ffmpeg，无需云端密钥）:")
        print(f"      在 {env_file} 中设置:  EXECUTION_MODE=local")
        print("      或启动时指定:           --mode local")
        print("=" * 60)
        raise SystemExit(1)

    if intended_mode == ExecutionMode.CLOUD:
        # cloud 缺变量 → exit（不降到 local）
        print("[错误] cloud 模式所需环境变量不全。")
        print()
        print("您有两个选择:")
        print(f"  ① 补全变量 → 在 {env_file} 中填写上述缺失项，然后重新运行")
        print("  ② 切换到 local 模式（本地 ASR + ffmpeg，无需云端密钥）:")
        print(f"      在 {env_file} 中设置:  EXECUTION_MODE=local")
        print("      或启动时指定:           --mode local")
        print("=" * 60)
        raise SystemExit(1)

    # local 本身无需额外变量
    print("=" * 60)
    return ExecutionMode.LOCAL
