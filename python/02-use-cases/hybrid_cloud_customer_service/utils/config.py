"""Environment configuration without secret-bearing defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_ARK_MODEL_NAME = "deepseek-v4-pro-260425"
DEFAULT_ARK_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"


@dataclass(frozen=True, slots=True)
class Settings:
    mode: str
    model_name: str | None
    model_api_key: str | None
    model_api_base: str

    @classmethod
    def from_env(cls) -> "Settings":
        mode = os.getenv("DEMO_MODE", "auto").lower()
        if mode not in {"auto", "live", "demo"}:
            raise ValueError("DEMO_MODE must be auto, live, or demo")
        return cls(
            mode=mode,
            model_name=(
                os.getenv("MODEL_AGENT_NAME") or os.getenv("ARK_MODEL") or DEFAULT_ARK_MODEL_NAME
            ),
            model_api_key=os.getenv("MODEL_AGENT_API_KEY") or os.getenv("ARK_API_KEY"),
            model_api_base=(
                os.getenv("MODEL_AGENT_API_BASE")
                or os.getenv("ARK_BASE_URL")
                or DEFAULT_ARK_API_BASE
            ),
        )

    @property
    def effective_mode(self) -> str:
        if self.mode == "demo":
            return "demo"
        if self.model_name and self.model_api_key:
            return "live"
        if self.mode == "live":
            raise ValueError("MODEL_AGENT_API_KEY is required in live mode")
        return "demo"
