# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
from copy import deepcopy
from typing import Dict, List, Optional, Tuple

from .models import FixAction, MetricMappingItem, NormalizedAssemblyInputs, PanelFinding, TargetValidation


METRIC_TOKEN = re.compile(r"\b([a-zA-Z_:][a-zA-Z0-9_:]*)\b")


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9_]+", text.lower()) if len(token) >= 3}


def _best_mapping(panel_title: str, query: str, mapping_items: List[MetricMappingItem]) -> Optional[MetricMappingItem]:
    title_tokens = _tokens(panel_title)
    query_tokens = _tokens(query)

    scored: List[Tuple[MetricMappingItem, float]] = []
    for item in mapping_items:
        sli_tokens = _tokens(item.sli_name)
        score = len(title_tokens & sli_tokens) * 0.3 + len(query_tokens & sli_tokens) * 0.2
        if item.chosen_metric and item.chosen_metric in query:
            score += 0.7
        scored.append((item, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    if not scored or scored[0][1] <= 0:
        return None
    return scored[0][0]


def _replace_first_metric(query: str, metric_name: str) -> str:
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

    def repl(match: re.Match[str]) -> str:
        token = match.group(1)
        if token in reserved:
            return token
        repl.called = True
        return metric_name

    repl.called = False  # type: ignore[attr-defined]
    replaced = METRIC_TOKEN.sub(repl, query, count=1)
    return replaced if repl.called else query


def _add_missing_labels(query: str, labels: List[str]) -> str:
    if not labels:
        return query
    if "by (" in query:
        return query
    grouped = ",".join(labels)
    if any(token in query for token in ["sum(", "avg(", "min(", "max(", "count("]):
        return f"sum by ({grouped}) ({query})"
    return query


def _ensure_default_service_variable(dashboard: Dict[str, object]) -> bool:
    templating = dashboard.setdefault("templating", {})
    if not isinstance(templating, dict):
        return False
    listing = templating.setdefault("list", [])
    if not isinstance(listing, list):
        return False

    if any(isinstance(item, dict) and item.get("name") == "service" for item in listing):
        return False

    listing.append(
        {
            "name": "service",
            "type": "query",
            "label": "service",
            "query": "label_values(up,service)",
            "refresh": 1,
            "hide": 0,
            "includeAll": False,
            "multi": False,
        }
    )
    return True


def apply_auto_repair(
    inputs: NormalizedAssemblyInputs,
    dashboard: Dict[str, object],
    validations: List[TargetValidation],
    findings: List[PanelFinding],
) -> Tuple[Dict[str, object], List[FixAction]]:
    patched = deepcopy(dashboard)
    actions: List[FixAction] = []

    if _ensure_default_service_variable(patched):
        actions.append(
            FixAction(
                panel_id=-1,
                panel_title="dashboard",
                target_index=-1,
                action="add_default_variable",
                before="",
                after="$service",
                reason="add missing default service variable",
                confidence=0.95,
            )
        )

    finding_by_target = {(item.panel_id, item.target_index): item for item in findings if item.target_index is not None}

    for panel in patched.get("panels", []):
        if not isinstance(panel, dict):
            continue
        panel_id = int(panel.get("id") or -1)
        panel_title = str(panel.get("title") or "Untitled")
        targets = panel.get("targets") if isinstance(panel.get("targets"), list) else []

        for index, target in enumerate(targets):
            if not isinstance(target, dict):
                continue
            validation = next((item for item in validations if item.panel_id == panel_id and item.target_index == index), None)
            if validation is None or validation.status == "success":
                continue

            before = str(target.get("expr") or target.get("query") or "")
            mapping = _best_mapping(panel_title, before, inputs.mapping_items)
            candidate = before

            if mapping and mapping.query_template and (not validation.executable or not validation.aggregation_ok):
                candidate = mapping.query_template
                if candidate != before:
                    actions.append(
                        FixAction(
                            panel_id=panel_id,
                            panel_title=panel_title,
                            target_index=index,
                            action="rewrite_query",
                            before=before,
                            after=candidate,
                            reason="repair query execution or aggregation semantics",
                            confidence=0.85,
                        )
                    )
            elif mapping and not validation.labels_ok:
                candidate = _add_missing_labels(before, mapping.dimensions)
                if candidate != before:
                    actions.append(
                        FixAction(
                            panel_id=panel_id,
                            panel_title=panel_title,
                            target_index=index,
                            action="adjust_labels",
                            before=before,
                            after=candidate,
                            reason="inject required grouping labels",
                            confidence=0.73,
                        )
                    )
            elif mapping and mapping.chosen_metric and mapping.chosen_metric not in before:
                candidate = _replace_first_metric(before, mapping.chosen_metric)
                if candidate != before:
                    actions.append(
                        FixAction(
                            panel_id=panel_id,
                            panel_title=panel_title,
                            target_index=index,
                            action="replace_metric_name",
                            before=before,
                            after=candidate,
                            reason="replace with mapped chosen metric",
                            confidence=0.78,
                        )
                    )

            if candidate == before and validation.status == "error":
                panel_type_before = str(panel.get("type") or "timeseries")
                if panel_type_before not in {"timeseries", "table"}:
                    panel["type"] = "timeseries"
                    actions.append(
                        FixAction(
                            panel_id=panel_id,
                            panel_title=panel_title,
                            target_index=index,
                            action="downgrade_panel_type",
                            before=panel_type_before,
                            after="timeseries",
                            reason="fallback panel type for unstable query result",
                            confidence=0.6,
                        )
                    )

            if "expr" in target:
                target["expr"] = candidate
            else:
                target["query"] = candidate

            finding = finding_by_target.get((panel_id, index))
            if finding and finding.finding_type == "no_data" and panel.get("description"):
                panel["description"] = str(panel.get("description")).strip()

    return patched, actions
