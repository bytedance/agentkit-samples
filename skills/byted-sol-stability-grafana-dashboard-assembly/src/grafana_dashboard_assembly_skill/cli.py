# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from .pipeline import PipelineOptions, run_pipeline


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Assemble and integration-validate Grafana dashboard JSON")
    parser.add_argument("--sli-spec", required=True, help="Path to SLI spec JSON")
    parser.add_argument("--metric-mapping-spec", required=True, help="Path to metric mapping spec JSON")
    parser.add_argument("--metrics-catalog", required=True, help="Path to metrics catalog JSON")
    parser.add_argument("--log-dict", required=True, help="Path to log field dictionary JSON")
    parser.add_argument("--trace-spans", required=True, help="Path to trace span names JSON")
    parser.add_argument("--existing-dashboard", required=True, help="Path to existing dashboard JSON")
    parser.add_argument("--grafana-url", default="", help="Grafana base URL")
    parser.add_argument("--grafana-token", default="", help="Grafana token")
    parser.add_argument("--datasource-uid", default="", help="Grafana datasource uid")
    parser.add_argument("--prom-url", default="", help="Prometheus base URL")
    parser.add_argument("--prom-bearer", default="", help="Prometheus bearer token")
    parser.add_argument("--prom-username", default="", help="Prometheus basic auth username")
    parser.add_argument("--prom-password", default="", help="Prometheus basic auth password")
    parser.add_argument("--time-range", default="now-6h,now", help="Time range like now-6h,now")
    parser.add_argument("--out-dir", default="output", help="Output base directory")
    parser.add_argument("--focus-service", help="Optional focus service")
    parser.add_argument("--offline", action="store_true", help="Use local checks only")
    parser.add_argument("--max-repair-rounds", type=int, default=2, help="Auto-repair rounds")
    return parser


def run_cli(argv: List[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    required_paths = [
        Path(args.sli_spec),
        Path(args.metric_mapping_spec),
        Path(args.metrics_catalog),
        Path(args.log_dict),
        Path(args.trace_spans),
        Path(args.existing_dashboard),
    ]
    for path in required_paths:
        if not path.exists():
            raise SystemExit(f"required path not found: {path}")

    result = run_pipeline(
        sli_spec=args.sli_spec,
        metric_mapping_spec=args.metric_mapping_spec,
        metrics_catalog=args.metrics_catalog,
        log_dict=args.log_dict,
        trace_spans=args.trace_spans,
        existing_dashboard=args.existing_dashboard,
        options=PipelineOptions(
            out_dir=args.out_dir,
            focus_service=args.focus_service,
            offline=args.offline,
            grafana_url=args.grafana_url,
            grafana_token=args.grafana_token,
            datasource_uid=args.datasource_uid,
            prom_url=args.prom_url,
            prom_bearer=args.prom_bearer,
            prom_username=args.prom_username,
            prom_password=args.prom_password,
            time_range=args.time_range,
            max_repair_rounds=max(1, args.max_repair_rounds),
        ),
    )

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
