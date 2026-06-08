# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Dict, List

from .models import GraphEdge, GraphNode, PathRecord, Signal


def build_service_graph(signals: List[Signal]) -> tuple[List[GraphNode], List[GraphEdge]]:
    services = sorted({s.value for s in signals if s.kind == "service"})
    if not services:
        services = ["request-entry", "session-service", "orchestrator", "model-gateway", "tool-gateway", "persistence"]

    nodes: List[GraphNode] = [GraphNode(node_id=f"svc:{x}", node_type="service", name=x) for x in services]
    edges: List[GraphEdge] = []
    for i in range(len(services) - 1):
        edges.append(
            GraphEdge(
                source=f"svc:{services[i]}",
                target=f"svc:{services[i + 1]}",
                edge_type="call",
                evidence="service adjacency from config/order",
            )
        )
    return nodes, edges


def build_dependency_graph(signals: List[Signal]) -> Dict[str, List[Dict[str, str]]]:
    out: Dict[str, List[Dict[str, str]]] = {
        "db": [],
        "cache": [],
        "mq": [],
        "third_party": [],
    }
    for s in signals:
        v = s.value.lower()
        item = {"name": s.value, "source": s.source_file}
        if s.kind == "mq" or any(k in v for k in ["kafka", "rabbitmq", "queue", "topic", "sqs", "pubsub"]):
            out["mq"].append(item)
        elif any(k in v for k in ["postgres", "mysql", "mongo", "dynamodb", "sqlite"]):
            out["db"].append(item)
        elif any(k in v for k in ["redis", "memcached", "cache"]):
            out["cache"].append(item)
        elif s.kind in {"third_party", "db_or_cache", "dependency_hint"}:
            out["third_party"].append(item)

    for key in out:
        seen = set()
        deduped = []
        for item in out[key]:
            name = item["name"]
            if name in seen:
                continue
            seen.add(name)
            deduped.append(item)
        out[key] = deduped
    return out


def build_request_and_async_paths(path_records: List[PathRecord], signals: List[Signal]) -> tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    request_paths: List[Dict[str, object]] = []
    async_paths: List[Dict[str, object]] = []
    for p in path_records:
        if p.category in {"core_user_link", "data_plane_link"}:
            request_paths.append({"name": p.name, "hops": p.hops, "evidence": p.evidence})

    mq_hits = [s for s in signals if s.kind == "mq" or "queue" in s.value.lower() or "topic" in s.value.lower()]
    if mq_hits:
        async_paths.append(
            {
                "name": "async_dependency_path",
                "hops": ["producer", "mq/topic", "consumer", "persistence"],
                "evidence": [x.source_file for x in mq_hits[:8]],
            }
        )
    return request_paths, async_paths
