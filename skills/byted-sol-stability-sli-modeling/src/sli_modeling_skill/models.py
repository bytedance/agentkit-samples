# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import re
from typing import Dict, Optional


_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def _extract_percent(value: str) -> Optional[float]:
    m = _PERCENT_RE.search(value)
    if not m:
        return None
    return float(m.group(1))


class SLIType(str, Enum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    CORRECTNESS = "correctness"
    FRESHNESS = "freshness"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"


class Severity(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


@dataclass
class SLISpec:
    capability: str
    user_journey: str
    sli_name: str
    sli_type: SLIType
    measurement: str
    denominator: str
    dimension: str
    target_slo: str
    error_budget: str
    severity: Severity
    owner: str

    def __post_init__(self) -> None:
        for field_name in (
            "capability",
            "user_journey",
            "sli_name",
            "measurement",
            "denominator",
            "dimension",
            "target_slo",
            "error_budget",
            "owner",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
            setattr(self, field_name, value.strip())

        if isinstance(self.sli_type, str):
            self.sli_type = SLIType(self.sli_type.strip().lower())
        if isinstance(self.severity, str):
            self.severity = Severity(self.severity.strip().upper())

        target_percent = _extract_percent(self.target_slo)
        if target_percent is not None:
            if target_percent >= 100:
                raise ValueError("target_slo percent must be < 100%")
            if target_percent <= 0:
                raise ValueError("target_slo percent must be > 0%")

            budget_percent = _extract_percent(self.error_budget)
            if budget_percent is not None:
                expected_budget = 100 - target_percent
                if abs(expected_budget - budget_percent) > 0.1:
                    raise ValueError("error_budget percent must align with 1 - target_slo")

    def to_dict(self) -> Dict[str, str]:
        data = asdict(self)
        data["sli_type"] = self.sli_type.value
        data["severity"] = self.severity.value
        return data
