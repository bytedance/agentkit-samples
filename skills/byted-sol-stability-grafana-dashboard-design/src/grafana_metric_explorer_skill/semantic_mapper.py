from __future__ import annotations

import re
from typing import Dict, List, Tuple

from .models import MetricMapping, MetricSignal, SLIItem
from .query_templates import build_query_template


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> List[str]:
    return [token for token in TOKEN_PATTERN.findall(text.lower()) if len(token) >= 3]


def _type_fit_score(sli_type: str, metric_name: str) -> float:
    metric = metric_name.lower()
    stype = sli_type.lower()
    latency_keys = ["latency", "duration", "p95", "p99", "seconds", "ms", "bucket"]
    reliability_keys = ["success", "error", "request", "availability", "complete", "correct", "good", "bad"]

    if "latency" in stype:
        if any(key in metric for key in latency_keys):
            return 1.0
        if any(key in metric for key in ["_total", "_count", "success", "error", "good", "bad"]):
            return 0.0
        return 0.2

    if any(key in stype for key in ["availability", "correctness", "completeness"]):
        if any(key in metric for key in reliability_keys):
            return 1.0
        if any(key in metric for key in latency_keys):
            return 0.05
        return 0.25

    return 0.5


def _dashboard_prior_score(metric_name: str, dashboard_queries: List[str]) -> float:
    if not dashboard_queries:
        return 0.0
    found = any(metric_name in query for query in dashboard_queries)
    return 1.0 if found else 0.0


def _dimension_fit_score(required: List[str], available: List[str]) -> float:
    if not required:
        return 0.8
    if not available:
        return 0.0
    req = {item.lower() for item in required}
    have = {item.lower() for item in available}
    return len(req & have) / max(len(req), 1)


def _semantic_overlap_score(sli: SLIItem, signal: MetricSignal) -> float:
    sli_tokens = set(_tokens(f"{sli.sli_name} {sli.measurement} {sli.sli_type}"))
    signal_tokens = set(_tokens(f"{signal.name} {signal.description} {' '.join(signal.semantic_tags)}"))
    if not sli_tokens:
        return 0.0
    return len(sli_tokens & signal_tokens) / len(sli_tokens)


def _score_candidate(sli: SLIItem, signal: MetricSignal, dashboard_queries: List[str]) -> float:
    semantic = _semantic_overlap_score(sli, signal)
    type_fit = _type_fit_score(sli.sli_type, signal.name)
    dim_fit = _dimension_fit_score(sli.dimensions, signal.dimensions)
    dashboard_prior = _dashboard_prior_score(signal.name, dashboard_queries)

    score = (semantic * 0.35) + (type_fit * 0.25) + (dim_fit * 0.25) + (dashboard_prior * 0.15)

    stype = sli.sli_type.lower()
    metric = signal.name.lower()
    if "latency" in stype:
        if signal.datasource == "tempo":
            score += 0.12
        if any(key in metric for key in ["latency", "duration", "bucket", "p95", "p99", "ms", "seconds"]):
            score += 0.1
        if any(key in metric for key in ["good_total", "success_total", "error_total", "requests_total"]):
            score -= 0.2

    if any(key in stype for key in ["availability", "correctness", "completeness"]):
        if any(key in metric for key in ["success", "error", "good", "bad", "availability", "correct", "complete"]):
            score += 0.08
        if "request" in metric and not any(key in metric for key in ["success", "error", "good", "bad"]):
            score -= 0.1

    return min(max(score, 0.0), 1.0)


def choose_mapping(
    sli: SLIItem,
    candidates: List[MetricSignal],
    dashboard_queries: List[str],
) -> Tuple[MetricMapping, Dict[str, MetricSignal]]:
    if not candidates:
        return (
            MetricMapping(
                sli_name=sli.sli_name,
                candidate_metrics=[],
                chosen_metric="",
                datasource="prometheus",
                query_template="",
                dimensions=sli.dimensions,
                confidence=0.0,
                missing_gap="missing_instrumentation",
            ),
            {},
        )

    scored = [(signal, _score_candidate(sli, signal, dashboard_queries)) for signal in candidates]
    scored.sort(key=lambda item: item[1], reverse=True)

    top_signal, top_score = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else 0.0

    confidence = top_score
    if second_score and (top_score - second_score) < 0.08:
        confidence = max(0.0, confidence - 0.1)

    query_template = build_query_template(sli, top_signal)

    candidate_names = [signal.name for signal, _ in scored[:10]]
    signal_map = {signal.name: signal for signal, _ in scored}

    mapping = MetricMapping(
        sli_name=sli.sli_name,
        candidate_metrics=candidate_names,
        chosen_metric=top_signal.name,
        datasource=top_signal.datasource,
        query_template=query_template,
        dimensions=top_signal.dimensions or sli.dimensions,
        confidence=round(confidence, 3),
        missing_gap="none",
    )

    return mapping, signal_map
