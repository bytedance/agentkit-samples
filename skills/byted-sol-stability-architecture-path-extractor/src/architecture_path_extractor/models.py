# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List


@dataclass
class Signal:
    kind: str
    source_file: str
    value: str
    evidence: str = ""


@dataclass
class GraphNode:
    node_id: str
    node_type: str
    name: str
    attributes: Dict[str, str] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str
    target: str
    edge_type: str
    evidence: str


@dataclass
class PathRecord:
    category: str
    name: str
    hops: List[str]
    evidence: List[str] = field(default_factory=list)


@dataclass
class FailurePoint:
    component: str
    risk: str
    impact: str
    evidence: List[str] = field(default_factory=list)


@dataclass
class ObservabilityGap:
    component: str
    gap_type: str
    missing_signal: str
    suggestion: str
    evidence: List[str] = field(default_factory=list)


@dataclass
class TopologyModel:
    service_graph: Dict[str, List[Dict[str, str]]]
    request_paths: List[Dict[str, object]]
    async_paths: List[Dict[str, object]]
    dependency_graph: Dict[str, List[Dict[str, str]]]
    failure_points: List[Dict[str, object]]
    observability_hook_points: List[Dict[str, object]]
    metadata: Dict[str, str]

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)
