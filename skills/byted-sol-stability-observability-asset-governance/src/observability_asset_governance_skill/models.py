# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


KNOWN_DATASOURCES = {"prometheus", "loki", "tempo", "internal_tsdb", "grafana"}
SEVERITY_VALUES = {"info", "warning", "error"}


@dataclass
class SLIItem:
    sli_name: str
    sli_type: str
    measurement: str = ""
    target: str = ""
    dimensions: List[str] = field(default_factory=list)


@dataclass
class ArchitectureCapability:
    name: str
    source: str


@dataclass
class MetricMappingItem:
    sli_name: str
    chosen_metric: str
    datasource: str
    query_template: str
    dimensions: List[str] = field(default_factory=list)
    confidence: float = 0.0
    missing_gap: str = "none"


@dataclass
class CatalogMetric:
    name: str
    datasource: str
    dimensions: List[str] = field(default_factory=list)


@dataclass
class PanelTarget:
    panel_id: int
    panel_title: str
    panel_type: str
    target_index: int
    ref_id: str
    datasource: str
    query: str


@dataclass
class UsageStat:
    dashboard_uid: str
    dashboard_title: str
    views: int = 0
    favorites: int = 0
    oncall_visits: int = 0
    panel_views: Dict[str, int] = field(default_factory=dict)


@dataclass
class RegistryEntry:
    asset_id: str
    asset_type: str
    name: str
    service: str
    owner: str = "unassigned"
    status: str = "active"
    source: str = "generated"
    last_seen: str = ""

    def with_last_seen(self) -> "RegistryEntry":
        if self.last_seen:
            return self
        self.last_seen = datetime.now(timezone.utc).isoformat()
        return self


@dataclass
class EvidenceItem:
    evidence_id: str
    source_type: str
    source_path: str
    locator: str
    summary: str


@dataclass
class RuntimeConfig:
    offline: bool = False
    grafana_url: str = ""
    grafana_token: str = ""
    prom_url: str = ""
    prom_bearer: str = ""
    prom_username: str = ""
    prom_password: str = ""


@dataclass
class NormalizedGovernanceInputs:
    repo_slug: str
    sli_items: List[SLIItem] = field(default_factory=list)
    architecture_capabilities: List[ArchitectureCapability] = field(default_factory=list)
    mapping_items: List[MetricMappingItem] = field(default_factory=list)
    catalog_metrics: List[CatalogMetric] = field(default_factory=list)
    dashboard: Dict[str, Any] = field(default_factory=dict)
    panel_targets: List[PanelTarget] = field(default_factory=list)
    usage_stats: List[UsageStat] = field(default_factory=list)
    registry_entries: List[RegistryEntry] = field(default_factory=list)
    evidence_items: List[EvidenceItem] = field(default_factory=list)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)


@dataclass
class GovernanceFinding:
    category: str
    finding_type: str
    severity: str
    message: str
    recommendation: str
    owner: str = "unassigned"
    asset_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
            "issues": [asdict(item) for item in self.issues],
        }


@dataclass
class PipelineArtifacts:
    governance_summary: Dict[str, Any]
    dashboard_drift_report: Dict[str, Any]
    metric_drift_report: Dict[str, Any]
    usage_analysis_report: Dict[str, Any]
    stale_panel_report: Dict[str, Any]
    duplicate_dashboard_report: Dict[str, Any]
    definition_conflict_report: Dict[str, Any]
    incremental_update_plan: Dict[str, Any]
    asset_registry: Dict[str, Any]
    validation_report: ValidationReport
    traceability: Dict[str, Any]
    evidence_enriched: List[Dict[str, Any]]


@dataclass
class PipelineResult:
    output_dir: str
    finding_count: int
    overall_pass: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
