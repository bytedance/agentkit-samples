# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, Iterable, List

from .models import SLISpec, SLIType, Severity


@dataclass
class ModelerResult:
    specs: List[SLISpec]
    notes: List[str]


def _extract_key_values(text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower().replace("-", "_").replace(" ", "_")
        value = value.strip()
        if key and value:
            result[key] = value
    return result


def _infer_sli_type(text: str) -> SLIType:
    low = text.lower()
    if any(x in low for x in ["latency", "p95", "p99", "duration", "耗时", "延迟"]):
        return SLIType.LATENCY
    if any(x in low for x in ["correct", "accuracy", "正确", "错误率", "error rate"]):
        return SLIType.CORRECTNESS
    if any(x in low for x in ["fresh", "时效", "新鲜", "lag"]):
        return SLIType.FRESHNESS
    if any(x in low for x in ["complete", "coverage", "完整", "丢失"]):
        return SLIType.COMPLETENESS
    if any(x in low for x in ["consistent", "一致", "一致性"]):
        return SLIType.CONSISTENCY
    return SLIType.AVAILABILITY


def _looks_like_internal_resource_metric(text: str) -> bool:
    low = text.lower()
    resource_hints = ("cpu", "ram", "storage", "throughput", "loadavg")
    return any(x in low for x in resource_hints)


def _infer_severity(text: str) -> Severity:
    m = re.search(r"\bP([012])\b", text.upper())
    if not m:
        return Severity.P1
    return {"0": Severity.P0, "1": Severity.P1, "2": Severity.P2}[m.group(1)]


def _read_refs(paths: Iterable[str]) -> str:
    chunks: List[str] = []
    for raw in paths:
        p = Path(raw)
        if not p.exists() or p.is_dir():
            continue
        try:
            chunks.append(p.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    return "\n".join(chunks)


def build_sli_specs(input_text: str, owner: str, reference_paths: Iterable[str] = ()) -> ModelerResult:
    if not input_text.strip():
        raise ValueError("input text cannot be empty")
    if not owner.strip():
        raise ValueError("owner cannot be empty")

    ref_text = _read_refs(reference_paths)
    merged = "\n".join([input_text, ref_text])
    kv = _extract_key_values(input_text)

    capability = kv.get("capability") or input_text.strip().splitlines()[0].strip()[:120]
    user_journey = kv.get("user_journey") or "service request handling"
    sli_type = kv.get("sli_type") or _infer_sli_type(merged).value
    severity = kv.get("severity") or _infer_severity(merged).value

    sli_name = kv.get("sli_name") or f"{capability} {sli_type}"
    measurement = kv.get("measurement")
    denominator = kv.get("denominator")

    if not measurement:
        if sli_type == SLIType.LATENCY.value:
            measurement = "good_requests_under_300ms / total_requests"
        elif sli_type == SLIType.CORRECTNESS.value:
            measurement = "correct_responses / processed_requests"
        elif sli_type == SLIType.FRESHNESS.value:
            measurement = "records_within_freshness_window / expected_records"
        else:
            measurement = "successful_requests / total_requests"

    if _looks_like_internal_resource_metric(measurement):
        raise ValueError("measurement must be user-facing, not internal resource metric")

    if not denominator:
        if sli_type in {SLIType.FRESHNESS.value, SLIType.COMPLETENESS.value}:
            denominator = "expected_records"
        elif sli_type == SLIType.CORRECTNESS.value:
            denominator = "processed_requests"
        else:
            denominator = "total_requests"

    dimension = kv.get("dimension") or "service,region"
    target_slo = kv.get("target_slo") or (
        "99.0% requests under threshold / rolling 30d"
        if sli_type == SLIType.LATENCY.value
        else "99.9% / rolling 30d"
    )
    error_budget = kv.get("error_budget") or (
        "1.0% / 30d"
        if sli_type == SLIType.LATENCY.value
        else "0.1% / 30d"
    )

    spec = SLISpec(
        capability=capability,
        user_journey=user_journey,
        sli_name=sli_name,
        sli_type=sli_type,
        measurement=measurement,
        denominator=denominator,
        dimension=dimension,
        target_slo=target_slo,
        error_budget=error_budget,
        severity=severity,
        owner=kv.get("owner") or owner,
    )

    notes: List[str] = []
    if "sli_type" not in kv:
        notes.append(f"inferred sli_type={spec.sli_type.value}")
    if "severity" not in kv:
        notes.append(f"inferred severity={spec.severity.value}")
    if "target_slo" not in kv:
        notes.append("defaulted target_slo to rolling 30d window")
    if "measurement" not in kv:
        notes.append("defaulted to user-facing request/data quality ratio")

    return ModelerResult(specs=[spec], notes=notes)
