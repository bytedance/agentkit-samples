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

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

import httpx

from amk_client.auth_mode import AmkAuthMode
from amk_client.config import (
    build_authorization_header,
    default_ark_api_key,
    default_bearer_token,
    normalize_secret,
    require_credentials_for_mode,
    resolve_base_url,
    resolve_default_auth_mode,
)


def _load_dotenv() -> None:
    try:
        from dotenv import find_dotenv, load_dotenv

        path = find_dotenv(usecwd=True)
        if path:
            load_dotenv(path)
    except ImportError:
        pass


class AmkClient:
    """
    Sync HTTP client for AMK APIs.

    **鉴权模式按「单次请求」指定**（与网关上各 API 注册方式一致），在
    ``request`` / ``get`` / ``post`` / ``put`` / ``delete`` / ``stream`` /
    ``iter_*`` 上传入 ``auth_mode=...``。

    - ``AmkAuthMode.MEDIAKIT_ONLY``：``Authorization: Bearer <MediaKit API Key>``
    - ``AmkAuthMode.ARK_AND_MEDIAKIT``：
      ``Authorization: Bearer <火山方舟 API Key>/<MediaKit API Key>``

    若某次调用**未传** ``auth_mode``，则使用构造参数 ``auth_mode``（默认模式）；
    构造时也未指定时，再读环境变量 ``AMK_AUTH_MODE``。

    密钥来自 ``AMK_API_KEY`` / ``ARK_API_KEY`` 或构造参数 ``api_key`` / ``ark_api_key``。

    - Base URL 默认由 ``AMK_ENV`` 与当次 ``auth_mode`` 共同决定（同一环境下不同鉴权模式可命中不同 host 组）；也可用构造参数 ``base_url`` 覆盖。
    - ``require_api_key=True``（默认）时，**每次请求**按当次 ``auth_mode`` 校验所需密钥。
    - ``require_api_key=False`` 时不校验；有密钥则仍按当次模式组 ``Authorization``。
    - 单次请求可传 ``headers`` 覆盖 ``Authorization``。
    """

    def __init__(
        self,
        *,
        auth_mode: AmkAuthMode | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        ark_api_key: str | None = None,
        require_api_key: bool = True,
        timeout: float | httpx.Timeout | None = 30.0,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        _load_dotenv()
        # 仅当具体请求未传 auth_mode 时使用（非「全局业务配置」，而是默认值）
        self._default_auth_mode = (
            auth_mode if auth_mode is not None else resolve_default_auth_mode()
        )
        self._base_override = base_url.rstrip("/") if base_url else None
        self._mediakit_explicit = api_key
        self._ark_explicit = ark_api_key
        self._require_api_key = require_api_key
        self._timeout = timeout
        self._extra_headers = dict(extra_headers) if extra_headers else {}

    def _mediakit_resolved(self) -> str | None:
        if self._mediakit_explicit is not None:
            return normalize_secret(self._mediakit_explicit)
        return default_bearer_token()

    def _ark_resolved(self) -> str | None:
        if self._ark_explicit is not None:
            return normalize_secret(self._ark_explicit)
        return default_ark_api_key()

    def _authorization_for_mode(self, mode: AmkAuthMode) -> str | None:
        mk = self._mediakit_resolved()
        if mode == AmkAuthMode.MEDIAKIT_ONLY:
            if not mk:
                return None
            return build_authorization_header(
                mediakit_api_key=mk, mode=AmkAuthMode.MEDIAKIT_ONLY
            )
        ark = self._ark_resolved()
        if not mk or not ark:
            return None
        return build_authorization_header(
            mediakit_api_key=mk,
            ark_api_key=ark,
            mode=AmkAuthMode.ARK_AND_MEDIAKIT,
        )

    def _effective_auth_mode(self, auth_mode: AmkAuthMode | None) -> AmkAuthMode:
        return auth_mode if auth_mode is not None else self._default_auth_mode

    def _merge_headers(
        self,
        call_headers: Mapping[str, str] | None,
        *,
        auth_mode: AmkAuthMode | None = None,
    ) -> dict[str, str]:
        mode = self._effective_auth_mode(auth_mode)
        if self._require_api_key:
            require_credentials_for_mode(
                mode,
                mediakit_from_constructor=self._mediakit_explicit,
                ark_from_constructor=self._ark_explicit,
            )
        merged: dict[str, str] = {**self._extra_headers}
        auth = self._authorization_for_mode(mode)
        if auth:
            merged.setdefault("Authorization", auth)
        # 默认使用 JSON 请求体；调用方可在单次请求 headers 中覆盖
        merged.setdefault("Content-Type", "application/json")
        if call_headers:
            merged.update(call_headers)
        return merged

    def _url(self, path: str, *, auth_mode: AmkAuthMode | None = None) -> str:
        p = path if path.startswith("/") else f"/{path}"
        mode = self._effective_auth_mode(auth_mode)
        base = self._base_override or resolve_base_url(
            auth_mode=mode, fallback_env="prod"
        )
        return f"{base}{p}"

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self._timeout)

    def request(
        self,
        method: str,
        path: str,
        *,
        auth_mode: AmkAuthMode | None = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        with self._client() as client:
            return client.request(
                method.upper(),
                self._url(path, auth_mode=auth_mode),
                headers=self._merge_headers(headers, auth_mode=auth_mode),
                **kwargs,
            )

    def get(
        self,
        path: str,
        *,
        auth_mode: AmkAuthMode | None = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return self.request("GET", path, auth_mode=auth_mode, headers=headers, **kwargs)

    def post(
        self,
        path: str,
        *,
        auth_mode: AmkAuthMode | None = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return self.request(
            "POST", path, auth_mode=auth_mode, headers=headers, **kwargs
        )

    def put(
        self,
        path: str,
        *,
        auth_mode: AmkAuthMode | None = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return self.request("PUT", path, auth_mode=auth_mode, headers=headers, **kwargs)

    def delete(
        self,
        path: str,
        *,
        auth_mode: AmkAuthMode | None = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return self.request(
            "DELETE", path, auth_mode=auth_mode, headers=headers, **kwargs
        )

    @contextmanager
    def stream(
        self,
        method: str,
        path: str,
        *,
        auth_mode: AmkAuthMode | None = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> Iterator[httpx.Response]:
        """Stream response body (SSE/chunked). Caller should read ``iter_bytes`` / ``iter_lines``."""
        with self._client() as client:
            with client.stream(
                method.upper(),
                self._url(path, auth_mode=auth_mode),
                headers=self._merge_headers(headers, auth_mode=auth_mode),
                **kwargs,
            ) as response:
                yield response

    def iter_bytes(
        self,
        method: str,
        path: str,
        *,
        auth_mode: AmkAuthMode | None = None,
        headers: Mapping[str, str] | None = None,
        chunk_size: int | None = None,
        **kwargs: Any,
    ) -> Iterator[bytes]:
        """Convenience: yield byte chunks from a streaming request."""
        with self.stream(
            method, path, auth_mode=auth_mode, headers=headers, **kwargs
        ) as resp:
            yield from resp.iter_bytes(chunk_size=chunk_size)

    def iter_lines(
        self,
        method: str,
        path: str,
        *,
        auth_mode: AmkAuthMode | None = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Convenience: yield text lines (e.g. SSE) from a streaming request."""
        with self.stream(
            method, path, auth_mode=auth_mode, headers=headers, **kwargs
        ) as resp:
            yield from resp.iter_lines()


class AmkAsyncClient(AmkClient):
    """Async HTTP client for AMK APIs."""

    def _async_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout)

    async def request(
        self,
        method: str,
        path: str,
        *,
        auth_mode: AmkAuthMode | None = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        async with self._async_client() as client:
            return await client.request(
                method.upper(),
                self._url(path, auth_mode=auth_mode),
                headers=self._merge_headers(headers, auth_mode=auth_mode),
                **kwargs,
            )

    async def get(
        self,
        path: str,
        *,
        auth_mode: AmkAuthMode | None = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self.request(
            "GET", path, auth_mode=auth_mode, headers=headers, **kwargs
        )

    async def post(
        self,
        path: str,
        *,
        auth_mode: AmkAuthMode | None = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self.request(
            "POST", path, auth_mode=auth_mode, headers=headers, **kwargs
        )

    async def put(
        self,
        path: str,
        *,
        auth_mode: AmkAuthMode | None = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self.request(
            "PUT", path, auth_mode=auth_mode, headers=headers, **kwargs
        )

    async def delete(
        self,
        path: str,
        *,
        auth_mode: AmkAuthMode | None = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self.request(
            "DELETE", path, auth_mode=auth_mode, headers=headers, **kwargs
        )
