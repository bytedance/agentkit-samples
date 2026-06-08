# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
from copy import deepcopy
from typing import Dict, List, Tuple

from .models import MetricMappingItem, NormalizedAssemblyInputs, PanelTarget, TargetValidation


TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")
METRIC_PATTERN = re.compile(r"\b([a-zA-Z_:][a-zA-Z0-9_:]*)\b")


def _tokens(text: str) -> set[str]:
    return {token for token in TOKEN_PATTERN.findall(text.lower()) if len(token) >= 3}


def _balanced(text: str, left: str, right: str) -> bool:
    count = 0
    for ch in text:
        if ch == left:
            count += 1
        elif ch == right:
            count -= 1
            if count < 0:
                return False
    return count == 0


def _query_executable(query: str) -> tuple[bool, List[str]]:
    errors: List[str] = []
    if not query.strip():
        errors.append("empty query")
    if not _balanced(query, "(", ")"):
        errors.append("unbalanced parentheses")
    if not _balanced(query, "{", "}"):
        errors.append("unbalanced braces")
    return len(errors) == 0, errors


def _extract_labels(query: str) -> set[str]:
    labels: set[str] = set()
    match = re.search(r"\{([^}]*)\}", query)
    if match:
        for part in match.group(1).split(","):
            key = re.split(r"=~|!=|=", part.strip(), maxsplit=1)[0].strip()
            if key:
                labels.add(key)

    for match in re.finditer(r"by\s*\(([^)]*)\)", query):
        for part in match.group(1).split(","):
            key = part.strip()
            if key:
                labels.add(key)

    return labels


def _extract_metric_names(query: str) -> set[str]:
    reserved = {
        "sum",
        "avg",
        "min",
        "max",
        "count",
        "rate",
        "irate",
        "increase",
        "histogram_quantile",
        "topk",
        "bottomk",
        "clamp_min",
        "clamp_max",
        "by",
        "without",
    }
    names = set()
    for token in METRIC_PATTERN.findall(query):
        if token not in reserved:
            names.add(token)
    return names


def _catalog_dimensions_for_query(query: str, catalog_dimensions: Dict[str, set[str]]) -> set[str]:
    dimensions: set[str] = set()
    for metric_name in _extract_metric_names(query):
        dimensions.update(catalog_dimensions.get(metric_name, set()))
    return dimensions


def _aggregation_ok(query: str, sli_type: str) -> bool:
    stype = sli_type.lower()
    lower = query.lower()
    if "latency" in stype:
        return any(token in lower for token in ["histogram_quantile", "quantile", "p95", "p99"])
    if any(token in stype for token in ["availability", "correctness", "completeness"]):
        return "/" in lower or "ratio" in lower
    return True


def _guess_has_data(query: str) -> bool:
    lower = query.lower()
    if any(token in lower for token in ["absent(", "no_data_metric", "missing_metric"]):
        return False
    return True


