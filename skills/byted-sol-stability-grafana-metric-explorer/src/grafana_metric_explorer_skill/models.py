# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class SLIItem:
    sli_name: str
    sli_type: str
    measurement: str = ""
    dimensions: List[str] = field(default_factory=list)


@dataclass
class MetricSignal:
    name: str
    datasource: str
    dimensions: List[str] = field(default_factory=list)
    description: str = ""
    semantic_tags: List[str] = field(default_factory=list)
    query_template: str = ""


@dataclass
class MetricMapping:
    sli_name: str
    candidate_metrics: List[str] = field(default_factory=list)
    chosen_metric: str = ""
    datasource: str = "prometheus"
    query_template: str = ""
    dimensions: List[str] = field(default_factory=list)
    confidence: float = 0.0
    missing_gap: str = "none"
