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

from __future__ import annotations

import os

from amk_client.auth_mode import AmkAuthMode

HOSTS_BY_AUTH_MODE: dict[AmkAuthMode, dict[str, str]] = {
    AmkAuthMode.MEDIAKIT_ONLY: {
        "prod": "https://amk.cn-beijing.volces.com",
    },
    AmkAuthMode.ARK_AND_MEDIAKIT: {
        "prod": "https://amk-ark.cn-beijing.volces.com",
    },
}

DEFAULT_AMK_ENV = "prod"
DEFAULT_AMK_AUTH_MODE = AmkAuthMode.MEDIAKIT_ONLY

# 控制台入口，供缺失/错误配置时的 reference_url
AMK_CONSOLE_REFERENCE = "https://console.volcengine.com/imp/ai-mediakit/"
ARK_CONSOLE_REFERENCE = "https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seed-1-8"


class MissingConfigError(ValueError):
    """缺少或非法配置。``var`` 供程序判断；``args[0]`` 为结构化说明，便于人与 Agent 阅读。"""

    var: str

    @classmethod
    def missing_env(
        cls,
        name: str,
        *,
        purpose: str,
        reference_url: str | None = None,
        value_placeholder: str = "<值>",
    ) -> MissingConfigError:
        steps = (
            f"在仓库根目录的 `.env` 增加一行: {name}={value_placeholder}",
            f"或在本终端执行: export {name}={value_placeholder}（再重新运行命令）",
            "若由 Agent 处理：向用户索取真实密钥后，直接编辑仓库根目录 `.env` 写入该键值，"
            f"或在执行命令的 shell 中 `export {name}=<密钥>`，然后重试；不要仅复述本错误而不改配置。",
        )
        lines = [
            f"missing_env_var: {name}",
            f"purpose: {purpose}",
            "fix:",
            *[f"  - {s}" for s in steps],
            "agent_instruction: Obtain the secret from the user, then add `"
            f"{name}=<actual_value>` to repo-root `.env` or export it in the shell, and retry; do not stop after parroting this error.",
        ]
        if reference_url:
            lines.append(f"reference_url: {reference_url}")
        msg = "\n".join(lines)
        err = cls(msg)
        err.var = name
        return err

    @classmethod
    def invalid_env_value(
        cls,
        name: str,
        value: str,
        *,
        allowed: tuple[str, ...],
        purpose: str,
    ) -> MissingConfigError:
        lines = [
            f"invalid_env_var: {name}",
            f"given_value: {value!r}",
            f"allowed: {', '.join(allowed)}",
            f"purpose: {purpose}",
            "fix:",
            "  - 将环境变量设为 allowed 中之一；若未设置该变量，将使用默认 `prod`。",
            f"agent_instruction: Edit repo-root `.env` (or export) so `{name}` is one of: "
            f"{', '.join(allowed)}; or remove `{name}` to use default `prod`, then retry.",
        ]
        msg = "\n".join(lines)
        err = cls(msg)
        err.var = name
        return err


def _read_amk_env(*, auth_mode: AmkAuthMode) -> str:
    raw = os.environ.get("AMK_ENV")
    if raw is None or not raw.strip():
        return DEFAULT_AMK_ENV
    v = raw.strip().lower()
    allowed_envs = HOSTS_BY_AUTH_MODE[auth_mode]
    if v not in allowed_envs:
        raise MissingConfigError.invalid_env_value(
            "AMK_ENV",
            v,
            allowed=tuple(sorted(allowed_envs)),
            purpose="选择 AMK 网关环境：当前仅支持 `prod`（线上环境）。",
        )
    return v


def resolve_default_auth_mode() -> AmkAuthMode:
    """从 ``AMK_AUTH_MODE`` 解析 **AmkClient 的默认** 鉴权模式（仅当单次请求未传 ``auth_mode``、且构造时也未指定 ``auth_mode`` 时生效）；未设置环境变量时为 ``mediakit_only``。

    合法取值：``mediakit_only``（或 ``mediakit`` / ``single``）、
    ``ark_and_mediakit``（或 ``ark_mediakit`` / ``dual`` / ``combined``）。
    """
    raw = (os.environ.get("AMK_AUTH_MODE") or "").strip().lower()
    if raw in ("", "mediakit_only", "mediakit", "single"):
        return AmkAuthMode.MEDIAKIT_ONLY
    if raw in ("ark_and_mediakit", "ark_mediakit", "dual", "combined", "ark+mediakit"):
        return AmkAuthMode.ARK_AND_MEDIAKIT
    raise MissingConfigError.invalid_env_value(
        "AMK_AUTH_MODE",
        raw or "(empty)",
        allowed=("mediakit_only", "ark_and_mediakit"),
        purpose="注册 API 时选择的鉴权方式：仅 MediaKit Key，或 方舟 Key + MediaKit Key。",
    )


