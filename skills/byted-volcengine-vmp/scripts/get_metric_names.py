#!/usr/bin/env python3
from __future__ import annotations

if __package__ in (None, ""):
    from _bootstrap import ensure_package

    ensure_package()
    from _byted_volcengine_vmp_scripts.cli_common import build_metric_names_parser, run_with_client  # type: ignore
else:
    from .cli_common import build_metric_names_parser, run_with_client


def _handle(client, args):
    return client.query_metric_names(args.workspace_id, args.match)


def main() -> None:
    run_with_client(build_metric_names_parser(), _handle)


if __name__ == "__main__":
    main()