def _best_mapping(target: PanelTarget, mapping_items: List[MetricMappingItem]) -> MetricMappingItem | None:
    title_tokens = _tokens(target.panel_title)
    query_tokens = _tokens(target.query)

    scored: List[tuple[MetricMappingItem, float]] = []
    for item in mapping_items:
        score = 0.0
        sli_tokens = _tokens(item.sli_name)
        score += len(title_tokens & sli_tokens) * 0.3
        score += len(query_tokens & sli_tokens) * 0.2
        if item.chosen_metric and item.chosen_metric in target.query:
            score += 0.8
        if item.datasource and target.datasource.startswith(item.datasource):
            score += 0.2
        scored.append((item, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    if not scored:
        return None
    if scored[0][1] <= 0:
        return None
    return scored[0][0]


def _normalize_datasource_type(name: str) -> str:
    normalized = (name or "prometheus").strip().lower().replace(" ", "_")
    return normalized or "prometheus"


def _datasource_var_name(datasource_type: str) -> str:
    return "DS_" + _normalize_datasource_type(datasource_type).upper()


def _grafana_datasource_ref(datasource_type: str, runtime_uid: str) -> Dict[str, str]:
    normalized = _normalize_datasource_type(datasource_type)
    if runtime_uid and normalized == "prometheus":
        return {"type": normalized, "uid": runtime_uid}
    return {"type": normalized, "uid": "${" + _datasource_var_name(normalized) + "}"}


def _uses_datasource_variable(datasource_type: str, runtime_uid: str) -> bool:
    normalized = _normalize_datasource_type(datasource_type)
    return not (runtime_uid and normalized == "prometheus")


def _plugin_name(datasource_type: str) -> str:
    normalized = _normalize_datasource_type(datasource_type)
    if normalized == "prometheus":
        return "Prometheus"
    if normalized == "tempo":
        return "Tempo"
    if normalized == "loki":
        return "Loki"
    return normalized


def _datasource_input(datasource_type: str) -> Dict[str, str]:
    normalized = _normalize_datasource_type(datasource_type)
    return {
        "name": _datasource_var_name(normalized),
        "label": _plugin_name(normalized),
        "description": "",
        "type": "datasource",
        "pluginId": normalized,
        "pluginName": _plugin_name(normalized),
    }


def _merge_dashboard_inputs(existing: object, datasource_types: set[str]) -> List[Dict[str, str]]:
    merged: Dict[str, Dict[str, str]] = {}
    if isinstance(existing, list):
        for item in existing:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                merged[item["name"]] = item

    for datasource_type in sorted(datasource_types):
        item = _datasource_input(datasource_type)
        merged[item["name"]] = item

    return [merged[name] for name in sorted(merged)]


def _require_item(datasource_type: str) -> Dict[str, str]:
    normalized = _normalize_datasource_type(datasource_type)
    return {
        "type": "datasource",
        "id": normalized,
        "name": _plugin_name(normalized),
        "version": "",
    }


def _merge_requires(existing: object, datasource_types: set[str]) -> List[Dict[str, str]]:
    merged: Dict[str, Dict[str, str]] = {}
    if isinstance(existing, list):
        for item in existing:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                merged[item["id"]] = item

    for datasource_type in sorted(datasource_types):
        item = _require_item(datasource_type)
        merged[item["id"]] = item

    return [merged[name] for name in sorted(merged)]


def adapt_queries(inputs: NormalizedAssemblyInputs, dashboard: Dict[str, object]) -> Tuple[Dict[str, object], List[TargetValidation]]:
    patched = deepcopy(dashboard)
    panel_targets = inputs.panel_targets

    target_lookup = {(item.panel_id, item.target_index): item for item in panel_targets}
    mapping_by_target: Dict[tuple[int, int], MetricMappingItem | None] = {}
    for target in panel_targets:
        mapping_by_target[(target.panel_id, target.target_index)] = _best_mapping(target, inputs.mapping_items)

    catalog_dimensions: Dict[str, set[str]] = {item.name: set(item.dimensions) for item in inputs.catalog_metrics}

    validations: List[TargetValidation] = []
    datasource_inputs: set[str] = set()

    for panel in patched.get("panels", []):
        targets = panel.get("targets") if isinstance(panel.get("targets"), list) else []
        for index, target in enumerate(targets):
            if not isinstance(target, dict):
                continue
            panel_id = int(panel.get("id") or -1)
            key = (panel_id, index)
            base = target_lookup.get(key)
            if base is None:
                continue

            mapping = mapping_by_target.get(key)
            query = (target.get("expr") or target.get("query") or "").strip()
            if not query and mapping and mapping.query_template:
                query = mapping.query_template

            if mapping and mapping.chosen_metric and mapping.chosen_metric not in query and mapping.query_template:
                query = mapping.query_template

            if "expr" in target:
                target["expr"] = query
            else:
                target["query"] = query

            source_ds = mapping.datasource if mapping else base.datasource
            datasource_ref = _grafana_datasource_ref(source_ds, inputs.runtime.datasource_uid)
            if _uses_datasource_variable(source_ds, inputs.runtime.datasource_uid):
                datasource_inputs.add(_normalize_datasource_type(source_ds))
            target["datasource"] = datasource_ref
            panel["datasource"] = datasource_ref

            executable, errors = _query_executable(query)
            required_labels = set(mapping.dimensions) if mapping else set()
            existing_labels = _extract_labels(query)
            available_from_catalog = _catalog_dimensions_for_query(query, catalog_dimensions)
            labels_ok = required_labels.issubset(existing_labels | available_from_catalog) if required_labels else True

            sli_type = mapping.sli_name if mapping else panel.get("title", "")
            aggregation_ok = _aggregation_ok(query, sli_type)
            has_data = _guess_has_data(query)

            if not executable:
                status = "error"
            elif executable and labels_ok and aggregation_ok and has_data:
                status = "success"
            else:
                status = "warning"

            if not labels_ok:
                missing = sorted(required_labels - existing_labels)
                errors.append(f"missing labels: {', '.join(missing)}")
            if not aggregation_ok:
                errors.append("aggregation does not match sli semantics")
            if not has_data:
                errors.append("query has no data in selected range")

            validations.append(
                TargetValidation(
                    panel_id=panel_id,
                    panel_title=str(panel.get("title") or "Untitled"),
                    target_index=index,
                    ref_id=str(target.get("refId") or chr(ord("A") + index)),
                    datasource=base.datasource,
                    query=query,
                    executable=executable,
                    labels_ok=labels_ok,
                    aggregation_ok=aggregation_ok,
                    has_data=has_data,
                    status=status,
                    errors=errors,
                )
            )

    if datasource_inputs:
        patched["__inputs"] = _merge_dashboard_inputs(patched.get("__inputs"), datasource_inputs)
        patched["__requires"] = _merge_requires(patched.get("__requires"), datasource_inputs)

    return patched, validations
