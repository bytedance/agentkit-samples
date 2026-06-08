# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Dict, List

from .models import FailurePoint


def find_failure_points(dependency_graph: Dict[str, List[Dict[str, str]]], request_paths: List[Dict[str, object]]) -> List[FailurePoint]:
    failures: List[FailurePoint] = []

    if dependency_graph.get("db"):
        failures.append(
            FailurePoint(
                "database",
                "single critical datastore",
                "core read/write path degraded or unavailable",
                evidence=[x.get("source", "") for x in dependency_graph["db"][:3]],
            )
        )

    if dependency_graph.get("mq"):
        failures.append(
            FailurePoint(
                "message-queue",
                "async backlog or broker outage",
                "delayed task execution and eventual user-visible timeout",
                evidence=[x.get("source", "") for x in dependency_graph["mq"][:3]],
            )
        )

    if request_paths:
        failures.append(
            FailurePoint(
                "orchestrator",
                "central orchestration bottleneck",
                "major user journey interruption",
                evidence=request_paths[0].get("evidence", [])[:3],
            )
        )

    return failures
