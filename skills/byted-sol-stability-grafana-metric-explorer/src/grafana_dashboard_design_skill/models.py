# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SLIIndicator:
    indicator_id: str
    name: str
    sli_type: str
    target: str = ""
    formula: str = ""
    owner: str = ""


@dataclass
class ArchPath:
    path_id: str
    name: str
    category: str
    hops: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)


@dataclass
class DependencyRisk:
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
class EvidenceItem:
    evidence_id: str
    source_type: str
    source_path: str
    locator: str
    summary: str


@dataclass
class TraceLink:
    target_type: str
    target_id: str
    evidence_ids: List[str] = field(default_factory=list)
    rationale: str = ""


@dataclass
class NormalizedInputs:
    repo_slug: str
    sli_indicators: List[SLIIndicator] = field(default_factory=list)
    request_paths: List[ArchPath] = field(default_factory=list)
    async_paths: List[ArchPath] = field(default_factory=list)
    dependency_risks: List[DependencyRisk] = field(default_factory=list)
    observability_gaps: List[ObservabilityGap] = field(default_factory=list)
    code_metric_hints: List[str] = field(default_factory=list)
    evidence_items: List[EvidenceItem] = field(default_factory=list)
    focus_service: Optional[str] = None


@dataclass
class IASection:
    section_id: str
    name: str
    zone_type: str
    purpose: str


@dataclass
class IAPage:
    page_id: str
    page_type: str
    name: str
    purpose: str
    sections: List[IASection] = field(default_factory=list)


@dataclass
class DashboardIA:
    title: str
    pages: List[IAPage] = field(default_factory=list)
    global_variables: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ThresholdRule:
    color: str
    operator: str
    value: float


@dataclass
class DrillDownLink:
    title: str
    target: str


@dataclass
class PanelSpec:
    panel_id: str
    page_id: str
    section_id: str
    title: str
    chart_type: str
    metric_formula: str
    dimensions: List[str]
    refresh_interval: str
    thresholds: List[ThresholdRule]
    drilldown: DrillDownLink
    sli_link: str
    path_link: str
    zone_type: str
    confidence: str
    evidence_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["thresholds"] = [asdict(item) for item in self.thresholds]
        data["drilldown"] = asdict(self.drilldown)
        return data


@dataclass
class GrafanaPanelDTO:
    panel_id: str
    title: str
    panel_type: str
    expr: str
    grid_pos: Dict[str, int]
    description: str
    links: List[Dict[str, str]] = field(default_factory=list)
    threshold_steps: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class GrafanaDashboardDoc:
    title: str
    uid: str
    tags: List[str] = field(default_factory=list)
    refresh: str = "30s"
    time_from: str = "now-6h"
    panels: List[GrafanaPanelDTO] = field(default_factory=list)
    templating_variables: List[str] = field(default_factory=list)
    annotations: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "uid": self.uid,
            "tags": self.tags,
            "refresh": self.refresh,
            "time": {"from": self.time_from, "to": "now"},
            "templating": {
                "list": [
                    {
                        "name": name,
                        "label": name,
                        "type": "textbox",
                        "query": "",
                        "current": {"text": "all", "value": "all"},
                    }
                    for name in self.templating_variables
                ]
            },
            "annotations": {"list": self.annotations},
            "panels": [
                {
                    "id": index + 1,
                    "title": panel.title,
                    "type": panel.panel_type,
                    "gridPos": panel.grid_pos,
                    "targets": [{"refId": "A", "expr": panel.expr}],
                    "fieldConfig": {
                        "defaults": {
                            "thresholds": {
                                "mode": "absolute",
                                "steps": panel.threshold_steps,
                            }
                        },
                        "overrides": [],
                    },
                    "description": panel.description,
                    "links": panel.links,
                }
                for index, panel in enumerate(self.panels)
            ],
            "schemaVersion": 39,
            "version": 1,
        }


@dataclass
class ValidationIssue:
    level: str
    rule: str
    message: str


@dataclass
class ValidationReport:
    passed: bool
    summary: Dict[str, int]
    issues: List[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "summary": self.summary,
            "issues": [asdict(issue) for issue in self.issues],
        }


@dataclass
class PipelineResult:
    output_dir: str
    panel_count: int
    placeholder_panel_count: int
    page_count: int
    validation_passed: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
