#!/usr/bin/env python3
from __future__ import annotations

if __package__ in (None, ""):
    from _bootstrap import ensure_package

    ensure_package()
    from _byted_volcengine_vmp_scripts.cli_common import build_query_range_metrics_parser, run_with_client  # type: ignore
else:
    from .cli_common import build_query_range_metrics_parser, run_with_client


def _handle(client, args):
    return client.query_range_metrics(args.workspace_id, args.query, args.start, args.end, args.step)


def main() -> None:
    run_with_client(build_query_range_metrics_parser(), _handle)


if __name__ == "__main__":
    main()
