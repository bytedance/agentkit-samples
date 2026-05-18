#!/usr/bin/env python3
import argparse
import html
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from topology_constants import (
    TOPOLOGY_DOT_FILE_NAME,
    TOPOLOGY_JSON_FILE_NAME,
    TOPOLOGY_PNG_FILE_NAME,
    TOPOLOGY_SVG_FILE_NAME,
)

ATTRIBUTE_CONTEXT_TYPES = {"project", "security_group", "subnet", "vpc", "ebs"}
ATTRIBUTE_CONTEXT_ORDER = ["project", "vpc", "subnet", "security_group", "ebs"]
ATTRIBUTE_CONTEXT_DISPLAY = {
    "project": "Project",
    "security_group": "SG",
    "subnet": "Subnet",
    "vpc": "VPC",
    "ebs": "EBS",
}
REPORT_HIDDEN_NODE_TYPES = ATTRIBUTE_CONTEXT_TYPES | {"listener", "server_group"}
BACKEND_NODE_TYPES = {"ecs", "eni", "ip"}
REPORT_VISIBLE_PATH_TYPES = {
    "eip",
    "clb",
    "alb",
    "natgateway",
    "rds_mysql",
    "redis",
} | BACKEND_NODE_TYPES


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def normalize(value: Any) -> str:
    return str(value or "").strip()


def dot_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def html_escape(value: str) -> str:
    return html.escape(value, quote=True)


def node_primary_value(node: Dict[str, Any]) -> str:
    node_id = normalize(node.get("id"))
    node_type = normalize(node.get("type"))
    name = normalize(node.get("name"))
    metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}

    # EIP 优先展示公网 IP；其他资源仍以实例 ID 为主，避免名称重复带来歧义。
    primary_value = node_id
    if node_type == "eip":
        primary_value = normalize(metadata.get("public_ip")) or name or node_id
    elif node_type == "listener":
        primary_value = name or node_id
    return primary_value


def node_label(node: Dict[str, Any], extra_lines: Optional[List[str]] = None) -> str:
    node_id = normalize(node.get("id"))
    node_type = normalize(node.get("type"))
    name = normalize(node.get("name"))
    metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
    workload = normalize(metadata.get("workload")).lower()
    type_display = {
        "eip": "EIP",
        "clb": "CLB",
        "alb": "ALB",
        "natgateway": "NATGateway",
        "listener": "Listener",
        "server_group": "Server Group",
        "ecs": "ECS",
        "eni": "ENI",
        "ip": "IP",
        "rds_mysql": "RDS MySQL",
        "redis": "Redis",
        "ebs": "EBS",
        "security_group": "Security Group",
        "vpc": "VPC",
        "subnet": "Subnet",
        "project": "Project",
    }.get(node_type, node_type or "Node")
    if node_type == "eni" and workload == "vke":
        type_display = "VKE ENI"
    primary_value = node_primary_value(node)

    lines = [type_display, primary_value]
    if name and name not in {primary_value, node_id}:
        lines.append(name)
    if extra_lines:
        lines.extend(extra_lines)
    # Graphviz label 需要真实换行符，不能把 "\n" 当作字面量写进 DOT。
    return "\n".join(item for item in lines if item)


def compact_text(value: str, keep: int = 8) -> str:
    normalized = normalize(value)
    if len(normalized) <= 24:
        return normalized
    prefix, _, suffix = normalized.partition("-")
    if suffix:
        return f"{prefix}-...{suffix[-keep:]}"
    return normalized[:12] + "..." + normalized[-keep:]


def node_title_and_subtitle(node: Dict[str, Any]) -> Tuple[str, str]:
    node_id = normalize(node.get("id"))
    node_type = normalize(node.get("type"))
    name = normalize(node.get("name"))
    primary_value = node_primary_value(node)

    if node_type == "eip":
        title = primary_value or name or node_id
        subtitle = node_id if node_id and node_id != title else ""
        return title, subtitle

    if name and name not in {primary_value, node_id}:
        return name, primary_value or node_id
    return primary_value or name or node_id, ""


