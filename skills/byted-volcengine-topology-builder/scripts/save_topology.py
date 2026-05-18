#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from topology_constants import (
    BUSINESS_ROOT_DIR,
    TOPOLOGY_JSON_FILE_NAME,
    TOPOLOGY_MD_FILE_NAME,
)


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def normalize_business_key(raw: str) -> str:
    value = (raw or "").strip().lower()
    if not value:
        raise ValueError("business_key 不能为空")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
        raise ValueError(
            "business_key 必须是英文小写 + 数字 + 中划线，例如 payment-core"
        )
    return value


def node_label(node: Dict[str, Any]) -> str:
    node_id = str(node.get("id") or "").strip()
    node_type = str(node.get("type") or "").strip()
    name = str(node.get("name") or "").strip()
    metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
    workload = str(metadata.get("workload") or "").strip().lower()
    type_display = {
        "eip": "EIP",
        "clb": "CLB",
        "alb": "ALB",
        "natgateway": "NATGateway",
        "listener": "监听器",
        "server_group": "后端服务器组",
        "ecs": "ECS",
        "eni": "ENI",
        "ip": "IP",
        "rds_mysql": "RDS MySQL",
        "redis": "Redis",
        "ebs": "EBS",
        "security_group": "安全组",
        "vpc": "VPC",
        "subnet": "子网",
        "project": "项目",
    }.get(node_type, node_type or "node")
    if node_type == "eni" and workload == "vke":
        type_display = "VKE ENI"

    # 展示优先使用实例 ID，避免资源名称重复导致误判；
    # 仅 EIP 保留公网 IP 作为更可读的主展示值。
    if node_type == "eip" and name and name != node_id:
        return f"{type_display}:{name} ({node_id})"
    if node_type == "project":
        return f"{type_display}:{name or node_id}"
    return f"{type_display}:{node_id}"


