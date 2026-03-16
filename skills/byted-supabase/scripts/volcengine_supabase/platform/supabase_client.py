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
import asyncio
import httpx
import logging
import json
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SupabaseApiError(Exception):
    def __init__(self, status_code: int, path: str, endpoint: str, payload: Any):
        self.status_code = status_code
        self.path = path
        self.endpoint = endpoint
        self.payload = payload
        super().__init__(
            json.dumps(
                {
                    "status_code": status_code,
                    "path": path,
                    "endpoint": endpoint,
                    "error": payload,
                },
                ensure_ascii=False,
            )
        )


class SupabaseClient:
    def __init__(self, endpoint: str, api_key: str):
        self.endpoint = endpoint
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return self._client

    async def close(self):
        """Close HTTP client"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def call_api(
        self,
        path: str,
        method: str = "GET",
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        content: Optional[bytes] = None,
        timeout: float = 30.0
    ) -> Any:
        url = f"{self.endpoint}{path}"
        logger.info(f"[DEBUG] Calling API: method={method}, url={url}, path={path}")

        default_headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
        }
        if headers:
            default_headers.update(headers)

        client = await self._get_client()
        for attempt in range(3):
            try:
                if content:
                    response = await client.request(
                        method, url, content=content, headers=default_headers,
                        params=params, timeout=timeout
                    )
                else:
                    response = await client.request(
                        method, url, json=json_data, headers=default_headers,
                        params=params, timeout=timeout
                    )
                response.raise_for_status()

                if response.status_code == 204 or not response.content:
                    return {"success": True}

                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    return response.json()
                return {"raw": response.text}
            except httpx.HTTPStatusError as e:
                response = e.response
                if response.status_code in {502, 503, 504} and attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                payload: Any
                try:
                    payload = response.json()
                except Exception:
                    payload = response.text
                raise SupabaseApiError(
                    status_code=response.status_code,
                    path=path,
                    endpoint=self.endpoint,
                    payload=payload,
                ) from e
            except httpx.TransportError as e:
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                detail = str(e) or type(e).__name__
                raise Exception(f"{detail} [endpoint: {self.endpoint}, path: {path}]") from e
            except Exception as e:
                if isinstance(e, SupabaseApiError):
                    raise
                detail = str(e) or type(e).__name__
                if hasattr(e, "__cause__") and e.__cause__:
                    cause_detail = str(e.__cause__) or type(e.__cause__).__name__
                    detail += f" | Cause: {cause_detail}"
                raise Exception(f"{detail} [endpoint: {self.endpoint}, path: {path}]") from e
