# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Dict, List

from .models import GovernanceFinding, NormalizedGovernanceInputs


def _query_fingerprint(query: str) -> str:
    normalized = " ".join(query.lower().split())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def detect_duplicate_dashboards(inputs: NormalizedGovernanceInputs) -> Dict[str, object]:
    findings: List[GovernanceFinding] = []
    by_fingerprint: Dict[str, List[int]] = defaultdict(list)

    for panel in inputs.panel_targets:
        by_fingerprint[_query_fingerprint(panel.query)].append(panel.panel_id)

    for fingerprint, panel_ids in by_fingerprint.items():
        if len(panel_ids) < 3:
            continue
        findings.append(
            GovernanceFinding(
                category="duplicate_dashboard",
                finding_type="high_query_duplication",
                severity="warning",
                message=f"multiple panels share identical query fingerprint ({len(panel_ids)} panels)",
                recommendation="consolidate duplicated panels or split by distinct dimensions",
                owner="unassigned",
                asset_refs=[f"fingerprint:{fingerprint}"] + [f"panel:{item}" for item in sorted(set(panel_ids))],
            )
        )

    return {
        "summary": {
            "total_findings": len(findings),
            "warnings": len(findings),
            "errors": 0,
        },
        "findings": [item.to_dict() for item in findings],
    }
