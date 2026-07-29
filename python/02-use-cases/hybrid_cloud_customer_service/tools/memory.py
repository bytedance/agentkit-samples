"""Tenant-isolated in-memory preference store for the demo."""

from __future__ import annotations


class MemoryTool:
    def __init__(self) -> None:
        self._preferences: dict[tuple[str, str], str] = {}

    def remember(self, tenant_id: str, user_id: str, preference: str) -> None:
        self._preferences[(tenant_id, user_id)] = preference

    def recall(self, tenant_id: str, user_id: str) -> str | None:
        return self._preferences.get((tenant_id, user_id))
