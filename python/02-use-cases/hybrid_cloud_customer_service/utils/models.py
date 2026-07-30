"""Shared response models for the hybrid-cloud demo."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class CapabilityEvent:
    name: str
    status: str = "succeeded"
    mode: str = "demo"
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AgentResponse:
    answer: str
    session_id: str
    trace_id: str
    mode: str
    citations: list[dict[str, str]] = field(default_factory=list)
    events: list[CapabilityEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["events"] = [event.to_dict() for event in self.events]
        return data
