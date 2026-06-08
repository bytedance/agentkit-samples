# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Dict

from .models import MetricMapping, MetricSignal, SLIItem


def diagnose_gap(sli: SLIItem, mapping: MetricMapping, signal_map: Dict[str, MetricSignal]) -> str:
    if not mapping.candidate_metrics or not mapping.chosen_metric:
        return "missing_instrumentation"

    chosen = signal_map.get(mapping.chosen_metric)
    if chosen is None:
        return "missing_instrumentation"

    required_dims = {item.lower() for item in sli.dimensions}
    available_dims = {item.lower() for item in (chosen.dimensions or mapping.dimensions)}

    if required_dims:
        overlap = required_dims & available_dims
        if not overlap:
            return "missing_label"
        if "service" in required_dims and "service" not in available_dims:
            return "missing_label"
        if len(required_dims) <= 3 and not required_dims.issubset(available_dims):
            return "missing_label"

    sli_type = sli.sli_type.lower()
    query = mapping.query_template.lower()

    if mapping.confidence < 0.5:
        return "missing_aggregation_semantics"

    if "latency" in sli_type:
        if not any(key in query for key in ["histogram_quantile", "quantile", "p95", "p99"]):
            return "missing_aggregation_semantics"

    if any(key in sli_type for key in ["availability", "correctness", "completeness"]):
        if "/" not in query and "ratio" not in query:
            return "missing_aggregation_semantics"

    return "none"
