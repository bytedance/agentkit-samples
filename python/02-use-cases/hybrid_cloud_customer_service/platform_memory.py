"""AgentKit Memory adapter injected through Runtime associations."""

from __future__ import annotations

import hashlib
import logging
import os
import time

import requests


logger = logging.getLogger(__name__)


def normalize_memory_tool_metadata(tools: list[object]) -> None:
    """Keep VeADK's load_memory metadata hashable and JSON-safe.

    VeADK 0.5.40 stores the backend object in
    ``LoadMemoryTool.custom_metadata["backend"]``. AgentKit/ADK processes
    this diagnostic metadata while handling a tool call, but the Pydantic
    backend instance is mutable and unhashable. Replace only the metadata
    value with its stable class name; the tool keeps using the original
    long-term-memory backend.
    """
    for tool in tools:
        if getattr(tool, "name", "") != "load_memory":
            continue
        metadata = getattr(tool, "custom_metadata", None)
        if not isinstance(metadata, dict):
            continue
        backend = metadata.get("backend")
        if backend is not None and not isinstance(backend, (str, int, float, bool)):
            metadata["backend"] = type(backend).__name__


def build_platform_memory(app_name: str):
    """Return a VeADK mem0 backend or None when no platform binding exists."""
    endpoint = os.getenv("DATABASE_MEM0_BASE_URL", "").rstrip("/")
    api_key = os.getenv("DATABASE_MEM0_API_KEY", "")
    if not endpoint or not api_key:
        return None
    from veadk.memory import LongTermMemory
    from veadk.memory.long_term_memory_backends.base_backend import (
        BaseLongTermMemoryBackend,
    )

    async_mode = os.getenv("MEM0_ASYNC_MODE", "true").lower() not in {
        "0",
        "false",
        "no",
    }

    class AgentKitMem0Backend(BaseLongTermMemoryBackend):
        """Small Mem0 REST adapter; avoids shipping an unused local vector DB."""

        def precheck_index_naming(self) -> bool:
            """Validate the runtime-selected index before VeADK starts using it.

            AgentKit injects the Mem0 binding at runtime.  The platform accepts
            the application name as the index namespace, so no remote call is
            needed here; this hook fulfils the VeADK backend contract.
            """
            return bool(self.index and self.index.strip())

        def _headers(self) -> dict[str, str]:
            return {
                "Authorization": f"Token {api_key}",
                "Mem0-User-ID": hashlib.md5(api_key.encode()).hexdigest(),
                "Content-Type": "application/json",
            }

        def save_memory(self, user_id: str, event_strings: list[str], **kwargs) -> bool:
            del kwargs
            messages = [
                {"role": "user", "content": event_string}
                for event_string in event_strings
                if event_string.strip()
            ]
            if not messages:
                return True
            # Mem0 accepts a message list.  One batch prevents a session's
            # individual events from exhausting the component's write quota.
            for attempt in range(3):
                response = requests.post(
                    f"{endpoint}/v1/memories/",
                    headers=self._headers(),
                    json={
                        "messages": messages,
                        "user_id": user_id,
                        "output_format": "v1.1",
                        "async_mode": async_mode,
                        "version": "v2",
                    },
                    timeout=30,
                )
                if getattr(response, "status_code", None) == 429 and attempt < 2:
                    retry_after = getattr(response, "headers", {}).get("Retry-After", "")
                    try:
                        delay = min(float(retry_after), 2.0) if retry_after else 0.25 * (2**attempt)
                    except ValueError:
                        delay = 0.25 * (2**attempt)
                    time.sleep(delay)
                    continue
                response.raise_for_status()
                logger.info(
                    "MEM0 write accepted: events=%s async_mode=%s status=%s",
                    len(messages),
                    async_mode,
                    getattr(response, "status_code", "unknown"),
                )
                return True
            return True

        def search_memory(
            self,
            user_id: str,
            query: str,
            top_k: int,
            **kwargs,
        ) -> list[str]:
            del kwargs
            response = requests.post(
                f"{endpoint}/v1/memories/search/",
                headers=self._headers(),
                json={
                    "query": query,
                    "user_id": user_id,
                    "output_format": "v1.1",
                    "top_k": top_k,
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            results = payload if isinstance(payload, list) else payload.get("results", [])
            logger.info("MEM0 search completed: results=%s", len(results))
            return [str(item["memory"]) for item in results if item.get("memory")]

    return LongTermMemory(backend=AgentKitMem0Backend(index=app_name), app_name=app_name, top_k=3)
