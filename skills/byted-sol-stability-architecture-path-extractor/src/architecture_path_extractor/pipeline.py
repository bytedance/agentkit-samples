# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
from typing import List

from .classifier import classify_paths
from .extractors.api_parser import parse_api_signals
from .extractors.config_parser import parse_config_signals
from .extractors.dependency_parser import parse_dependency_signals
from .extractors.doc_diagram_parser import parse_doc_diagram_signals
from .extractors.repo_scanner import scan_repo_files
from .inputs import build_input_bundle
from .models import TopologyModel
from .observability_gap import find_observability_gaps
from .path_builder import build_dependency_graph, build_request_and_async_paths, build_service_graph
from .risk_analyzer import find_failure_points


def run_pipeline(repo: str, product_docs: List[str], arch_diagrams: List[str]) -> TopologyModel:
    bundle = build_input_bundle(repo=repo, product_docs=product_docs, arch_diagrams=arch_diagrams)
    files = scan_repo_files(bundle.repo_path)

    config_signals = parse_config_signals(files)
    api_signals = parse_api_signals(files)
    dep_signals = parse_dependency_signals(files)
    doc_signals = parse_doc_diagram_signals(bundle.product_docs, kind="product_doc")
    diagram_signals = parse_doc_diagram_signals(bundle.arch_diagrams, kind="arch_diagram")

    signals = config_signals + api_signals + dep_signals + doc_signals + diagram_signals

    nodes, edges = build_service_graph(signals)
    dependency_graph = build_dependency_graph(signals)
    path_records = classify_paths(signals)
    request_paths, async_paths = build_request_and_async_paths(path_records, signals)
    failures = find_failure_points(dependency_graph, request_paths)
    gaps = find_observability_gaps(failures, request_paths, async_paths)

    model = TopologyModel(
        service_graph={
            "nodes": [
                {"id": n.node_id, "type": n.node_type, "name": n.name, "attributes": n.attributes}
                for n in nodes
            ],
            "edges": [
                {"source": e.source, "target": e.target, "edge_type": e.edge_type, "evidence": e.evidence}
                for e in edges
            ],
        },
        request_paths=request_paths,
        async_paths=async_paths,
        dependency_graph=dependency_graph,
        failure_points=[
            {
                "component": f.component,
                "risk": f.risk,
                "impact": f.impact,
                "evidence": f.evidence,
            }
            for f in failures
        ],
        observability_hook_points=[
            {
                "component": g.component,
                "gap_type": g.gap_type,
                "missing_signal": g.missing_signal,
                "suggestion": g.suggestion,
                "evidence": g.evidence,
            }
            for g in gaps
        ],
        metadata={
            "repo": str(bundle.repo_path),
            "signals": str(len(signals)),
            "docs": str(len(bundle.product_docs)),
            "diagrams": str(len(bundle.arch_diagrams)),
        },
    )
    return model
