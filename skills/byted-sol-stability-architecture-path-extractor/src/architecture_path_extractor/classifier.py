# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import List

from .models import PathRecord, Signal


def classify_paths(signals: List[Signal]) -> List[PathRecord]:
    values = "\n".join([s.value + "\n" + s.evidence for s in signals]).lower()

    user_hops = ["login/auth", "create-space", "create-agent", "model-gateway", "tool-gateway", "return-result"]
    control_hops = ["config-change", "resource-dispatch", "permission-check", "rate-limit/quota", "audit"]
    data_hops = ["request-entry", "session-service", "orchestrator", "model-gateway", "tool-gateway", "memory/retrieval", "sandbox/browser", "persistence"]

    if "session" not in values:
        data_hops = ["request-entry", "orchestrator", "model-gateway", "persistence"]

    return [
        PathRecord(category="core_user_link", name="core_user_link", hops=user_hops, evidence=[s.source_file for s in signals[:5]]),
        PathRecord(category="control_plane_link", name="control_plane_link", hops=control_hops, evidence=[s.source_file for s in signals[:5]]),
        PathRecord(category="data_plane_link", name="data_plane_link", hops=data_hops, evidence=[s.source_file for s in signals[:8]]),
    ]
