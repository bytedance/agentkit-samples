#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from sdk_runtime import DEFAULT_REGION
from topology_constants import (
    ASSETS_SNAPSHOT_FILE_NAME,
    BUSINESS_ROOT_DIR,
    DEFAULT_BUSINESS_KEY,
    DEFAULT_ENTRY_TYPES,
    DEFAULT_ENV_FILE_NAME,
    DEFAULT_INCLUDE_TYPES,
    TOPOLOGY_JSON_FILE_NAME,
)


def parse_csv(values: Optional[List[str]]) -> List[str]:
    result: List[str] = []
    for raw in values or []:
        for item in (raw or "").split(","):
            normalized = item.strip()
            if normalized:
                result.append(normalized)
    return result


def run(cmd: List[str], cwd: str) -> None:
    # 逐步执行每一层产物生成，确保任一步失败都能及时暴露出来。
    subprocess.run(cmd, cwd=cwd, check=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="一键生成基础资产快照与拓扑视图（快照 -> 构图 -> 落盘/画图）"
    )
    parser.add_argument(
        "--env-path",
        default=None,
        help="AK/SK 的 .env 路径；不传则默认读取工作空间根目录下的 .env",
    )
    parser.add_argument(
        "--region",
        default=DEFAULT_REGION,
        help=f"地域，默认 {DEFAULT_REGION}",
    )
    parser.add_argument(
        "--business",
        default=DEFAULT_BUSINESS_KEY,
        help=f"业务或资产视图标识（business_key），默认 {DEFAULT_BUSINESS_KEY}",
    )
    parser.add_argument(
        "--workspace-root",
        default=os.getcwd(),
        help="工作空间根目录；输出目录和默认 .env 都基于这个目录计算",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help=(
            "需要采集的资源类型，可重复传入或用逗号分隔。"
            f"默认 {','.join(DEFAULT_INCLUDE_TYPES)}"
        ),
    )
    parser.add_argument(
        "--project",
        action="append",
        default=[],
        help="按火山引擎项目组过滤，可重复传入或用逗号分隔；不传默认不过滤",
    )
    parser.add_argument(
        "--entry",
        action="append",
        default=[],
        help=(
            "构图时优先使用的入口资源类型，可重复传入或用逗号分隔。"
            f"默认 {','.join(DEFAULT_ENTRY_TYPES)}"
        ),
    )
    parser.add_argument(
        "--skip-render-graph",
        action="store_true",
        help="只生成结构化产物，不额外输出 DOT/SVG/PNG",
    )
    parser.add_argument(
        "--context-as-attributes",
        action="store_true",
        help="渲染图时将 security_group/subnet/vpc/ebs 作为所属节点标签属性展示",
    )
    parser.add_argument(
        "--context-as-nodes",
        action="store_false",
        dest="context_as_attributes",
        help="渲染图时将 security_group/subnet/vpc/ebs 恢复为独立节点和关系边展示",
    )
    parser.add_argument(
        "--report-style",
        action="store_true",
        help="渲染图时使用更偏汇报图的极简样式",
    )
    parser.set_defaults(context_as_attributes=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace_root = os.path.abspath(os.path.expanduser(args.workspace_root))
    env_path = args.env_path or os.path.join(workspace_root, DEFAULT_ENV_FILE_NAME)
    script_dir = Path(__file__).resolve().parent

    include = parse_csv(args.include) or DEFAULT_INCLUDE_TYPES
    project_names = parse_csv(args.project)
    entries = parse_csv(args.entry) or DEFAULT_ENTRY_TYPES

    out_dir = os.path.join(workspace_root, BUSINESS_ROOT_DIR, args.business)
    os.makedirs(out_dir, exist_ok=True)

    assets_file = os.path.join(out_dir, ASSETS_SNAPSHOT_FILE_NAME)
    topology_file = os.path.join(out_dir, TOPOLOGY_JSON_FILE_NAME)
    topology_root = os.path.join(workspace_root, BUSINESS_ROOT_DIR)

    dump_cmd = [
        "python3",
        str(script_dir / "dump_account_assets.py"),
        "--region",
        args.region,
        "--env-path",
        env_path,
        "--output-file",
        assets_file,
        "--include",
        ",".join(include),
    ]
    for project_name in project_names:
        dump_cmd.extend(["--project", project_name])
    run(dump_cmd, cwd=workspace_root)

    build_cmd = [
        "python3",
        str(script_dir / "build_topology_from_account_assets.py"),
        "--assets-file",
        assets_file,
        "--region",
        args.region,
        "--output-file",
        topology_file,
    ]
    for entry in entries:
        build_cmd.extend(["--entry", entry])
    run(build_cmd, cwd=workspace_root)

    save_cmd = [
        "python3",
        str(script_dir / "save_topology.py"),
        "--business",
        args.business,
        "--topology-file",
        topology_file,
        "--root",
        topology_root,
    ]
    if args.skip_render_graph:
        save_cmd.append("--skip-render-graph")
    if args.context_as_attributes:
        save_cmd.append("--context-as-attributes")
    if args.report_style:
        save_cmd.append("--report-style")
    run(save_cmd, cwd=workspace_root)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        print(f'{{"error":"command failed","returncode":{exc.returncode}}}')
        sys.exit(exc.returncode)
