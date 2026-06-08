# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .models import (
    ArchitectureCapability,
    CatalogMetric,
    EvidenceItem,
    MetricMappingItem,
    NormalizedGovernanceInputs,
    PanelTarget,
    RegistryEntry,
    RuntimeConfig,
    SLIItem,
    UsageStat,
)


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


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _normalize_sli_items(payload: Any) -> List[SLIItem]:
    records: List[Dict[str, Any]] = []
    if isinstance(payload, list):
        records.extend(item for item in payload if isinstance(item, dict))
    elif isinstance(payload, dict):
        for key in ["sli_indicators", "indicators", "slis", "items"]:
            value = payload.get(key)
            if isinstance(value, list):
                records.extend(item for item in value if isinstance(item, dict))
        if not records and payload:
            records.append(payload)

    result: List[SLIItem] = []
    for idx, item in enumerate(records, start=1):
        result.append(
            SLIItem(
                sli_name=_pick_text(item.get("sli_name"), item.get("name"), item.get("id"), default=f"sli-{idx}"),
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


def _normalize_catalog_metrics(payload: Any, mappings: List[MetricMappingItem]) -> List[CatalogMetric]:
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

    known = {item.name for item in result}
    for mapping in mappings:
        if mapping.chosen_metric and mapping.chosen_metric not in known:
            result.append(CatalogMetric(name=mapping.chosen_metric, datasource=mapping.datasource, dimensions=mapping.dimensions))
            known.add(mapping.chosen_metric)

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


def _normalize_usage_stats(payload: Any, dashboard: Dict[str, Any]) -> List[UsageStat]:
    records: List[Dict[str, Any]] = []
    if isinstance(payload, list):
        records.extend(item for item in payload if isinstance(item, dict))
    elif isinstance(payload, dict):
        values = payload.get("dashboards") or payload.get("items")
        if isinstance(values, list):
            records.extend(item for item in values if isinstance(item, dict))
        elif payload:
            records.append(payload)

    result: List[UsageStat] = []
    for item in records:
        result.append(
            UsageStat(
                dashboard_uid=_pick_text(item.get("dashboard_uid"), item.get("uid"), default=_pick_text(dashboard.get("uid"), default="dashboard")),
                dashboard_title=_pick_text(item.get("dashboard_title"), item.get("title"), default=_pick_text(dashboard.get("title"), default="dashboard")),
                views=int(item.get("views") or 0),
                favorites=int(item.get("favorites") or 0),
                oncall_visits=int(item.get("oncall_visits") or 0),
                panel_views={str(k): int(v) for k, v in (item.get("panel_views") or {}).items()} if isinstance(item.get("panel_views"), dict) else {},
            )
        )

    if not result:
        result.append(
            UsageStat(
                dashboard_uid=_pick_text(dashboard.get("uid"), default="dashboard"),
                dashboard_title=_pick_text(dashboard.get("title"), default="dashboard"),
            )
        )

    return result


def _normalize_registry_entries(payload: Any) -> List[RegistryEntry]:
    records: List[Dict[str, Any]] = []
    if isinstance(payload, list):
        records.extend(item for item in payload if isinstance(item, dict))
    elif isinstance(payload, dict):
        values = payload.get("assets") or payload.get("items")
        if isinstance(values, list):
            records.extend(item for item in values if isinstance(item, dict))
        elif payload:
            records.append(payload)

    result: List[RegistryEntry] = []
    for item in records:
        result.append(
            RegistryEntry(
                asset_id=_pick_text(item.get("asset_id"), item.get("id"), default=""),
                asset_type=_pick_text(item.get("asset_type"), item.get("type"), default="dashboard"),
                name=_pick_text(item.get("name"), item.get("title"), default="unknown"),
                service=_pick_text(item.get("service"), default="unknown"),
                owner=_pick_text(item.get("owner"), default="unassigned"),
                status=_pick_text(item.get("status"), default="active"),
                source=_pick_text(item.get("source"), default="input_registry"),
                last_seen=_pick_text(item.get("last_seen")),
            )
        )
    return result


def _load_architecture_capabilities(path: str) -> List[ArchitectureCapability]:
    p = Path(path)
    if p.is_file():
        return [ArchitectureCapability(name=p.stem, source=str(p))]
    if not p.exists() or not p.is_dir():
        return []

    result: List[ArchitectureCapability] = []
    for item in sorted(p.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            result.append(ArchitectureCapability(name=item.name, source=str(item)))
        elif item.suffix.lower() in {".md", ".json", ".yaml", ".yml"}:
            result.append(ArchitectureCapability(name=item.stem, source=str(item)))
    return result


def _slug(text: str) -> str:
    chars = [c.lower() if c.isalnum() else "-" for c in text.strip()]
    slug = "".join(chars)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "governance"


def _derive_repo_slug(existing_dashboard_path: str, dashboard: Dict[str, Any], focus_service: str | None) -> str:
    if focus_service and focus_service.strip():
        return _slug(focus_service)
    title = _pick_text(dashboard.get("title"))
    if title:
        return _slug(title)
    return _slug(Path(existing_dashboard_path).stem)


def normalize_inputs(
    sli_spec_path: str,
    architecture_spec_path: str,
    metric_mapping_spec_path: str,
    existing_dashboard_path: str,
    metrics_catalog_path: str | None,
    usage_stats_path: str | None,
    asset_registry_path: str | None,
    runtime: RuntimeConfig,
    focus_service: str | None = None,
) -> NormalizedGovernanceInputs:
    sli_payload = _load_json(sli_spec_path)
    mapping_payload = _load_json(metric_mapping_spec_path)
    dashboard_payload = _load_json(existing_dashboard_path)
    catalog_payload = _load_json(metrics_catalog_path) if metrics_catalog_path else {}
    usage_payload = _load_json(usage_stats_path) if usage_stats_path else {}
    registry_payload = _load_json(asset_registry_path) if asset_registry_path else {}

    sli_items = _normalize_sli_items(sli_payload)
    mapping_items = _normalize_mapping_items(mapping_payload)
    catalog_metrics = _normalize_catalog_metrics(catalog_payload, mapping_items)
    dashboard = dashboard_payload if isinstance(dashboard_payload, dict) else {}
    panel_targets = _extract_panel_targets(dashboard)
    usage_stats = _normalize_usage_stats(usage_payload, dashboard)
    registry_entries = _normalize_registry_entries(registry_payload)
    architecture_capabilities = _load_architecture_capabilities(architecture_spec_path)

    evidence_items: List[EvidenceItem] = []
    for idx, item in enumerate(sli_items, start=1):
        evidence_items.append(EvidenceItem(f"ev-sli-{idx}", "sli_spec", sli_spec_path, f"sli[{idx-1}]", item.sli_name))
    for idx, item in enumerate(mapping_items, start=1):
        evidence_items.append(EvidenceItem(f"ev-map-{idx}", "metric_mapping_spec", metric_mapping_spec_path, f"mapping[{idx-1}]", f"{item.sli_name}->{item.chosen_metric}"))
    for idx, item in enumerate(catalog_metrics, start=1):
        evidence_items.append(EvidenceItem(f"ev-metric-{idx}", "metrics_catalog", metrics_catalog_path or "derived", item.name, item.name))
    for idx, item in enumerate(panel_targets, start=1):
        evidence_items.append(EvidenceItem(f"ev-panel-{idx}", "existing_dashboard", existing_dashboard_path, f"panel={item.panel_id}/target={item.target_index}", item.panel_title))
    for idx, item in enumerate(architecture_capabilities, start=1):
        evidence_items.append(EvidenceItem(f"ev-arch-{idx}", "architecture_spec", item.source, item.name, item.name))

    return NormalizedGovernanceInputs(
        repo_slug=_derive_repo_slug(existing_dashboard_path, dashboard, focus_service),
        sli_items=sli_items,
        architecture_capabilities=architecture_capabilities,
        mapping_items=mapping_items,
        catalog_metrics=catalog_metrics,
        dashboard=dashboard,
        panel_targets=panel_targets,
        usage_stats=usage_stats,
        registry_entries=registry_entries,
        evidence_items=evidence_items,
        runtime=runtime,
    )