def render_topology_md(topology: Dict[str, Any]) -> str:
    nodes = topology.get("nodes") if isinstance(topology.get("nodes"), list) else []
    chains = topology.get("chains") if isinstance(topology.get("chains"), dict) else {}
    region = topology.get("region")
    nodes_by_id: Dict[str, Dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "").strip()
        if node_id:
            nodes_by_id[node_id] = node

    def label_from_id(node_id: str, fallback_type: str = "") -> str:
        node = nodes_by_id.get(node_id)
        if node:
            return node_label(node)
        return f"{fallback_type or 'node'}:{node_id}"

    def render_path(path: List[Dict[str, Any]]) -> str:
        parts: List[str] = []
        for item in path:
            if not isinstance(item, dict):
                continue
            parts.append(
                label_from_id(
                    str(item.get("id") or "").strip(),
                    str(item.get("type") or "").strip(),
                )
            )
        return " -> ".join(parts)

    lines: List[str] = []
    lines.append("# Topology")
    if region:
        lines.append("")
        lines.append(f"- region: `{region}`")
    lines.append(f"- nodes: `{len(nodes)}`")
    lines.append(f"- chains: `{len(chains)}`")

    lines.append("")
    lines.append("## Chains")
    if not chains:
        lines.append("- (empty)")
    else:
        for entry_id, chain in sorted(chains.items()):
            if not isinstance(chain, dict):
                continue
            lines.append("")
            lines.append(f"{entry_id}: {label_from_id(entry_id)}")
            route_views: List[tuple[str, Dict[str, Any]]] = []
            if isinstance(chain.get("path"), list):
                path = chain.get("path") if isinstance(chain.get("path"), list) else []
                contexts = (
                    chain.get("contexts")
                    if isinstance(chain.get("contexts"), dict)
                    else {}
                )
                target_id = ""
                if path and isinstance(path[-1], dict):
                    target_id = str(path[-1].get("id") or "").strip()
                if target_id:
                    route_views = [(target_id, {"path": path, "contexts": contexts})]
            else:
                route_views = [
                    (target_id, route)
                    for target_id, route in sorted(chain.items())
                    if isinstance(route, dict)
                ]

            show_route_key = len(route_views) > 1
            for target_id, route in route_views:
                path = route.get("path") if isinstance(route.get("path"), list) else []
                route_text = render_path(path)
                if route_text:
                    if not show_route_key:
                        lines.append(f"  path: {route_text}")
                    else:
                        lines.append(f"  route[{target_id}]: {route_text}")
                contexts = (
                    route.get("contexts")
                    if isinstance(route.get("contexts"), dict)
                    else {}
                )
                for context_node_id, context_groups in contexts.items():
                    if not isinstance(context_groups, dict) or not context_groups:
                        continue
                    parts = []
                    for group_name, items in context_groups.items():
                        if not isinstance(items, list) or not items:
                            continue
                        labels = [
                            label_from_id(str(item), group_name) for item in items
                        ]
                        if labels:
                            parts.append(f"{group_name}={', '.join(labels)}")
                    if parts:
                        lines.append(
                            f"  context[{label_from_id(str(context_node_id))}]: {'; '.join(parts)}"
                        )

    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "将 "
            f"{TOPOLOGY_JSON_FILE_NAME} "
            f"落盘到当前工作空间的 {BUSINESS_ROOT_DIR}/<business>/"
        )
    )
    parser.add_argument(
        "--business",
        required=True,
        help="业务标识（英文小写中划线），例如 payment-core",
    )
    parser.add_argument(
        "--topology-file", required=True, help="输入 topology.json 文件路径"
    )
    parser.add_argument(
        "--root",
        default=BUSINESS_ROOT_DIR,
        help=f"输出根目录（默认当前工作空间 {BUSINESS_ROOT_DIR}）",
    )
    parser.add_argument(
        "--skip-render-graph",
        action="store_true",
        help=(
            f"只保存 {TOPOLOGY_JSON_FILE_NAME}/{TOPOLOGY_MD_FILE_NAME}，"
            "不额外生成 topology.dot/svg/png"
        ),
    )
    parser.add_argument(
        "--graph-layout",
        default="dot",
        help="Graphviz 布局引擎，默认 dot；仅在渲染图片时使用",
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
    parser.add_argument("--output", choices=["json"], default="json")
    parser.set_defaults(context_as_attributes=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    business_key = normalize_business_key(args.business)
    script_dir = Path(__file__).resolve().parent

    topology = load_json(args.topology_file)
    if not isinstance(topology, dict) or topology.get("version") not in {
        "0.1",
        "0.2",
        "0.3",
        "0.4",
        "0.5",
        "0.6",
        "0.7",
    }:
        raise ValueError(
            "topology-file 不是合法 version 0.1/0.2/0.3/0.4/0.5/0.6/0.7 拓扑"
        )

    out_dir = os.path.abspath(os.path.join(args.root, business_key))
    ensure_dir(out_dir)

    out_json = os.path.join(out_dir, TOPOLOGY_JSON_FILE_NAME)
    out_md = os.path.join(out_dir, TOPOLOGY_MD_FILE_NAME)

    with open(out_json, "w", encoding="utf-8") as file_obj:
        file_obj.write(dump_json(topology) + "\n")

    with open(out_md, "w", encoding="utf-8") as file_obj:
        file_obj.write(render_topology_md(topology))

    result: Dict[str, Any] = {
        "business": business_key,
        "output_dir": out_dir,
        "topology_json": out_json,
        "topology_md": out_md,
        "topology_dot": None,
        "topology_svg": None,
        "topology_png": None,
        "graphviz_available": False,
    }

    # 这里把“保存”和“渲染”分层：即使本地没装 Graphviz，也至少输出 DOT 供后续查看或二次转换。
    if not args.skip_render_graph:
        render_cmd = [
            "python3",
            str(script_dir / "render_topology_graph.py"),
            "--topology-file",
            out_json,
            "--output-dir",
            out_dir,
            "--layout",
            args.graph_layout,
        ]
        if args.context_as_attributes:
            render_cmd.append("--context-as-attributes")
        if args.report_style:
            render_cmd.append("--report-style")
        render_completed = subprocess.run(
            render_cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        render_result = json.loads(render_completed.stdout)
        result.update(
            {
                "topology_dot": render_result.get("topology_dot"),
                "topology_svg": render_result.get("topology_svg"),
                "topology_png": render_result.get("topology_png"),
                "graphviz_available": bool(render_result.get("graphviz_available")),
                "graphviz_engine": render_result.get("graphviz_engine"),
                "graphviz_engine_path": render_result.get("graphviz_engine_path"),
                "context_as_attributes": bool(
                    render_result.get("context_as_attributes")
                ),
                "report_style": bool(render_result.get("report_style")),
            }
        )

    print(dump_json(result))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        print(dump_json({"error": "render_graph_failed", "returncode": exc.returncode}))
        sys.exit(exc.returncode)
    except Exception as exc:
        print(dump_json({"error": str(exc)}))
        sys.exit(1)
