# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from .models import MetricSignal, SLIItem


def _derive_total_metric(metric_name: str) -> str:
    metric = metric_name.lower()
    if metric.endswith("_success_total"):
        return f"{metric_name[:-14]}_total"
    if metric.endswith("_good_total"):
        return f"{metric_name[:-11]}_total"
    if metric.endswith("_error_total"):
        return f"{metric_name[:-12]}_total"
    if metric.endswith("_bad_total"):
        return f"{metric_name[:-10]}_total"
    return metric_name


def build_query_template(sli: SLIItem, signal: MetricSignal) -> str:
    stype = sli.sli_type.lower()
    metric = signal.name

    if signal.datasource == "tempo":
        if signal.query_template:
            return signal.query_template
        return f"quantile_over_time(0.95, {{{metric}=~\".+\"}}[5m])"

    if "latency" in stype:
        bucket_metric = metric if metric.endswith("_bucket") else f"{metric}_bucket"
        return f"histogram_quantile(0.95, sum(rate({bucket_metric}[5m])) by (le, service))"

    if any(key in stype for key in ["availability", "correctness", "completeness"]):
        denominator_metric = _derive_total_metric(metric)
        return (
            f"sum(rate({metric}[5m])) / "
            f"clamp_min(sum(rate({denominator_metric}[5m])), 1)"
        )

    return f"sum(rate({metric}[5m]))"