def build_authorization_header(
    *,
    mediakit_api_key: str,
    ark_api_key: str | None = None,
    mode: AmkAuthMode = DEFAULT_AMK_AUTH_MODE,
) -> str:
    """组装 ``Authorization`` 请求头的完整值（含 ``Bearer `` 前缀）。"""
    if mode == AmkAuthMode.MEDIAKIT_ONLY:
        return f"Bearer {mediakit_api_key}"
    if ark_api_key is None:
        raise ValueError("ark_and_mediakit 模式下必须提供 ark_api_key")
    return f"Bearer {ark_api_key}/{mediakit_api_key}"


def resolve_base_url(
    *,
    auth_mode: AmkAuthMode = DEFAULT_AMK_AUTH_MODE,
    fallback_env: str = DEFAULT_AMK_ENV,
) -> str:
    """Return API base URL for current ``AMK_ENV`` and auth mode.

    若显式设置了非法的 ``AMK_ENV``，抛出 ``MissingConfigError``。
    """
    env = _read_amk_env(auth_mode=auth_mode)
    hosts = HOSTS_BY_AUTH_MODE[auth_mode]
    return hosts.get(env, hosts[fallback_env])


def normalize_secret(value: str | None) -> str | None:
    """非空、非 ``null`` 的字符串视为有效密钥；否则 ``None``。"""
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or stripped.lower() == "null":
        return None
    return stripped


def default_bearer_token() -> str | None:
    """Token from ``AMK_API_KEY`` (empty or ``null`` ignored)."""
    return normalize_secret(os.environ.get("AMK_API_KEY"))


def require_amk_api_key() -> str:
    """返回可用的 MediaKit / AMK ``AMK_API_KEY``；缺失时抛出 ``MissingConfigError``。"""
    key = default_bearer_token()
    if key is None:
        raise MissingConfigError.missing_env(
            "AMK_API_KEY",
            purpose="调用 AMK（MediaKit）HTTP API 时的 Bearer 鉴权。",
            reference_url=AMK_CONSOLE_REFERENCE,
            value_placeholder="<MediaKit API Key>",
        )
    return key


def default_ark_api_key() -> str | None:
    """方舟 ``ARK_API_KEY``；未设置、空或 ``null`` 时返回 ``None``。"""
    return normalize_secret(os.environ.get("ARK_API_KEY"))


def require_ark_api_key() -> str:
    """返回可用的方舟密钥；缺失时抛出 ``MissingConfigError``。"""
    key = default_ark_api_key()
    if key is None:
        raise MissingConfigError.missing_env(
            "ARK_API_KEY",
            purpose="方舟 + MediaKit 双 Key 鉴权时，作为 ``Authorization: Bearer <方舟>/<MediaKit>`` 的前段。",
            reference_url=ARK_CONSOLE_REFERENCE,
            value_placeholder="<Ark API Key>",
        )
    return key


def require_credentials_for_mode(
    mode: AmkAuthMode,
    *,
    mediakit_from_constructor: str | None,
    ark_from_constructor: str | None,
) -> None:
    """按鉴权模式校验必填密钥（构造参数或环境变量）；缺一则抛 ``MissingConfigError``。"""
    mk = (
        normalize_secret(mediakit_from_constructor)
        if mediakit_from_constructor is not None
        else default_bearer_token()
    )
    if mode == AmkAuthMode.MEDIAKIT_ONLY:
        if (
            mediakit_from_constructor is not None
            and normalize_secret(mediakit_from_constructor) is None
        ):
            raise MissingConfigError.missing_env(
                "AMK_API_KEY",
                purpose="单 MediaKit Key 鉴权，或双 Key 模式下的 MediaKit 段。",
                reference_url=AMK_CONSOLE_REFERENCE,
                value_placeholder="<MediaKit API Key>",
            )
        if mk is None:
            require_amk_api_key()
        return

    # ARK_AND_MEDIAKIT
    if (
        mediakit_from_constructor is not None
        and normalize_secret(mediakit_from_constructor) is None
    ):
        raise MissingConfigError.missing_env(
            "AMK_API_KEY",
            purpose="双 Key 鉴权：``Authorization: Bearer <方舟 API Key>/<MediaKit API Key>`` 的后段。",
            reference_url=AMK_CONSOLE_REFERENCE,
            value_placeholder="<MediaKit API Key>",
        )
    if mk is None:
        require_amk_api_key()

    ark = (
        normalize_secret(ark_from_constructor)
        if ark_from_constructor is not None
        else default_ark_api_key()
    )
    if (
        ark_from_constructor is not None
        and normalize_secret(ark_from_constructor) is None
    ):
        raise MissingConfigError.missing_env(
            "ARK_API_KEY",
            purpose="双 Key 鉴权：``Authorization: Bearer <方舟 API Key>/<MediaKit API Key>`` 的前段。",
            reference_url=ARK_CONSOLE_REFERENCE,
            value_placeholder="<Ark API Key>",
        )
    if ark is None:
        require_ark_api_key()
