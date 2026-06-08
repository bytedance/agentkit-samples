# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SLIItem:
    sli_name: str
    sli_type: str
    measurement: str = ""
    target: str = ""
    dimensions: List[str] = field(default_factory=list)


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
    datasource_uid: str = ""
    prom_url: str = ""
    prom_bearer: str = ""
    prom_username: str = ""
    prom_password: str = ""
    time_range: str = "now-6h,now"


@dataclass
class NormalizedAssemblyInputs:
    repo_slug: str
    sli_items: List[SLIItem] = field(default_factory=list)
    mapping_items: List[MetricMappingItem] = field(default_factory=list)
    catalog_metrics: List[CatalogMetric] = field(default_factory=list)
    log_fields: List[str] = field(default_factory=list)
    trace_spans: List[str] = field(default_factory=list)
    dashboard: Dict[str, Any] = field(default_factory=dict)
    panel_targets: List[PanelTarget] = field(default_factory=list)
    evidence_items: List[EvidenceItem] = field(default_factory=list)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)


@dataclass
class ConnectivityCheck:
    datasource: str
    exists: bool
    credentials_ok: bool
    query_api_ok: bool
    status: str
    message: str


@dataclass
class TargetValidation:
    panel_id: int
    panel_title: str
    target_index: int
    ref_id: str
    datasource: str
    query: str
    executable: bool
    labels_ok: bool
    aggregation_ok: bool
    has_data: bool
    status: str
    errors: List[str] = field(default_factory=list)


@dataclass
class PanelFinding:
    panel_id: int
    panel_title: str
    severity: str
    finding_type: str
    message: str
    target_index: Optional[int] = None


@dataclass
class FixAction:
    panel_id: int
    panel_title: str
    target_index: int
    action: str
    before: str
    after: str
    reason: str
    confidence: float


@dataclass
class AcceptanceReport:
    success_rate: float
    empty_panels_count: int
    error_query_count: int
    manual_confirmation_items: List[str]
    overall_pass: bool

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
    dashboard_assembled: Dict[str, Any]
    connectivity_checks: List[ConnectivityCheck]
    target_validations: List[TargetValidation]
    panel_findings: List[PanelFinding]
    fix_actions: List[FixAction]
    acceptance: AcceptanceReport
    validation: ValidationReport
    traceability: Dict[str, Any]
    evidence_enriched: List[Dict[str, Any]]


@dataclass
class PipelineResult:
    output_dir: str
    panel_count: int
    target_count: int
    overall_pass: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
