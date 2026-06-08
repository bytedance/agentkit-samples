# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .adapters import (
    load_existing_dashboard,
    load_log_dict,
    load_metric_mapping_spec,
    load_metrics_catalog,
    load_sli_spec,
    load_trace_spans,
)
from .models import (
    CatalogMetric,
    EvidenceItem,
    MetricMappingItem,
    NormalizedAssemblyInputs,
    PanelTarget,
    RuntimeConfig,
    SLIItem,
)


TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _pick_text(*values: Any, default: str = "") -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default


def _to_dimensions(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _normalize_sli_items(payload: Any) -> List[SLIItem]:
    records: List[Dict[str, Any]] = []
    if isinstance(payload, list):
        records.extend(item for item in payload if isinstance(item, dict))
    elif isinstance(payload, dict):
        for key in ["sli_indicators", "indicators", "slis", "items"]:
            value = payload.get(key)
            if isinstance(value, list):
                records.extend(item for item in value if isinstance(item, dict))
        if not records:
            records.append(payload)

    result: List[SLIItem] = []
    for index, item in enumerate(records, start=1):
        result.append(
            SLIItem(
                sli_name=_pick_text(item.get("sli_name"), item.get("name"), item.get("id"), default=f"sli-{index}"),
                sli_type=_pick_text(item.get("sli_type"), item.get("type"), default="availability"),
                measurement=_pick_text(item.get("measurement"), item.get("formula"), item.get("query")),
                target=_pick_text(item.get("target"), item.get("target_slo"), item.get("objective"), item.get("slo")),
                dimensions=_to_dimensions(item.get("dimensions") or item.get("dimension")),
            )
        )
    return result


def _normalize_mapping_items(payload: Any) -> List[MetricMappingItem]:
    records = payload if isinstance(payload, list) else _as_list(payload.get("items") if isinstance(payload, dict) else payload)
    result: List[MetricMappingItem] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        datasource = _pick_text(item.get("datasource"), default="prometheus").lower().replace(" ", "_")
        if datasource in {"internal", "internal-tsdb", "internaltsdb"}:
            datasource = "internal_tsdb"
        result.append(
            MetricMappingItem(
                sli_name=_pick_text(item.get("sli_name"), item.get("name")),
                chosen_metric=_pick_text(item.get("chosen_metric"), item.get("metric")),
                datasource=datasource,
                query_template=_pick_text(item.get("query_template"), item.get("query")),
                dimensions=_to_dimensions(item.get("dimensions") or item.get("labels")),
                confidence=float(item.get("confidence") or 0.0),
                missing_gap=_pick_text(item.get("missing_gap"), default="none"),
            )
        )
    return result


def _normalize_catalog_metrics(payload: Any) -> List[CatalogMetric]:
    records: List[Dict[str, Any]] = []
    if isinstance(payload, list):
        records.extend(item for item in payload if isinstance(item, dict))
    elif isinstance(payload, dict):
        values = payload.get("metrics") or payload.get("items")
        if isinstance(values, list):
            records.extend(item for item in values if isinstance(item, dict))
        elif payload:
            records.append(payload)

    result: List[CatalogMetric] = []
    for item in records:
        name = _pick_text(item.get("name"), item.get("metric"), item.get("metric_name"))
        if not name:
            continue
        datasource = _pick_text(item.get("datasource"), item.get("source"), default="prometheus").lower().replace(" ", "_")
        if datasource in {"internal", "internal-tsdb", "internaltsdb"}:
            datasource = "internal_tsdb"
        result.append(CatalogMetric(name=name, datasource=datasource, dimensions=_to_dimensions(item.get("dimensions") or item.get("labels"))))
    return result


def _iter_panels(panels: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for panel in panels:
        yield panel
        nested = panel.get("panels")
        if isinstance(nested, list):
            for sub in _iter_panels(nested):
                yield sub


def _extract_panel_targets(dashboard: Dict[str, Any], fallback_datasource: str = "prometheus") -> List[PanelTarget]:
    result: List[PanelTarget] = []
    for panel in _iter_panels(dashboard.get("panels", [])):
        panel_id = int(panel.get("id") or -1)
        panel_title = _pick_text(panel.get("title"), default="Untitled")
        panel_type = _pick_text(panel.get("type"), default="timeseries")
        panel_ds = panel.get("datasource")
        panel_ds_name = fallback_datasource
        if isinstance(panel_ds, dict):
            panel_ds_name = _pick_text(panel_ds.get("type"), panel_ds.get("uid"), default=fallback_datasource)
        elif isinstance(panel_ds, str) and panel_ds.strip():
            panel_ds_name = panel_ds.strip()

        targets = panel.get("targets") if isinstance(panel.get("targets"), list) else []
        for index, target in enumerate(targets):
            if not isinstance(target, dict):
                continue
            query = _pick_text(target.get("expr"), target.get("query"))
            ref_id = _pick_text(target.get("refId"), default=chr(ord("A") + index))
            target_ds = target.get("datasource")
            datasource = panel_ds_name
            if isinstance(target_ds, dict):
                datasource = _pick_text(target_ds.get("type"), target_ds.get("uid"), default=datasource)
            elif isinstance(target_ds, str) and target_ds.strip():
                datasource = target_ds.strip()

            result.append(
                PanelTarget(
                    panel_id=panel_id,
                    panel_title=panel_title,
                    panel_type=panel_type,
                    target_index=index,
                    ref_id=ref_id,
                    datasource=datasource.lower().replace(" ", "_"),
                    query=query,
                )
            )
    return result


def _slug(text: str) -> str:
    chars = [c.lower() if c.isalnum() else "-" for c in text.strip()]
    slug = "".join(chars)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "dashboard"


def _derive_repo_slug(existing_dashboard_path: str, dashboard: Dict[str, Any], focus_service: str | None) -> str:
    if focus_service and focus_service.strip():
        return _slug(focus_service)
    title = _pick_text(dashboard.get("title"))
    if title:
        return _slug(title)
    return _slug(Path(existing_dashboard_path).stem)


def normalize_inputs(
    sli_spec_path: str,
    metric_mapping_spec_path: str,
    metrics_catalog_path: str,
    log_dict_path: str,
    trace_spans_path: str,
    existing_dashboard_path: str,
    runtime: RuntimeConfig,
    focus_service: str | None = None,
) -> NormalizedAssemblyInputs:
    sli_payload = load_sli_spec(sli_spec_path)
    mapping_payload = load_metric_mapping_spec(metric_mapping_spec_path)
    catalog_payload = load_metrics_catalog(metrics_catalog_path)
    log_payload = load_log_dict(log_dict_path)
    trace_payload = load_trace_spans(trace_spans_path)
    dashboard_payload = load_existing_dashboard(existing_dashboard_path)

    sli_items = _normalize_sli_items(sli_payload)
    mapping_items = _normalize_mapping_items(mapping_payload)
    catalog_metrics = _normalize_catalog_metrics(catalog_payload)

    log_fields = [str(v).strip() for v in _as_list(log_payload.get("fields") if isinstance(log_payload, dict) else log_payload) if str(v).strip()]
    trace_spans = [str(v).strip() for v in _as_list(trace_payload.get("spans") if isinstance(trace_payload, dict) else trace_payload) if str(v).strip()]

    dashboard = dashboard_payload if isinstance(dashboard_payload, dict) else {}
    panel_targets = _extract_panel_targets(dashboard)

    evidence_items: List[EvidenceItem] = []
    for idx, item in enumerate(sli_items, start=1):
        evidence_items.append(
            EvidenceItem(
                evidence_id=f"ev-sli-{idx}",
                source_type="sli_spec",
                source_path=sli_spec_path,
                locator=f"sli[{idx-1}]",
                summary=item.sli_name,
            )
        )
    for idx, item in enumerate(mapping_items, start=1):
        evidence_items.append(
            EvidenceItem(
                evidence_id=f"ev-map-{idx}",
                source_type="metric_mapping_spec",
                source_path=metric_mapping_spec_path,
                locator=f"mapping[{idx-1}]",
                summary=f"{item.sli_name} -> {item.chosen_metric}",
            )
        )
    for idx, item in enumerate(catalog_metrics, start=1):
        evidence_items.append(
            EvidenceItem(
                evidence_id=f"ev-catalog-{idx}",
                source_type="metrics_catalog",
                source_path=metrics_catalog_path,
                locator=item.name,
                summary=item.name,
            )
        )
    for idx, field in enumerate(log_fields, start=1):
        evidence_items.append(
            EvidenceItem(
                evidence_id=f"ev-log-{idx}",
                source_type="log_dict",
                source_path=log_dict_path,
                locator=field,
                summary=field,
            )
        )
    for idx, span in enumerate(trace_spans, start=1):
        evidence_items.append(
            EvidenceItem(
                evidence_id=f"ev-trace-{idx}",
                source_type="trace_spans",
                source_path=trace_spans_path,
                locator=span,
                summary=span,
            )
        )

    return NormalizedAssemblyInputs(
        repo_slug=_derive_repo_slug(existing_dashboard_path, dashboard, focus_service),
        sli_items=sli_items,
        mapping_items=mapping_items,
        catalog_metrics=catalog_metrics,
        log_fields=log_fields,
        trace_spans=trace_spans,
        dashboard=dashboard,
        panel_targets=panel_targets,
        evidence_items=evidence_items,
        runtime=runtime,
    )
