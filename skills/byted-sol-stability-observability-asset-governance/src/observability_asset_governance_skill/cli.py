# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from .pipeline import PipelineOptions, run_pipeline


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run observability asset governance pipeline")
    parser.add_argument("--sli-spec", required=True, help="Path to SLI spec JSON")
    parser.add_argument("--architecture-spec", required=True, help="Path to architecture spec JSON or directory")
    parser.add_argument("--metric-mapping-spec", required=True, help="Path to metric mapping spec JSON")
    parser.add_argument("--existing-dashboard", required=True, help="Path to existing dashboard JSON")
    parser.add_argument("--metrics-catalog", default="", help="Optional path to metrics catalog JSON")
    parser.add_argument("--usage-stats", default="", help="Optional path to usage stats JSON")
    parser.add_argument("--asset-registry", default="", help="Optional path to existing asset registry JSON")
    parser.add_argument("--grafana-url", default="", help="Optional Grafana base URL")
    parser.add_argument("--grafana-token", default="", help="Optional Grafana token")
    parser.add_argument("--prom-url", default="", help="Optional Prometheus base URL")
    parser.add_argument("--prom-bearer", default="", help="Optional Prometheus bearer token")
    parser.add_argument("--prom-username", default="", help="Optional Prometheus basic auth username")
    parser.add_argument("--prom-password", default="", help="Optional Prometheus basic auth password")
    parser.add_argument("--out-dir", default="output", help="Output base directory")
    parser.add_argument("--focus-service", default="", help="Optional focus service")
    parser.add_argument("--offline", action="store_true", help="Run with offline-only semantics")
    return parser


def _assert_exists(path_value: str, label: str) -> None:
    if not Path(path_value).exists():
        raise SystemExit(f"{label} not found: {path_value}")


def run_cli(argv: List[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    _assert_exists(args.sli_spec, "--sli-spec")
    _assert_exists(args.architecture_spec, "--architecture-spec")
    _assert_exists(args.metric_mapping_spec, "--metric-mapping-spec")
    _assert_exists(args.existing_dashboard, "--existing-dashboard")

    if args.metrics_catalog:
        _assert_exists(args.metrics_catalog, "--metrics-catalog")
    if args.usage_stats:
        _assert_exists(args.usage_stats, "--usage-stats")
    if args.asset_registry:
        _assert_exists(args.asset_registry, "--asset-registry")

    result = run_pipeline(
        sli_spec=args.sli_spec,
        architecture_spec=args.architecture_spec,
        metric_mapping_spec=args.metric_mapping_spec,
        existing_dashboard=args.existing_dashboard,
        metrics_catalog=args.metrics_catalog or None,
        usage_stats=args.usage_stats or None,
        asset_registry=args.asset_registry or None,
        options=PipelineOptions(
            out_dir=args.out_dir,
            focus_service=args.focus_service or None,
            offline=args.offline,
            grafana_url=args.grafana_url,
            grafana_token=args.grafana_token,
            prom_url=args.prom_url,
            prom_bearer=args.prom_bearer,
            prom_username=args.prom_username,
            prom_password=args.prom_password,
        ),
    )

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