def collect_route_views(chain: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = chain.get("path")
    contexts = chain.get("contexts")
    if isinstance(path, list) and path:
        return [
            {
                "path": path,
                "contexts": contexts if isinstance(contexts, dict) else {},
            }
        ]
    return [route for route in chain.values() if isinstance(route, dict)]


def build_relations(
    topology: Dict[str, Any],
    hidden_context_types: Optional[Set[str]] = None,
) -> List[Dict[str, str]]:
    chains = topology.get("chains")
    relations: List[Dict[str, str]] = []
    hidden_context_types = hidden_context_types or set()

    def add_relation(frm: Any, to: Any, relation: Any) -> None:
        normalized_from = normalize(frm)
        normalized_to = normalize(to)
        normalized_relation = normalize(relation)
        if not normalized_from or not normalized_to or not normalized_relation:
            return
        relations.append(
            {
                "from": normalized_from,
                "to": normalized_to,
                "relation": normalized_relation,
            }
        )

    if not isinstance(chains, dict):
        return relations

    context_relation_by_type = {
        "project": "belongs_to",
        "security_group": "belongs_to",
        "subnet": "belongs_to",
        "vpc": "belongs_to",
        "ebs": "attached_to",
        "listener": "has",
    }

    for chain in chains.values():
        if not isinstance(chain, dict):
            continue
        for route in collect_route_views(chain):
            path = route.get("path")
            if isinstance(path, list):
                for index in range(1, len(path)):
                    current = path[index]
                    previous = path[index - 1]
                    if not isinstance(current, dict) or not isinstance(previous, dict):
                        continue
                    add_relation(
                        previous.get("id", ""),
                        current.get("id", ""),
                        current.get("relation", ""),
                    )

            contexts = route.get("contexts")
            if isinstance(contexts, dict):
                for context_node_id, context_groups in contexts.items():
                    node_id = normalize(context_node_id)
                    if not node_id or not isinstance(context_groups, dict):
                        continue
                    for context_type, items in context_groups.items():
                        normalized_context_type = normalize(context_type)
                        if normalized_context_type in hidden_context_types:
                            continue
                        relation = context_relation_by_type.get(
                            normalized_context_type, ""
                        )
                        if not relation or not isinstance(items, list):
                            continue
                        for item in items:
                            if isinstance(item, dict):
                                add_relation(node_id, item.get("id", ""), relation)
                            else:
                                add_relation(node_id, item, relation)

    deduped: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str, str]] = set()
    for relation in relations:
        key = (relation["from"], relation["to"], relation["relation"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(relation)
    return deduped


def node_style(node_type: str) -> Dict[str, str]:
    styles = {
        "eip": {
            "shape": "box",
            "fillcolor": "#DBEAFE",
            "color": "#2563EB",
        },
        "clb": {
            "shape": "box",
            "fillcolor": "#E0E7FF",
            "color": "#4F46E5",
        },
        "alb": {
            "shape": "box",
            "fillcolor": "#E0E7FF",
            "color": "#4F46E5",
        },
        "natgateway": {
            "shape": "box",
            "fillcolor": "#EDE9FE",
            "color": "#7C3AED",
        },
        "listener": {
            "shape": "component",
            "fillcolor": "#F3E8FF",
            "color": "#9333EA",
        },
        "server_group": {
            "shape": "folder",
            "fillcolor": "#FEF3C7",
            "color": "#D97706",
        },
        "ecs": {
            "shape": "box3d",
            "fillcolor": "#DCFCE7",
            "color": "#16A34A",
        },
        "rds_mysql": {
            "shape": "box3d",
            "fillcolor": "#FDE68A",
            "color": "#B45309",
        },
        "redis": {
            "shape": "box3d",
            "fillcolor": "#FECACA",
            "color": "#DC2626",
        },
        "eni": {
            "shape": "box3d",
            "fillcolor": "#DBEAFE",
            "color": "#2563EB",
        },
        "ip": {
            "shape": "box",
            "fillcolor": "#E0F2FE",
            "color": "#0284C7",
        },
        "security_group": {
            "shape": "hexagon",
            "fillcolor": "#FCE7F3",
            "color": "#DB2777",
        },
        "subnet": {
            "shape": "tab",
            "fillcolor": "#FDE68A",
            "color": "#B45309",
        },
        "vpc": {
            "shape": "tab",
            "fillcolor": "#FDE68A",
            "color": "#92400E",
        },
        "project": {
            "shape": "folder",
            "fillcolor": "#E0F2FE",
            "color": "#0369A1",
        },
        "ebs": {
            "shape": "cylinder",
            "fillcolor": "#E5E7EB",
            "color": "#4B5563",
        },
    }
    return styles.get(
        node_type,
        {
            "shape": "box",
            "fillcolor": "#F3F4F6",
            "color": "#6B7280",
        },
    )


def edge_style(relation: str) -> Dict[str, str]:
    if relation == "belongs_to":
        return {"color": "#EC4899", "style": "dashed"}
    if relation == "attached_to":
        return {"color": "#2563EB", "style": "solid"}
    if relation == "has":
        return {"color": "#7C3AED", "style": "solid"}
    if relation == "contains":
        return {"color": "#16A34A", "style": "bold"}
    return {"color": "#6B7280", "style": "solid"}


def report_edge_style() -> Dict[str, str]:
    return {"color": "#3B82F6", "style": "solid", "penwidth": "2.2"}


def build_attribute_context_lines(
    topology: Dict[str, Any],
    nodes_by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, List[str]]:
    chains = topology.get("chains")
    if not isinstance(chains, dict):
        return {}

    owner_contexts: Dict[str, Dict[str, List[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    seen_values: Dict[Tuple[str, str], Set[str]] = defaultdict(set)

    # 仅在紧凑模式下把上下文资源聚合到主节点标签中，避免主链路过长。
    for chain in chains.values():
        if not isinstance(chain, dict):
            continue
        for route in collect_route_views(chain):
            contexts = route.get("contexts")
            if not isinstance(contexts, dict):
                continue
            for owner_id, context_groups in contexts.items():
                normalized_owner_id = normalize(owner_id)
                if not normalized_owner_id or not isinstance(context_groups, dict):
                    continue
                for context_type in ATTRIBUTE_CONTEXT_ORDER:
                    items = context_groups.get(context_type)
                    if not isinstance(items, list):
                        continue
                    for item in items:
                        target_id = (
                            normalize(item.get("id"))
                            if isinstance(item, dict)
                            else normalize(item)
                        )
                        if not target_id:
                            continue
                        dedupe_key = (normalized_owner_id, context_type)
                        if target_id in seen_values[dedupe_key]:
                            continue
                        seen_values[dedupe_key].add(target_id)
                        target_node = nodes_by_id.get(target_id)
                        target_value = node_primary_value(
                            target_node or {"id": target_id, "type": context_type}
                        )
                        owner_contexts[normalized_owner_id][context_type].append(
                            target_value
                        )

    attribute_lines: Dict[str, List[str]] = {}
    for owner_id, grouped_values in owner_contexts.items():
        lines: List[str] = []
        for context_type in ATTRIBUTE_CONTEXT_ORDER:
            values = grouped_values.get(context_type)
            if values:
                lines.append(
                    f'{ATTRIBUTE_CONTEXT_DISPLAY[context_type]}: {", ".join(values)}'
                )
        if lines:
            attribute_lines[owner_id] = lines
    return attribute_lines


def build_attribute_context_groups(
    topology: Dict[str, Any],
    nodes_by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, List[str]]]:
    chains = topology.get("chains")
    if not isinstance(chains, dict):
        return {}

    owner_contexts: Dict[str, Dict[str, List[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    seen_values: Dict[Tuple[str, str], Set[str]] = defaultdict(set)

    # 仅在紧凑模式下把上下文资源聚合到主节点标签中，避免主链路过长。
    for chain in chains.values():
        if not isinstance(chain, dict):
            continue
        for route in collect_route_views(chain):
            contexts = route.get("contexts")
            if not isinstance(contexts, dict):
                continue
            for owner_id, context_groups in contexts.items():
                normalized_owner_id = normalize(owner_id)
                if not normalized_owner_id or not isinstance(context_groups, dict):
                    continue
                for context_type in ATTRIBUTE_CONTEXT_ORDER:
                    items = context_groups.get(context_type)
                    if not isinstance(items, list):
                        continue
                    for item in items:
                        target_id = (
                            normalize(item.get("id"))
                            if isinstance(item, dict)
                            else normalize(item)
                        )
                        if not target_id:
                            continue
                        dedupe_key = (normalized_owner_id, context_type)
                        if target_id in seen_values[dedupe_key]:
                            continue
                        seen_values[dedupe_key].add(target_id)
                        target_node = nodes_by_id.get(target_id)
                        target_value = node_primary_value(
                            target_node or {"id": target_id, "type": context_type}
                        )
                        owner_contexts[normalized_owner_id][context_type].append(
                            target_value
                        )

    return {
        owner_id: dict(grouped_values)
        for owner_id, grouped_values in owner_contexts.items()
    }


def compact_node_label_html(
    node: Dict[str, Any],
    style: Dict[str, str],
    context_groups: Optional[Dict[str, List[str]]] = None,
) -> str:
    node_type = normalize(node.get("type"))
    metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
    workload = normalize(metadata.get("workload")).lower()
    type_display = {
        "eip": "EIP",
        "clb": "CLB",
        "alb": "ALB",
        "natgateway": "NATGateway",
        "listener": "Listener",
        "server_group": "Server Group",
        "ecs": "ECS",
        "eni": "ENI",
        "ip": "IP",
        "ebs": "EBS",
        "security_group": "Security Group",
        "vpc": "VPC",
        "subnet": "Subnet",
    }.get(node_type, node_type or "Node")
    if node_type == "eni" and workload == "vke":
        type_display = "VKE ENI"
    title, subtitle = node_title_and_subtitle(node)
    rows = [
        '<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="6" COLOR="{border}" BGCOLOR="white">'.format(
            border=html_escape(style["color"])
        ),
        (
            '<TR><TD ALIGN="LEFT" BGCOLOR="{bg}" COLOR="{border}">'
            '<FONT POINT-SIZE="10"><B>{type_display}</B></FONT></TD></TR>'
        ).format(
            bg=html_escape(style["fillcolor"]),
            border=html_escape(style["color"]),
            type_display=html_escape(type_display),
        ),
        (
            '<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="13"><B>{title}</B></FONT></TD></TR>'
        ).format(title=html_escape(title)),
    ]
    if subtitle:
        rows.append(
            '<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="9" COLOR="#64748B">{subtitle}</FONT></TD></TR>'.format(
                subtitle=html_escape(compact_text(subtitle))
            )
        )

    for context_type in ATTRIBUTE_CONTEXT_ORDER:
        values = (context_groups or {}).get(context_type)
        if not values:
            continue
        rows.append(
            (
                '<TR><TD ALIGN="LEFT" BGCOLOR="#F8FAFC">'
                '<FONT POINT-SIZE="9" COLOR="#64748B">{label}</FONT>'
                '<FONT POINT-SIZE="10">  {value}</FONT></TD></TR>'
            ).format(
                label=html_escape(ATTRIBUTE_CONTEXT_DISPLAY[context_type]),
                value=html_escape(", ".join(compact_text(item) for item in values)),
            )
        )

    rows.append("</TABLE>")
    return "<" + "".join(rows) + ">"


def attribute_card_label_html(
    context_groups: Optional[Dict[str, List[str]]] = None,
) -> str:
    rows = [
        '<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="6" COLOR="#CBD5E1" BGCOLOR="#F8FAFC">',
        '<TR><TD ALIGN="LEFT" BGCOLOR="#EEF2FF"><FONT POINT-SIZE="9" COLOR="#475569"><B>Context</B></FONT></TD></TR>',
    ]
    for context_type in ATTRIBUTE_CONTEXT_ORDER:
        values = (context_groups or {}).get(context_type)
        if not values:
            continue
        rows.append(
            (
                '<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="9" COLOR="#64748B">{label}</FONT>'
                '<FONT POINT-SIZE="10">  {value}</FONT></TD></TR>'
            ).format(
                label=html_escape(ATTRIBUTE_CONTEXT_DISPLAY[context_type]),
                value=html_escape(", ".join(compact_text(item) for item in values)),
            )
        )
    rows.append("</TABLE>")
    return "<" + "".join(rows) + ">"


def report_node_label_html(
    node: Dict[str, Any],
    style: Dict[str, str],
    context_groups: Optional[Dict[str, List[str]]] = None,
) -> str:
    node_type = normalize(node.get("type"))
    metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
    workload = normalize(metadata.get("workload")).lower()
    type_display = {
        "eip": "Internet Entry" if node_type == "eip" else "Entry",
        "clb": "Load Balancer",
        "alb": "Load Balancer",
        "natgateway": "NAT Gateway",
        "ecs": "Compute",
        "rds_mysql": "MySQL",
        "redis": "Redis",
        "eni": "ENI Backend",
        "ip": "IP Backend",
    }.get(node_type, node_type.upper() or "Node")
    if node_type == "eni" and workload == "vke":
        type_display = "VKE Backend"
    title, subtitle = node_title_and_subtitle(node)
    attribute_parts: List[str] = []
    for context_type in ATTRIBUTE_CONTEXT_ORDER:
        values = (context_groups or {}).get(context_type)
        if values:
            attribute_parts.append(
                f'{ATTRIBUTE_CONTEXT_DISPLAY[context_type]}: {", ".join(compact_text(item) for item in values)}'
            )
    attrs_line = " | ".join(attribute_parts)

    rows = [
        '<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="0">',
        (
            '<TR><TD><TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="10" '
            'COLOR="{border}" BGCOLOR="white">'
        ).format(border=html_escape(style["color"])),
        (
            '<TR><TD ALIGN="LEFT" BGCOLOR="{bg}"><FONT POINT-SIZE="10" COLOR="{border}"><B>{kind}</B></FONT></TD></TR>'
        ).format(
            bg=html_escape(style["fillcolor"]),
            border=html_escape(style["color"]),
            kind=html_escape(type_display),
        ),
        '<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="16"><B>{title}</B></FONT></TD></TR>'.format(
            title=html_escape(title)
        ),
    ]
    if subtitle:
        rows.append(
            '<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="9" COLOR="#64748B">{subtitle}</FONT></TD></TR>'.format(
                subtitle=html_escape(compact_text(subtitle))
            )
        )
    if attrs_line:
        rows.append(
            '<TR><TD ALIGN="LEFT" BGCOLOR="#F8FAFC"><FONT POINT-SIZE="9" COLOR="#475569">{attrs}</FONT></TD></TR>'.format(
                attrs=html_escape(attrs_line)
            )
        )
    rows.extend(["</TABLE></TD></TR>", "</TABLE>"])
    return "<" + "".join(rows) + ">"


def build_report_relations(topology: Dict[str, Any]) -> List[Dict[str, str]]:
    chains = topology.get("chains")
    if not isinstance(chains, dict):
        return []

    relations: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str, str]] = set()

    def add(frm: str, to: str, relation: str) -> None:
        normalized = (normalize(frm), normalize(to), normalize(relation))
        if not all(normalized[:2]) or normalized[0] == normalized[1]:
            return
        if normalized in seen:
            return
        seen.add(normalized)
        relations.append(
            {"from": normalized[0], "to": normalized[1], "relation": normalized[2]}
        )

    for chain in chains.values():
        if not isinstance(chain, dict):
            continue
        for route in collect_route_views(chain):
            path = route.get("path")
            if not isinstance(path, list):
                continue
            visible_nodes = [
                item
                for item in path
                if isinstance(item, dict)
                and normalize(item.get("type")) in REPORT_VISIBLE_PATH_TYPES
            ]
            for index in range(1, len(visible_nodes)):
                previous = visible_nodes[index - 1]
                current = visible_nodes[index]
                current_type = normalize(current.get("type"))
                relation = "main_flow"
                if current_type in BACKEND_NODE_TYPES:
                    relation = "to_compute"
                elif current_type in {"clb", "alb", "natgateway"}:
                    relation = "to_service"
                add(
                    str(previous.get("id") or ""),
                    str(current.get("id") or ""),
                    relation,
                )
    return relations


def render_dot(
    topology: Dict[str, Any],
    context_as_attributes: bool = True,
    report_style: bool = False,
) -> str:
    nodes = topology.get("nodes") if isinstance(topology.get("nodes"), list) else []
    nodes_by_id: Dict[str, Dict[str, Any]] = {}
    type_groups: Dict[str, List[str]] = defaultdict(list)
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = normalize(node.get("id"))
        if not node_id:
            continue
        nodes_by_id[node_id] = node
        type_groups[normalize(node.get("type"))].append(node_id)
    effective_context_as_attributes = context_as_attributes or report_style
    attribute_context_groups = (
        build_attribute_context_groups(topology, nodes_by_id)
        if effective_context_as_attributes
        else {}
    )

    lines: List[str] = [
        "digraph topology {",
        (
            '  graph [rankdir=LR, splines=ortho, overlap=false, pad="0.45", nodesep="0.6", ranksep="1.0"];'
            if report_style
            else '  graph [rankdir=LR, splines=true, overlap=false, pad="0.35", nodesep="0.45", ranksep="0.85"];'
        ),
        '  node [fontname="Helvetica", fontsize=11, shape=box, style="rounded,filled", margin="0.12,0.08"];',
        (
            '  edge [fontname="Helvetica", fontsize=10, arrowsize=0.8];'
            if report_style
            else '  edge [fontname="Helvetica", fontsize=10, arrowsize=0.7];'
        ),
    ]

    for node_id in sorted(nodes_by_id):
        node = nodes_by_id[node_id]
        node_type = normalize(node.get("type"))
        if report_style and node_type in REPORT_HIDDEN_NODE_TYPES:
            continue
        if effective_context_as_attributes and node_type in ATTRIBUTE_CONTEXT_TYPES:
            continue
        style = node_style(node_type)
        if report_style:
            lines.append(
                "  "
                + dot_quote(node_id)
                + " [shape=plain, margin=0, label="
                + report_node_label_html(
                    node, style, attribute_context_groups.get(node_id)
                )
                + "];"
            )
            continue
        lines.append(
            "  "
            + dot_quote(node_id)
            + " [label="
            + dot_quote(node_label(node))
            + ", shape="
            + dot_quote(style["shape"])
            + ", fillcolor="
            + dot_quote(style["fillcolor"])
            + ", color="
            + dot_quote(style["color"])
            + "];"
        )

    if effective_context_as_attributes and not report_style:
        # 主节点保持第一版形态；上下文信息放到侧边小卡片里，兼顾可读性和版面整洁。
        for owner_id in sorted(attribute_context_groups):
            if owner_id not in nodes_by_id:
                continue
            card_id = f"{owner_id}::__context_card"
            lines.append(
                "  "
                + dot_quote(card_id)
                + " [shape=plain, margin=0, label="
                + attribute_card_label_html(attribute_context_groups.get(owner_id))
                + "];"
            )
            lines.append(
                "  "
                + dot_quote(owner_id)
                + " -> "
                + dot_quote(card_id)
                + ' [color="#94A3B8", style="dashed", arrowhead="none", constraint=false];'
            )
            lines.append(
                "  { rank=same; "
                + dot_quote(owner_id)
                + "; "
                + dot_quote(card_id)
                + "; }"
            )

    # 用 rank 把主链路节点大致放在相近层级，避免默认布局过度散开。
    rank_buckets: List[Tuple[str, Iterable[str]]] = (
        [
            ("entry", type_groups.get("eip", []) + type_groups.get("natgateway", [])),
            ("lb", type_groups.get("clb", []) + type_groups.get("alb", [])),
            (
                "compute",
                type_groups.get("ecs", [])
                + type_groups.get("rds_mysql", [])
                + type_groups.get("redis", [])
                + type_groups.get("eni", [])
                + type_groups.get("ip", []),
            ),
        ]
        if report_style
        else [
            ("entry", type_groups.get("eip", []) + type_groups.get("natgateway", [])),
            (
                "lb",
                type_groups.get("clb", [])
                + type_groups.get("alb", [])
                + type_groups.get("listener", []),
            ),
            ("group", type_groups.get("server_group", [])),
            (
                "compute",
                type_groups.get("ecs", [])
                + type_groups.get("rds_mysql", [])
                + type_groups.get("redis", [])
                + type_groups.get("eni", [])
                + type_groups.get("ip", []),
            ),
        ]
    )
    for _, bucket in rank_buckets:
        filtered_bucket = [
            item
            for item in sorted(set(bucket))
            if normalize((nodes_by_id.get(item) or {}).get("type"))
            not in (REPORT_HIDDEN_NODE_TYPES if report_style else set())
        ]
        bucket_items = [dot_quote(item) for item in filtered_bucket]
        if bucket_items:
            lines.append("  { rank=same; " + "; ".join(bucket_items) + "; }")

    hidden_context_types = (
        ATTRIBUTE_CONTEXT_TYPES if effective_context_as_attributes else set()
    )
    relations = (
        build_report_relations(topology)
        if report_style
        else build_relations(topology, hidden_context_types=hidden_context_types)
    )
    for relation in relations:
        style = (
            report_edge_style() if report_style else edge_style(relation["relation"])
        )
        lines.append(
            "  "
            + dot_quote(relation["from"])
            + " -> "
            + dot_quote(relation["to"])
            + " [color="
            + dot_quote(style["color"])
            + ", style="
            + dot_quote(style["style"])
            + (", penwidth=" + dot_quote(style["penwidth"]) if report_style else "")
            + ("" if report_style else ", label=" + dot_quote(relation["relation"]))
            + "];"
        )

    lines.append("}")
    return "\n".join(lines) + "\n"


def render_with_graphviz(
    engine: str, dot_file: str, output_file: str, output_format: str
) -> None:
    subprocess.run(
        [engine, f"-T{output_format}", dot_file, "-o", output_file],
        check=True,
    )


def candidate_install_commands() -> List[List[str]]:
    # 按常见包管理器顺序尝试安装 Graphviz。
    commands: List[List[str]] = []
    if shutil.which("brew"):
        commands.append(["brew", "install", "graphviz"])
    if shutil.which("apt-get"):
        commands.append(["sudo", "apt-get", "update"])
        commands.append(["sudo", "apt-get", "install", "-y", "graphviz"])
    elif shutil.which("apt"):
        commands.append(["sudo", "apt", "update"])
        commands.append(["sudo", "apt", "install", "-y", "graphviz"])
    if shutil.which("dnf"):
        commands.append(["sudo", "dnf", "install", "-y", "graphviz"])
    if shutil.which("yum"):
        commands.append(["sudo", "yum", "install", "-y", "graphviz"])
    if shutil.which("apk"):
        commands.append(["sudo", "apk", "add", "graphviz"])
    return commands


def try_install_graphviz() -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    for command in candidate_install_commands():
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
            return {
                "installed": True,
                "attempts": attempts
                + [
                    {
                        "command": command,
                        "returncode": completed.returncode,
                        "stdout": completed.stdout[-2000:],
                        "stderr": completed.stderr[-2000:],
                    }
                ],
            }
        except Exception as exc:
            attempts.append(
                {
                    "command": command,
                    "error": str(exc),
                }
            )
    return {
        "installed": False,
        "attempts": attempts,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            f"将 {TOPOLOGY_JSON_FILE_NAME} 渲染为 DOT/SVG/PNG；"
            "若本机未安装 Graphviz，则至少输出 DOT。"
        )
    )
    parser.add_argument(
        "--topology-file",
        required=True,
        help=f"输入 {TOPOLOGY_JSON_FILE_NAME} 文件路径",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=f"输出目录；默认使用 {TOPOLOGY_JSON_FILE_NAME} 所在目录",
    )
    parser.add_argument("--layout", default="dot", help="Graphviz 布局引擎，默认 dot")
    parser.add_argument(
        "--context-as-attributes",
        action="store_true",
        help="将 security_group/subnet/vpc/ebs 作为所属节点标签属性展示，而不是单独渲染为节点",
    )
    parser.add_argument(
        "--context-as-nodes",
        action="store_false",
        dest="context_as_attributes",
        help="将 security_group/subnet/vpc/ebs 恢复为独立节点和关系边展示",
    )
    parser.add_argument(
        "--report-style",
        action="store_true",
        help="生成更偏汇报图的极简样式，默认折叠 listener/server_group 并隐藏边标签",
    )
    parser.add_argument(
        "--skip-auto-install-graphviz",
        action="store_true",
        help="未检测到 Graphviz 时，不尝试自动安装，直接降级只输出 DOT",
    )
    parser.add_argument("--output", choices=["json"], default="json")
    parser.set_defaults(context_as_attributes=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    topology = load_json(args.topology_file)
    if not isinstance(topology, dict):
        raise ValueError("topology-file 不是合法 JSON 对象")

    output_dir = os.path.abspath(
        os.path.expanduser(
            args.output_dir or os.path.dirname(args.topology_file) or "."
        )
    )
    ensure_dir(output_dir)

    dot_file = os.path.join(output_dir, TOPOLOGY_DOT_FILE_NAME)
    svg_file = os.path.join(output_dir, TOPOLOGY_SVG_FILE_NAME)
    png_file = os.path.join(output_dir, TOPOLOGY_PNG_FILE_NAME)

    with open(dot_file, "w", encoding="utf-8") as file_obj:
        file_obj.write(
            render_dot(
                topology,
                context_as_attributes=args.context_as_attributes,
                report_style=args.report_style,
            )
        )

    engine_path = shutil.which(args.layout)
    install_result: Optional[Dict[str, Any]] = None
    if not engine_path and not args.skip_auto_install_graphviz:
        # 优先尝试自动安装；安装失败也不抛错，继续走 DOT 降级路径。
        install_result = try_install_graphviz()
        engine_path = shutil.which(args.layout)

    result: Dict[str, Any] = {
        "graphviz_available": bool(engine_path),
        "graphviz_engine": args.layout,
        "graphviz_engine_path": engine_path,
        "graphviz_install_attempted": install_result is not None,
        "graphviz_install_result": install_result,
        "context_as_attributes": args.context_as_attributes,
        "report_style": args.report_style,
        "topology_dot": dot_file,
        "topology_svg": None,
        "topology_png": None,
    }

    # 先稳定产出 DOT；本地装了 Graphviz 时再补渲染图片，不阻断主流程。
    if engine_path:
        render_with_graphviz(args.layout, dot_file, svg_file, "svg")
        render_with_graphviz(args.layout, dot_file, png_file, "png")
        result["topology_svg"] = svg_file
        result["topology_png"] = png_file

    print(dump_json(result))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        print(
            dump_json(
                {
                    "error": "graphviz_render_failed",
                    "returncode": exc.returncode,
                    "command": exc.cmd,
                }
            )
        )
        sys.exit(exc.returncode)
    except Exception as exc:
        print(dump_json({"error": str(exc)}))
        sys.exit(1)
