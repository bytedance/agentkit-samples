#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from typing import Callable

if __package__ in (None, ""):
    from _bootstrap import ensure_package

    ensure_package()
    from _byted_volcengine_vmp_scripts.vmp_client import VMPClient  # type: ignore
else:
    from .vmp_client import VMPClient


Handler = Callable[[VMPClient, argparse.Namespace], dict]


def _build_common_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--ak", help="火山引擎 Access Key")
    parser.add_argument("--sk", help="火山引擎 Secret Key")
    parser.add_argument("--region", default=os.getenv("VOLCENGINE_REGION", "cn-beijing"), help="地域")
    parser.add_argument("--endpoint", help="自定义 VMP Endpoint")
    parser.add_argument("--session-token", help="临时凭证 Session Token")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    return parser


def build_list_workspaces_parser() -> argparse.ArgumentParser:
    return _build_common_parser("查询 VMP 工作区列表")


def build_metric_names_parser() -> argparse.ArgumentParser:
    parser = _build_common_parser("查询指标名称列表")
    parser.add_argument("--workspace-id", "-w", required=True, help="工作区 ID")
    parser.add_argument("--match", "-m", help="PromQL 匹配条件")
    return parser


def build_metric_labels_parser() -> argparse.ArgumentParser:
    parser = _build_common_parser("查询指标标签列表")
    parser.add_argument("--workspace-id", "-w", required=True, help="工作区 ID")
    parser.add_argument("--metric-name", "-m", required=True, help="指标名称")
    return parser


def build_query_metrics_parser() -> argparse.ArgumentParser:
    parser = _build_common_parser("即时查询 VMP Metrics")
    parser.add_argument("--workspace-id", "-w", required=True, help="工作区 ID")
    parser.add_argument("--query", "-q", required=True, help="PromQL 查询语句")
    parser.add_argument("--time", "-t", help="查询时间，支持 RFC3339 或 Unix 时间戳")
    return parser


def build_query_range_metrics_parser() -> argparse.ArgumentParser:
    parser = _build_common_parser("范围查询 VMP Metrics")
    parser.add_argument("--workspace-id", "-w", required=True, help="工作区 ID")
    parser.add_argument("--query", "-q", required=True, help="PromQL 查询语句")
    parser.add_argument("--start", "-s", required=True, help="开始时间")
    parser.add_argument("--end", "-e", required=True, help="结束时间")
    parser.add_argument("--step", help="查询步长")
    return parser


def _create_client(args: argparse.Namespace) -> VMPClient:
    return VMPClient(
        ak=args.ak,
        sk=args.sk,
        region=args.region,
        endpoint=args.endpoint,
        session_token=args.session_token,
    )


def _print_result(result: dict, json_output: bool) -> None:
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if json_output:
        print(text)
        return
    print(text)


def run_with_client(parser: argparse.ArgumentParser, handler: Handler) -> None:
    args = parser.parse_args()
    try:
        client = _create_client(args)
        result = handler(client, args)
        _print_result(result, args.json)
    except Exception as exc:
        error_payload = {"error": str(exc), "type": exc.__class__.__name__}
        print(json.dumps(error_payload, indent=2, ensure_ascii=False))
        raise SystemExit(2)
