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
"""市场洞察 Agent 统一鉴权与 Provider 选择模块。

职责：
- 读取环境变量与本地持久化状态/凭证；
- 在 Gateway 与 SDK 之间做出决策，默认优先 Gateway；
- 实现会话级粘性（尽量复用上一次成功的 Provider）；
- 在需要 SDK 时自动安装 `volcengine-python-sdk>=5.0.22`；
- 将状态持久化到 `persist/state.json`，凭证持久化到 `persist/auth.json`；
- 暴露“最小化询问”占位提示，由 Agent 层据此调用 ask_user 获取凭证。

注意：本模块不做任何真实网络调用，只负责决策与配置。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Optional, Set

# ------------------------ 路径与常量 ------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent
PERSIST_DIR = ROOT_DIR / "persist"
STATE_FILE = PERSIST_DIR / "state.json"
AUTH_FILE = PERSIST_DIR / "auth.json"

# SDK 依赖要求
SDK_PACKAGE_NAME = "volcengine-python-sdk"
SDK_MIN_VERSION_SPEC = "volcengine-python-sdk>=5.0.22"

# 提示 Agent 层如何最小化询问用户
MINIMAL_ASK_HINT = (
    "当前缺少可用的市场洞察访问凭证。\n"
    "Agent 层应调用 ask_user，引导用户择一提供：\n"
    "1) API Gateway 地址 + API Key (ARK_SKILL_API_BASE / ARK_SKILL_API_KEY)，或\n"
    "2) 官方 AK/SK (VOLCSTACK_ACCESS_KEY_ID / VOLCSTACK_SECRET_ACCESS_KEY)。\n"
    "一套凭证即可，Skill 会自动选择最合适的链路，并在本地持久化，后续会话复用。"
)


# ------------------------ 自定义异常 ------------------------


class AuthError(RuntimeError):
    """鉴权失败：凭证缺失或无效。"""


class NetworkError(RuntimeError):
    """网络或网关错误（含 429 限流），已经过内部重试。"""


class MissingCredentialsError(RuntimeError):
    """完全缺少可用凭证时抛出，由 Agent 层触发最小化询问。"""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or MINIMAL_ASK_HINT)


class ProviderNotAvailableError(RuntimeError):
    """指定 Provider 不可用（如被标记为降级或缺少依赖）。"""


class SdkNotInstalledError(RuntimeError):
    """SDK 未安装或无法导入。"""


# ------------------------ 状态与凭证结构 ------------------------


@dataclass
class ProviderState:
    """Provider 运行状态，持久化到 state.json。

    字段说明：
    - provider: 上一次成功使用的 Provider 名称（"gateway" / "sdk"）。
    - degraded: 某个 Provider 是否处于降级状态（例如近期连续鉴权失败）。
    - sdk_installed: 是否已经在当前环境成功安装并导入过 SDK。
    - sdk_install_failed: SDK 安装是否已失败（失败后不再反复尝试）。
    - last_success_at: 最近一次成功调用的时间戳（秒）。
    - last_error: 最近一次错误的摘要信息（供调试使用，不含敏感信息）。
    """

    provider: Optional[str] = None
    degraded: Dict[str, bool] = field(
        default_factory=lambda: {"gateway": False, "sdk": False}
    )
    sdk_installed: bool = False
    sdk_install_failed: bool = False
    last_success_at: Optional[float] = None
    last_error: Optional[Dict[str, str]] = None


@dataclass
class AuthConfig:
    """统一的鉴权配置视图，综合环境变量与本地持久化 auth.json。

    gateway_* 字段用于 Gateway 调用；sdk_* 字段用于 SDK 调用。
    环境变量始终优先于本地 auth.json。
    """

    gateway_api_base: Optional[str] = None
    gateway_api_key: Optional[str] = None
    sdk_access_key_id: Optional[str] = None
    sdk_secret_access_key: Optional[str] = None
    sdk_region: str = "cn-beijing"


def _mask_value(value: str) -> str:
    """对环境变量值做简单脱敏处理：保留前 4 位和后 2 位，中间使用 ***。

    说明：对于长度较短的值，仍会进行脱敏，避免直接暴露完整内容。
    """
    v = value.strip()
    if not v:
        return "***"
    if len(v) <= 6:
        # 短值仅保留首尾一位
        if len(v) <= 2:
            return "***"
        return f"{v[0]}***{v[-1]}"
    return f"{v[:4]}***{v[-2:]}"


# 常见 rc 文件中允许解析的目标变量集合
RC_ENV_TARGET_VARS = {
    "ARK_SKILL_API_BASE",
    "ARK_SKILL_API_KEY",
    "VOLCSTACK_ACCESS_KEY_ID",
    "VOLCSTACK_SECRET_ACCESS_KEY",
    "VOLCSTACK_REGION",
}

# 缓存 rc 解析结果，避免多次重复读取
_RC_ENV_CACHE: Dict[str, str] = {}
_RC_ENV_SOURCE: Dict[str, str] = {}


def load_rc_env() -> Dict[str, str]:
    """从常见 rc 文件中解析 export 行，返回可用的环境变量值（不含脱敏）。

    注意：
    - 不执行 shell，不展开变量；
    - 仅解析形如 `export VAR=VALUE` 的简单单行；
    - VALUE 中若包含 `$`、`` ` ``、`$(` 等符号，则视为不可解析并跳过；
    - 仅收集 RC_ENV_TARGET_VARS 中定义的变量；
    - 若同一变量在多个文件中出现，只保留最先解析到的一份。
    """
    if _RC_ENV_CACHE:
        return dict(_RC_ENV_CACHE)

    home = Path.home()
    rc_files = [
        ("~/.bashrc", home / ".bashrc"),
        ("~/.bash_profile", home / ".bash_profile"),
        ("~/.zshrc", home / ".zshrc"),
        ("~/.profile", home / ".profile"),
    ]

    pattern = re.compile(r"^\s*export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

    for display_name, path in rc_files:
        if not path.exists() or not path.is_file():
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            # 单个文件读取失败不影响整体结果
            continue

        for line in content.splitlines():
            match = pattern.match(line)
            if not match:
                continue

            var_name, raw_value = match.group(1), match.group(2).strip()
            if var_name not in RC_ENV_TARGET_VARS:
                continue
            if var_name in _RC_ENV_CACHE:
                # 已经解析过该变量，保持最先出现的定义
                continue
            if not raw_value:
                continue

            # 对包含明显 shell 展开/命令替换的复杂表达式不做解析
            if any(sym in raw_value for sym in ("$(", "`")):
                continue

            # 去掉成对包裹的引号
            if (
                (raw_value.startswith('"') and raw_value.endswith('"'))
                or (raw_value.startswith("'") and raw_value.endswith("'"))
            ):
                raw_value = raw_value[1:-1].strip()

            if not raw_value:
                continue

            _RC_ENV_CACHE[var_name] = raw_value
            _RC_ENV_SOURCE[var_name] = display_name

    return dict(_RC_ENV_CACHE)


def discover_env_candidates() -> list[dict]:
    """只读扫描常见 shell rc 文件中的环境变量定义（脱敏后用于提示）。

    仅在当前进程缺少 ARK_* 或 VOLCSTACK_* 中任意一组凭证时才有意义：
    - 扫描 ~/.bashrc、~/.bash_profile、~/.zshrc、~/.profile（若存在）；
    - 仅匹配形如 `export VAR=VALUE` 的简单单行；
    - 支持的变量包括 RC_ENV_TARGET_VARS 中的定义；
    - 返回示例结构：
      {"file": "~/.bashrc", "vars": {"ARK_SKILL_API_BASE": "xxxx***yy", ...}} 列表。
    """
    # 当前进程如果已经具备两组凭证，则无需扫描 rc 文件
    has_ark = bool(os.getenv("ARK_SKILL_API_BASE") and os.getenv("ARK_SKILL_API_KEY"))
    has_volc = bool(
        os.getenv("VOLCSTACK_ACCESS_KEY_ID")
        and os.getenv("VOLCSTACK_SECRET_ACCESS_KEY")
    )
    if has_ark and has_volc:
        return []

    rc_env = load_rc_env()
    if not rc_env:
        return []

    # 根据变量来源文件聚合，并对值做脱敏
    file_to_vars: Dict[str, Dict[str, str]] = {}
    for var_name, raw_value in rc_env.items():
        file_label = _RC_ENV_SOURCE.get(var_name, "")
        if not file_label:
            continue
        masked = _mask_value(raw_value)
        bucket = file_to_vars.setdefault(file_label, {})
        bucket[var_name] = masked

    results: list[dict] = []
    for file_label, vars_map in file_to_vars.items():
        if vars_map:
            results.append({"file": file_label, "vars": vars_map})

    return results


# ------------------------ 文件读写工具 ------------------------


def _safe_read_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return {}
        return json.loads(text)
    except Exception:
        # 损坏或不可解析时忽略，避免阻塞运行
        return {}


def _safe_write_json(path: Path, data: Dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # 避免 NaN/Infinity 等不可序列化值
        payload = json.dumps(data, ensure_ascii=False)
        path.write_text(payload, encoding="utf-8")
    except Exception:
        # 状态写入失败不应影响主流程
        return


def load_state() -> ProviderState:
    data = _safe_read_json(STATE_FILE)
    if not data:
        return ProviderState()

    try:
        return ProviderState(
            provider=data.get("provider"),
            degraded=data.get("degraded") or {"gateway": False, "sdk": False},
            sdk_installed=bool(data.get("sdk_installed")),
            sdk_install_failed=bool(data.get("sdk_install_failed")),
            last_success_at=data.get("last_success_at"),
            last_error=data.get("last_error"),
        )
    except Exception:
        return ProviderState()


def save_state(state: ProviderState) -> None:
    _safe_write_json(STATE_FILE, asdict(state))


def load_auth() -> AuthConfig:
    """合并环境变量、本地 auth.json 与 rc 自动填充，优先级为：
    os.environ > auth.json > rc 文件。
    """

    raw = _safe_read_json(AUTH_FILE)
    gateway_raw = raw.get("gateway") if isinstance(raw.get("gateway"), dict) else {}
    sdk_raw = raw.get("sdk") if isinstance(raw.get("sdk"), dict) else {}

    # 1) 环境变量优先，其次为 auth.json
    gateway_api_base = os.getenv("ARK_SKILL_API_BASE") or gateway_raw.get("api_base")
    gateway_api_key = os.getenv("ARK_SKILL_API_KEY") or gateway_raw.get("api_key")

    sdk_access_key_id = os.getenv("VOLCSTACK_ACCESS_KEY_ID") or sdk_raw.get(
        "access_key_id"
    )
    sdk_secret_access_key = os.getenv("VOLCSTACK_SECRET_ACCESS_KEY") or sdk_raw.get(
        "secret_access_key"
    )
    sdk_region_env = os.getenv("VOLCSTACK_REGION")
    sdk_region_auth = sdk_raw.get("region")
    sdk_region = sdk_region_env or sdk_region_auth or "cn-beijing"

    auth = AuthConfig(
        gateway_api_base=gateway_api_base,
        gateway_api_key=gateway_api_key,
        sdk_access_key_id=sdk_access_key_id,
        sdk_secret_access_key=sdk_secret_access_key,
        sdk_region=sdk_region,
    )

    # 2) 若某一 Provider 的成对变量缺失，则尝试从 rc 文件自动填充（最低优先级）
    need_gateway = not (auth.gateway_api_base and auth.gateway_api_key)
    need_sdk = not (auth.sdk_access_key_id and auth.sdk_secret_access_key)

    if need_gateway or need_sdk:
        rc_env = load_rc_env()

        # Gateway: 需要同时存在 BASE 与 KEY
        if need_gateway:
            rc_base = rc_env.get("ARK_SKILL_API_BASE")
            rc_key = rc_env.get("ARK_SKILL_API_KEY")
            if rc_base and rc_key:
                auth.gateway_api_base = rc_base
                auth.gateway_api_key = rc_key
                file_label = (
                    _RC_ENV_SOURCE.get("ARK_SKILL_API_BASE")
                    or _RC_ENV_SOURCE.get("ARK_SKILL_API_KEY")
                    or "rc 文件"
                )
                masked_base = _mask_value(rc_base)
                masked_key = _mask_value(rc_key)
                print(
                    "[INFO] 从 {file} 检测到 Gateway 凭证定义（已自动采用，未持久化）："
                    "ARK_SKILL_API_BASE={base}, ARK_SKILL_API_KEY={key}".format(
                        file=file_label,
                        base=masked_base,
                        key=masked_key,
                    )
                )

        # SDK: 需要同时存在 AK 与 SK，可选 region
        if need_sdk:
            rc_ak = rc_env.get("VOLCSTACK_ACCESS_KEY_ID")
            rc_sk = rc_env.get("VOLCSTACK_SECRET_ACCESS_KEY")
            if rc_ak and rc_sk:
                auth.sdk_access_key_id = rc_ak
                auth.sdk_secret_access_key = rc_sk
                # 仅当环境变量/持久化中未显式配置 region 时，才使用 rc 中的 region
                rc_region = rc_env.get("VOLCSTACK_REGION")
                if rc_region and not (sdk_region_env or sdk_region_auth):
                    auth.sdk_region = rc_region

                file_label = (
                    _RC_ENV_SOURCE.get("VOLCSTACK_ACCESS_KEY_ID")
                    or _RC_ENV_SOURCE.get("VOLCSTACK_SECRET_ACCESS_KEY")
                    or "rc 文件"
                )
                masked_ak = _mask_value(rc_ak)
                masked_sk = _mask_value(rc_sk)
                print(
                    "[INFO] 从 {file} 检测到 SDK 凭证定义（已自动采用，未持久化）："
                    "VOLCSTACK_ACCESS_KEY_ID={ak}, VOLCSTACK_SECRET_ACCESS_KEY={sk}".format(
                        file=file_label,
                        ak=masked_ak,
                        sk=masked_sk,
                    )
                )

    return auth


def save_auth_gateway(api_base: str, api_key: str) -> None:
    raw = _safe_read_json(AUTH_FILE)
    raw["gateway"] = {
        "api_base": api_base,
        "api_key": api_key,
    }
    _safe_write_json(AUTH_FILE, raw)


def save_auth_sdk(access_key_id: str, secret_access_key: str, region: str) -> None:
    raw = _safe_read_json(AUTH_FILE)
    raw["sdk"] = {
        "access_key_id": access_key_id,
        "secret_access_key": secret_access_key,
        "region": region,
    }
    _safe_write_json(AUTH_FILE, raw)


# ------------------------ SDK 安装与检测 ------------------------


def _try_import_sdk() -> bool:
    """尝试导入 SDK 相关模块。成功返回 True，失败返回 False。"""

    try:
        import importlib

        importlib.import_module("volcenginesdkinsight")
        importlib.import_module("volcenginesdkcore")
        return True
    except Exception:
        return False


def ensure_sdk_available(state: Optional[ProviderState] = None) -> bool:
    """确保 SDK 可用：

    - 若已标记安装失败，直接返回 False；
    - 若已安装且可导入，返回 True；
    - 否则尝试通过 pip 安装一次 `volcengine-python-sdk>=5.0.22`；
    - 安装成功则返回 True，失败时标记 sdk_install_failed，返回 False。
    """

    st = state or load_state()

    if st.sdk_install_failed:
        return False

    if _try_import_sdk():
        if not st.sdk_installed:
            st.sdk_installed = True
            save_state(st)
        return True

    # 尝试自动安装
    auto_pip_flag = os.getenv("MARKET_INSIGHT_AUTO_PIP", "1").lower()
    allow_auto_pip = auto_pip_flag in {"1", "true", "yes", "y"}

    if not allow_auto_pip:
        return False

    print(
        "[INFO] 检测到 SDK 未安装，正在自动安装 "
        f"{SDK_MIN_VERSION_SPEC}（仅在缺少时执行一次）..."
    )

    cmd = [sys.executable, "-m", "pip", "install", SDK_MIN_VERSION_SPEC]

    try:
        proc = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] 自动安装 SDK 失败: {exc}")
        st.sdk_install_failed = True
        save_state(st)
        return False

    if proc.returncode != 0:
        print("[WARN] 自动安装 SDK 失败，后续将不再自动重试。")
        st.sdk_install_failed = True
        save_state(st)
        return False

    if _try_import_sdk():
        st.sdk_installed = True
        st.sdk_install_failed = False
        save_state(st)
        print("[INFO] SDK 安装并导入成功。")
        return True

    print("[WARN] SDK 安装后仍无法导入，将标记为安装失败。")
    st.sdk_install_failed = True
    save_state(st)
    return False


# ------------------------ Provider 封装 ------------------------


class BaseProvider:
    """统一的 Provider 抽象，具体实现由 Gateway / SDK 封装。"""

    name: str

    def list_custom_subs_task(self, **params):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def pull_post(self, **params):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def query_clue_info(self, **params):  # type: ignore[no-untyped-def]
        raise NotImplementedError


class GatewayProviderWrapper(BaseProvider):
    def __init__(self, api_base: str, api_key: str) -> None:
        self.name = "gateway"
        # 避免重复斜杠
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key

        # 延迟导入，避免初始化阶段的循环依赖
        from providers import gateway_provider  # type: ignore[import]

        self._impl = gateway_provider

    def list_custom_subs_task(self, **params):  # type: ignore[no-untyped-def]
        return self._impl.list_custom_subs_task(
            api_base=self.api_base,
            api_key=self.api_key,
            **params,
        )

    def pull_post(self, **params):  # type: ignore[no-untyped-def]
        return self._impl.pull_post(
            api_base=self.api_base,
            api_key=self.api_key,
            **params,
        )

    def query_clue_info(self, **params):  # type: ignore[no-untyped-def]
        return self._impl.query_clue_info(
            api_base=self.api_base,
            api_key=self.api_key,
            **params,
        )


class SdkProviderWrapper(BaseProvider):
    def __init__(self, access_key_id: str, secret_access_key: str, region: str) -> None:
        self.name = "sdk"
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.region = region

        if not ensure_sdk_available():
            raise SdkNotInstalledError(
                "volcengine-python-sdk 未安装或无法导入，且自动安装失败。"
            )

        from providers import sdk_provider  # type: ignore[import]

        self._impl = sdk_provider

    def list_custom_subs_task(self, **params):  # type: ignore[no-untyped-def]
        return self._impl.list_custom_subs_task(
            access_key_id=self.access_key_id,
            secret_access_key=self.secret_access_key,
            region=self.region,
            **params,
        )

    def pull_post(self, **params):  # type: ignore[no-untyped-def]
        return self._impl.pull_post(
            access_key_id=self.access_key_id,
            secret_access_key=self.secret_access_key,
            region=self.region,
            **params,
        )

    def query_clue_info(self, **params):  # type: ignore[no-untyped-def]
        return self._impl.query_clue_info(
            access_key_id=self.access_key_id,
            secret_access_key=self.secret_access_key,
            region=self.region,
            **params,
        )


# ------------------------ Provider 选择逻辑 ------------------------


def _pick_sticky_provider(
    state: ProviderState,
    auth: AuthConfig,
    exclude: Set[str],
) -> Optional[BaseProvider]:
    """若存在上一次成功 Provider 且未被排除，则优先尝试。"""

    name = state.provider
    if not name or name in exclude:
        return None

    if name == "gateway":
        if (
            auth.gateway_api_base
            and auth.gateway_api_key
            and not state.degraded.get("gateway", False)
        ):
            return GatewayProviderWrapper(auth.gateway_api_base, auth.gateway_api_key)

    if name == "sdk":
        if (
            auth.sdk_access_key_id
            and auth.sdk_secret_access_key
            and not state.degraded.get("sdk", False)
        ):
            return SdkProviderWrapper(
                auth.sdk_access_key_id,
                auth.sdk_secret_access_key,
                auth.sdk_region,
            )

    return None


def _pick_fresh_provider(
    state: ProviderState,
    auth: AuthConfig,
    exclude: Set[str],
) -> Optional[BaseProvider]:
    """按优先级选择 Provider：Gateway → SDK。"""

    # 默认优先 Gateway
    if (
        "gateway" not in exclude
        and auth.gateway_api_base
        and auth.gateway_api_key
        and not state.degraded.get("gateway", False)
    ):
        return GatewayProviderWrapper(auth.gateway_api_base, auth.gateway_api_key)

    # 其次 SDK
    if (
        "sdk" not in exclude
        and auth.sdk_access_key_id
        and auth.sdk_secret_access_key
        and not state.degraded.get("sdk", False)
    ):
        return SdkProviderWrapper(
            auth.sdk_access_key_id,
            auth.sdk_secret_access_key,
            auth.sdk_region,
        )

    return None


def get_provider(exclude: Optional[Set[str]] = None) -> BaseProvider:
    """决策当前应使用的 Provider。

    优先级：
    1. 若 state.provider 存在且未被排除，且对应凭证与状态可用，则优先使用（会话级粘性）；
    2. 否则按默认顺序尝试：Gateway → SDK；
    3. 若两者均不可用，则抛出 MissingCredentialsError，交由 Agent 层进行最小化询问。
    """

    exclude = exclude or set()
    state = load_state()
    auth = load_auth()

    # 先尝试粘性 Provider
    try:
        sticky = _pick_sticky_provider(state, auth, exclude)
        if sticky is not None:
            print(f"[INFO] 使用会话粘性 Provider: {sticky.name}")
            return sticky
    except (SdkNotInstalledError, ProviderNotAvailableError):
        # 如果粘性 Provider 初始化失败，继续尝试后续 Provider
        pass

    # 再按默认顺序选择
    try:
        fresh = _pick_fresh_provider(state, auth, exclude)
        if fresh is not None:
            print(f"[INFO] 使用 Provider: {fresh.name}")
            return fresh
    except SdkNotInstalledError:
        # SDK 初始化失败时，不再尝试 SDK
        state.degraded["sdk"] = True
        save_state(state)

    # 均不可用：缺少凭证或已全部降级
    candidates = discover_env_candidates()
    if candidates:
        # 在异常信息中追加只读环境变量位置提示，帮助用户排查 rc 文件
        lines = [
            "另：在以下文件中发现可能的环境变量定义，但当前进程未生效："
        ]
        for item in candidates:
            file_label = item.get("file") or ""
            vars_map = item.get("vars") or {}
            if not vars_map:
                continue
            pairs = ", ".join(f"{k}={v}" for k, v in vars_map.items())
            lines.append(f"- {file_label}: {pairs}")
        lines.append("请确认是否 export 以及启动环境是否 source 相应 rc 文件。")
        extra_msg = "\n".join(lines)
        raise MissingCredentialsError(f"{MINIMAL_ASK_HINT}\n\n{extra_msg}")
    raise MissingCredentialsError()


# ------------------------ 状态更新工具 ------------------------


def record_success(provider_name: str) -> None:
    """记录 Provider 调用成功，更新粘性状态。"""

    state = load_state()
    state.provider = provider_name
    state.degraded[provider_name] = False
    state.last_success_at = time.time()
    state.last_error = None
    save_state(state)


def mark_degraded(provider_name: str, error: Exception) -> None:
    """将指定 Provider 标记为降级，并记录错误摘要。"""

    state = load_state()
    state.degraded[provider_name] = True
    state.last_error = {
        "provider": provider_name,
        "type": error.__class__.__name__,
        "message": str(error)[:200],  # 避免异常文本过长
    }
    save_state(state)


__all__ = [
    "AuthError",
    "NetworkError",
    "MissingCredentialsError",
    "ProviderNotAvailableError",
    "SdkNotInstalledError",
    "ProviderState",
    "AuthConfig",
    "MINIMAL_ASK_HINT",
    "load_rc_env",
    "discover_env_candidates",
    "load_state",
    "save_state",
    "load_auth",
    "save_auth_gateway",
    "save_auth_sdk",
    "ensure_sdk_available",
    "BaseProvider",
    "GatewayProviderWrapper",
    "SdkProviderWrapper",
    "get_provider",
    "record_success",
    "mark_degraded",
]
