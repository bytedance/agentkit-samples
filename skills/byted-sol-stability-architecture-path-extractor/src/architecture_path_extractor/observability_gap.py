# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import List

from .models import FailurePoint, ObservabilityGap


def find_observability_gaps(failures: List[FailurePoint], request_paths: List[dict], async_paths: List[dict]) -> List[ObservabilityGap]:
    gaps: List[ObservabilityGap] = []

    for f in failures:
        gaps.append(
            ObservabilityGap(
                component=f.component,
                gap_type="metric",
                missing_signal=f"{f.component}_availability or saturation",
                suggestion=f"add RED + saturation metrics for {f.component}",
                evidence=f.evidence,
            )
        )

    if request_paths:
        gaps.append(
            ObservabilityGap(
                component="request_path",
                gap_type="trace",
                missing_signal="end-to-end trace span across core user path",
                suggestion="add trace span propagation at gateway/orchestrator/model/tool boundaries",
                evidence=request_paths[0].get("evidence", [])[:3],
            )
        )

    if async_paths:
        gaps.append(
            ObservabilityGap(
                component="async_path",
                gap_type="log",
                missing_signal="producer-consumer correlation id logging",
                suggestion="add structured logs with correlation_id for async producer/consumer",
                evidence=async_paths[0].get("evidence", [])[:3],
            )
        )

    gaps.append(
        ObservabilityGap(
            component="control_plane",
            gap_type="audit",
            missing_signal="config change and permission-check audit trail",
            suggestion="add immutable audit events for config changes, quota and permission decisions",
            evidence=[],
        )
    )

    return gaps
