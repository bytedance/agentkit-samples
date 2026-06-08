# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List

from .adapters import discover_code_metric_hints, load_arch_model, load_sli_model
from .models import (
    ArchPath,
    DependencyRisk,
    EvidenceItem,
    NormalizedInputs,
    ObservabilityGap,
    SLIIndicator,
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


def _normalize_sli_indicator(item: Dict[str, Any], index: int) -> SLIIndicator:
    indicator_id = _pick_text(item.get("indicator_id"), item.get("id"), item.get("sli_name"), default=f"sli-{index}")
    name = _pick_text(
        item.get("name"),
        item.get("title"),
        item.get("indicator"),
        item.get("sli_name"),
        item.get("capability"),
        default=indicator_id,
    )
    sli_type = _pick_text(
        item.get("sli_type"),
        item.get("type"),
        item.get("category"),
        default="availability",
    )
    target = _pick_text(item.get("target"), item.get("objective"), item.get("slo"), item.get("target_slo"))
    formula = _pick_text(
        item.get("formula"),
        item.get("query"),
        item.get("metric_formula"),
        item.get("measurement"),
    )
    owner = _pick_text(item.get("owner"), item.get("service"), item.get("component"))
    return SLIIndicator(
        indicator_id=indicator_id,
        name=name,
        sli_type=sli_type,
        target=target,
        formula=formula,
        owner=owner,
    )


def _extract_sli_indicators(payload: Any) -> List[SLIIndicator]:
    candidates: List[Dict[str, Any]] = []

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                candidates.append(item)
        return [_normalize_sli_indicator(item, index) for index, item in enumerate(candidates, start=1)]

    if not isinstance(payload, dict):
        return []

    for key in ["indicators", "sli_indicators", "slis", "specs"]:
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    if isinstance(item.get("indicators"), list):
                        for nested in item["indicators"]:
                            if isinstance(nested, dict):
                                candidates.append(nested)
                    else:
                        candidates.append(item)

    items_value = payload.get("items")
    if not candidates and isinstance(items_value, list):
        for item in items_value:
            if isinstance(item, dict):
                candidates.append(item)

    if not candidates and payload:
        candidates.append(payload)

    return [_normalize_sli_indicator(item, index) for index, item in enumerate(candidates, start=1)]


def _normalize_path(item: Dict[str, Any], index: int, category: str) -> ArchPath:
    path_id = _pick_text(item.get("id"), item.get("path_id"), default=f"{category}-{index}")
    name = _pick_text(item.get("name"), item.get("title"), default=path_id)
    hops_raw = item.get("hops")
    hops: List[str]
    if isinstance(hops_raw, list):
        hops = [str(v) for v in hops_raw if str(v).strip()]
    elif isinstance(item.get("path"), list):
        hops = [str(v) for v in item["path"] if str(v).strip()]
    else:
        hops = []
    evidence = [str(v) for v in _as_list(item.get("evidence")) if str(v).strip()]
    return ArchPath(path_id=path_id, name=name, category=category, hops=hops, evidence=evidence)


def _extract_paths(topology_model: Dict[str, Any], key: str, category: str) -> List[ArchPath]:
    records = topology_model.get(key)
    if not isinstance(records, list):
        return []
    result: List[ArchPath] = []
    for index, item in enumerate(records, start=1):
        if isinstance(item, dict):
            result.append(_normalize_path(item, index, category))
    return result


def _extract_dependency_risks(topology_model: Dict[str, Any]) -> List[DependencyRisk]:
    risks = topology_model.get("failure_points")
    if not isinstance(risks, list):
        return []
    normalized: List[DependencyRisk] = []
    for item in risks:
        if not isinstance(item, dict):
            continue
        normalized.append(
            DependencyRisk(
                component=_pick_text(item.get("component"), item.get("service"), default="unknown"),
                risk=_pick_text(item.get("risk"), item.get("description"), default="unknown risk"),
                impact=_pick_text(item.get("impact"), item.get("severity"), default="unknown impact"),
                evidence=[str(v) for v in _as_list(item.get("evidence")) if str(v).strip()],
            )
        )
    return normalized


def _extract_observability_gaps(topology_model: Dict[str, Any]) -> List[ObservabilityGap]:
    gaps = topology_model.get("observability_hook_points")
    if not isinstance(gaps, list):
        return []
    normalized: List[ObservabilityGap] = []
    for item in gaps:
        if not isinstance(item, dict):
            continue
        normalized.append(
            ObservabilityGap(
                component=_pick_text(item.get("component"), default="unknown"),
                gap_type=_pick_text(item.get("gap_type"), item.get("hook_type"), default="metric"),
                missing_signal=_pick_text(item.get("missing_signal"), item.get("description"), default="unknown"),
                suggestion=_pick_text(item.get("suggestion"), item.get("target"), default="add observability"),
                evidence=[str(v) for v in _as_list(item.get("evidence")) if str(v).strip()],
            )
        )
    return normalized


def _extract_evidence_items(evidence_payload: Any) -> List[EvidenceItem]:
    items = evidence_payload if isinstance(evidence_payload, list) else []
    normalized: List[EvidenceItem] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        source_path = _pick_text(item.get("source"), item.get("source_path"), default="unknown")
        normalized.append(
            EvidenceItem(
                evidence_id=_pick_text(item.get("id"), default=f"ev-{index}"),
                source_type=_pick_text(item.get("kind"), item.get("source_type"), default="unknown"),
                source_path=source_path,
                locator=_pick_text(item.get("locator"), default=source_path),
                summary=_pick_text(item.get("summary"), default=source_path),
            )
        )
    return normalized


def _derive_repo_slug(repo: str) -> str:
    return Path(repo).name.strip() or "repo"


def normalize_inputs(
    sli_model_path: str,
    arch_model_dir: str,
    repo: str,
    focus_service: str | None = None,
    offline: bool = False,
) -> NormalizedInputs:
    _ = offline

    sli_payload = load_sli_model(sli_model_path)
    arch_payload = load_arch_model(arch_model_dir)

    topology_model = arch_payload["topology_model"]
    sli_indicators = _extract_sli_indicators(sli_payload)
    request_paths = _extract_paths(topology_model, "request_paths", "request")
    async_paths = _extract_paths(topology_model, "async_paths", "async")
    dependency_risks = _extract_dependency_risks(topology_model)
    observability_gaps = _extract_observability_gaps(topology_model)
    evidence_items = _extract_evidence_items(arch_payload.get("evidence_index", []))

    code_metric_hints = discover_code_metric_hints(repo)

    return NormalizedInputs(
        repo_slug=_derive_repo_slug(repo),
        sli_indicators=sli_indicators,
        request_paths=request_paths,
        async_paths=async_paths,
        dependency_risks=dependency_risks,
        observability_gaps=observability_gaps,
        code_metric_hints=code_metric_hints,
        evidence_items=evidence_items,
        focus_service=focus_service,
    )
