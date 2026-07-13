#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple

ENTRY_TYPES = {"eip", "clb", "alb", "natgateway"}
PATH_TERMINAL_TYPES = {"eip", "alb", "natgateway"}
INFRA_TYPES = {"security_group", "subnet", "vpc", "ebs"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract structural topology information for change risk analysis."
    )
    parser.add_argument("--node", required=True, help="Target node id, name, service or keyword.")
    parser.add_argument("--business", help="Optional business directory name.")
    parser.add_argument("--root", help="Optional topology root directory.")
    parser.add_argument(
        "--output",
        choices=("json", "markdown"),
        default="json",
        help="Output format (default json for LLM ingestion).",
    )
    parser.add_argument("--top-k", type=int, default=3, help="Maximum number of matches.")
    parser.add_argument(
        "--max-depth",
        type=int,
        default=6,
        help="Traversal depth limit.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# 拓扑数据加载与节点匹配
# ---------------------------------------------------------------------------


def normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def collect_search_terms(value: Any) -> Set[str]:
    terms: Set[str] = set()
    if value is None:
        return terms
    if isinstance(value, dict):
        for item in value.values():
            terms.update(collect_search_terms(item))
        return terms
    if isinstance(value, (list, tuple, set)):
        for item in value:
            terms.update(collect_search_terms(item))
        return terms
    if isinstance(value, (str, int, float, bool)):
        text = normalize(value)
        if text:
            terms.add(text)
    return terms


def score_node_match(node: Dict[str, Any], query: str) -> Tuple[int, List[str]]:
    normalized_query = normalize(query)
    if not normalized_query:
        return 0, []

    metadata = node.get("metadata", {})
    score = 0
    reasons: List[str] = []

    candidates = [
        (normalize(node.get("id")), 120, 80, "id"),
        (normalize(node.get("name")), 110, 70, "name"),
        (normalize(metadata.get("public_ip")), 115, 75, "public_ip"),
    ]

    for ip in metadata.get("public_ips", []):
        candidates.append((normalize(ip), 115, 75, "public_ip"))
    for ip in metadata.get("private_ips", []):
        candidates.append((normalize(ip), 105, 65, "private_ip"))

    for term in collect_search_terms(metadata):
        if term in {value for value, _, _, _ in candidates}:
            continue
        candidates.append((term, 90, 50, "metadata"))

    for term, exact_score, fuzzy_score, label in candidates:
        if not term:
            continue
        if normalized_query == term:
            score = max(score, exact_score)
            reasons.append(f"{label}:exact")
            continue
        if normalized_query in term:
            score = max(score, fuzzy_score)
            reasons.append(f"{label}:fuzzy")

    unique_reasons: List[str] = []
    seen: Set[str] = set()
    for reason in reasons:
        if reason in seen:
            continue
        seen.add(reason)
        unique_reasons.append(reason)
    return score, unique_reasons


def resolve_root(root_arg: str | None) -> Path:
    if root_arg:
        return Path(root_arg).expanduser().resolve()

    cwd = Path.cwd()
    candidates = [
        cwd / ".trae" / "business_topologies",
        cwd / "business_topologies",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def load_topologies(root: Path, business: str | None) -> List[Dict[str, Any]]:
    if business:
        topology_files = [root / business / "topology.json"]
    else:
        topology_files = sorted(root.glob("*/topology.json"))

    topologies: List[Dict[str, Any]] = []
    for topology_file in topology_files:
        if not topology_file.exists():
            continue
        with topology_file.open("r", encoding="utf-8") as handle:
            topology = json.load(handle)
        topologies.append(
            {
                "business": topology_file.parent.name,
                "topology_file": str(topology_file),
                "topology_md": str(topology_file.with_suffix(".md")),
                "account_assets_snapshot": str(
                    topology_file.parent / "account_assets_snapshot.json"
                ),
                "topology": topology,
            }
        )
    return topologies


def load_account_assets_snapshot(snapshot_path: str) -> Dict[str, Any]:
    path = Path(snapshot_path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_snapshot_ecs_brief(instance: Dict[str, Any]) -> Dict[str, Any]:
    network_interfaces = instance.get("network_interfaces", [])
    private_ips: List[str] = []
    for nic in network_interfaces:
        if not isinstance(nic, dict):
            continue
        primary_ip = normalize(nic.get("primary_ip_address"))
        if primary_ip:
            private_ips.append(primary_ip)

    public_ips: List[str] = []
    eip = instance.get("eip_address")
    if isinstance(eip, dict):
        public_ip = normalize(eip.get("ip_address"))
        if public_ip:
            public_ips.append(public_ip)

    instance_id = str(instance.get("instance_id") or "").strip()
    instance_name = str(instance.get("instance_name") or instance_id).strip()
    return {
        "id": instance_id,
        "type": "ecs",
        "name": instance_name,
        "private_ips": private_ips,
        "public_ips": public_ips,
        "public_ip": public_ips[0] if public_ips else None,
    }


def infer_snapshot_impacted_ecs(
    target: Dict[str, Any], snapshot: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    ecs_items = snapshot.get("ecs_instances", {}).get("items", [])
    if not isinstance(ecs_items, list):
        return {}

    target_id = str(target.get("id") or "").strip()
    target_type = str(target.get("type") or "").strip()
    impacted: Dict[str, Dict[str, Any]] = {}

    for instance in ecs_items:
        if not isinstance(instance, dict):
            continue
        instance_id = str(instance.get("instance_id") or "").strip()
        if not instance_id:
            continue

        network_interfaces = instance.get("network_interfaces", [])
        volumes = instance.get("volumes", [])
        eip = instance.get("eip_address")

        matched = False
        if target_type == "ecs":
            matched = instance_id == target_id
        elif target_type == "security_group":
            matched = any(
                target_id in nic.get("security_group_ids", [])
                for nic in network_interfaces
                if isinstance(nic, dict)
            )
        elif target_type == "subnet":
            matched = any(
                str(nic.get("subnet_id") or "").strip() == target_id
                for nic in network_interfaces
                if isinstance(nic, dict)
            )
        elif target_type == "vpc":
            matched = (
                str(instance.get("vpc_id") or "").strip() == target_id
                or any(
                    str(nic.get("vpc_id") or "").strip() == target_id
                    for nic in network_interfaces
                    if isinstance(nic, dict)
                )
            )
        elif target_type == "ebs":
            matched = any(
                str(volume.get("volume_id") or "").strip() == target_id
                for volume in volumes
                if isinstance(volume, dict)
            )
        elif target_type == "eip" and isinstance(eip, dict):
            matched = str(eip.get("allocation_id") or "").strip() == target_id

        if matched:
            impacted[instance_id] = build_snapshot_ecs_brief(instance)

    return impacted


def match_nodes(topologies: Sequence[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    ranked_matches: List[Dict[str, Any]] = []

    for item in topologies:
        for node in item["topology"].get("nodes", []):
            score, reasons = score_node_match(node, query)
            if score <= 0:
                continue
            ranked_matches.append(
                {
                    "business": item["business"],
                    "topology_file": item["topology_file"],
                    "topology_md": item["topology_md"],
                    "account_assets_snapshot": item["account_assets_snapshot"],
                    "topology": item["topology"],
                    "node": node,
                    "match_score": score,
                    "match_reasons": reasons,
                }
            )

    return sorted(
        ranked_matches,
        key=lambda item: (
            -item["match_score"],
            item["business"],
            item["node"].get("type", ""),
            item["node"].get("id", ""),
        ),
    )


# ---------------------------------------------------------------------------
# 拓扑分析与链路回溯
# ---------------------------------------------------------------------------


def build_graph(topology: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    nodes = {node["id"]: node for node in topology.get("nodes", [])}
    outgoing: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    incoming: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    chains = topology.get("chains")
    relations: List[Dict[str, str]] = []

    def add_relation(frm: str, to: str, relation: str) -> None:
        normalized_from = str(frm or "").strip()
        normalized_to = str(to or "").strip()
        normalized_relation = str(relation or "").strip()
        if not normalized_from or not normalized_to or not normalized_relation:
            return
        relations.append(
            {
                "from": normalized_from,
                "to": normalized_to,
                "relation": normalized_relation,
            }
        )

    if isinstance(chains, dict):
        context_relation_by_type = {
            "security_group": "belongs_to",
            "subnet": "belongs_to",
            "vpc": "belongs_to",
            "ebs": "attached_to",
            "listener": "has",
        }

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
                        add_relation(previous.get("id", ""), current.get("id", ""), current.get("relation", ""))

                contexts = route.get("contexts")
                if isinstance(contexts, dict):
                    for context_node_id, context_groups in contexts.items():
                        node_id = str(context_node_id or "").strip()
                        if not node_id or not isinstance(context_groups, dict):
                            continue
                        for context_type, items in context_groups.items():
                            relation = context_relation_by_type.get(str(context_type), "")
                            if not relation or not isinstance(items, list):
                                continue
                            for item in items:
                                if isinstance(item, dict):
                                    add_relation(node_id, item.get("id", ""), relation)
                                else:
                                    add_relation(node_id, str(item), relation)
                else:
                    ecs_id = ""
                    if isinstance(path, list) and path and isinstance(path[-1], dict):
                        ecs_id = str(path[-1].get("id") or "").strip()
                    attachments = route.get("attachments")
                    if ecs_id and isinstance(attachments, dict):
                        for attachment_type, items in attachments.items():
                            relation = context_relation_by_type.get(str(attachment_type), "")
                            if not relation or not isinstance(items, list):
                                continue
                            for item in items:
                                if isinstance(item, dict):
                                    add_relation(ecs_id, item.get("id", ""), relation)
                                else:
                                    add_relation(ecs_id, str(item), relation)

    seen_relations: Set[Tuple[str, str, str]] = set()
    for relation in relations:
        key = (relation["from"], relation["to"], relation["relation"])
        if key in seen_relations:
            continue
        seen_relations.add(key)
        outgoing[relation["from"]].append(relation)
        incoming[relation["to"]].append(relation)
    return nodes, outgoing, incoming


def find_downstream_ecs(
    start_id: str,
    nodes: Dict[str, Any],
    outgoing: Dict[str, List[Dict[str, Any]]],
    max_depth: int,
) -> Set[str]:
    result: Set[str] = set()
    queue: deque[Tuple[str, int]] = deque([(start_id, 0)])
    visited: Set[str] = {start_id}

    while queue:
        node_id, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for edge in outgoing.get(node_id, []):
            neighbor_id = edge["to"]
            if neighbor_id in visited:
                continue
            visited.add(neighbor_id)
            neighbor = nodes.get(neighbor_id, {})
            if neighbor.get("type") == "ecs":
                result.add(neighbor_id)
            queue.append((neighbor_id, depth + 1))
    return result


def find_impacted_ecs(
    target: Dict[str, Any],
    nodes: Dict[str, Any],
    outgoing: Dict[str, List[Dict[str, Any]]],
    incoming: Dict[str, List[Dict[str, Any]]],
    max_depth: int,
) -> Set[str]:
    node_type = target.get("type")
    target_id = target["id"]

    if node_type == "ecs":
        return {target_id}

    if node_type in ENTRY_TYPES or node_type == "server_group":
        return find_downstream_ecs(target_id, nodes, outgoing, max_depth)

    impacted: Set[str] = set()

    if node_type in INFRA_TYPES:
        for edge in incoming.get(target_id, []):
            if nodes.get(edge["from"], {}).get("type") == "ecs":
                impacted.add(edge["from"])
        return impacted

    for edge in incoming.get(target_id, []):
        if nodes.get(edge["from"], {}).get("type") == "ecs":
            impacted.add(edge["from"])
    for edge in outgoing.get(target_id, []):
        if nodes.get(edge["to"], {}).get("type") == "ecs":
            impacted.add(edge["to"])
    return impacted


def enumerate_upstream_paths(
    ecs_id: str,
    nodes: Dict[str, Any],
    incoming: Dict[str, List[Dict[str, Any]]],
    max_depth: int,
) -> List[List[str]]:
    results: List[List[str]] = []

    def dfs(current_id: str, path: List[str], visited: Set[str], depth: int) -> None:
        current_node = nodes.get(current_id, {})
        current_type = current_node.get("type")
        if depth >= max_depth or current_type in PATH_TERMINAL_TYPES:
            results.append(list(reversed(path)))
            return

        parents = incoming.get(current_id, [])
        if not parents:
            results.append(list(reversed(path)))
            return

        expanded = False
        for edge in parents:
            parent_id = edge["from"]
            if parent_id in visited:
                continue
            expanded = True
            dfs(parent_id, path + [parent_id], visited | {parent_id}, depth + 1)

        if not expanded:
            results.append(list(reversed(path)))

    dfs(ecs_id, [ecs_id], {ecs_id}, 0)

    unique_paths: List[List[str]] = []
    seen: Set[Tuple[str, ...]] = set()
    for path in sorted(results, key=len):
        key = tuple(path)
        if key in seen:
            continue
        seen.add(key)
        unique_paths.append(path)
    return unique_paths


def shortest_undirected_distances(
    start_id: str,
    outgoing: Dict[str, List[Dict[str, Any]]],
    incoming: Dict[str, List[Dict[str, Any]]],
    max_depth: int,
) -> Dict[str, int]:
    distances = {start_id: 0}
    queue: deque[str] = deque([start_id])

    while queue:
        current = queue.popleft()
        depth = distances[current]
        if depth >= max_depth:
            continue

        neighbors = [edge["to"] for edge in outgoing.get(current, [])]
        neighbors.extend(edge["from"] for edge in incoming.get(current, []))

        for neighbor in neighbors:
            if neighbor in distances:
                continue
            distances[neighbor] = depth + 1
            queue.append(neighbor)

    return distances


def node_brief(node: Dict[str, Any]) -> Dict[str, Any]:
    metadata = node.get("metadata", {})
    return {
        "id": node.get("id"),
        "type": node.get("type"),
        "name": node.get("name"),
        "private_ips": metadata.get("private_ips", []),
        "public_ips": metadata.get("public_ips", []),
        "public_ip": metadata.get("public_ip"),
    }


def direct_relations(
    target_id: str,
    nodes: Dict[str, Any],
    outgoing: Dict[str, List[Dict[str, Any]]],
    incoming: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    relations: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, str, str]] = set()
    for edge in outgoing.get(target_id, []):
        key = ("outgoing", str(edge.get("relation")), str(edge.get("to")), "")
        if key in seen:
            continue
        seen.add(key)
        relations.append(
            {
                "direction": "outgoing",
                "relation": edge.get("relation"),
                "neighbor": node_brief(nodes[edge["to"]]),
            }
        )
    for edge in incoming.get(target_id, []):
        key = ("incoming", str(edge.get("relation")), str(edge.get("from")), "")
        if key in seen:
            continue
        seen.add(key)
        relations.append(
            {
                "direction": "incoming",
                "relation": edge.get("relation"),
                "neighbor": node_brief(nodes[edge["from"]]),
            }
        )
    return relations


def analyze_match(match: Dict[str, Any], max_depth: int) -> Dict[str, Any]:
    topology = match["topology"]
    target = match["node"]
    nodes, outgoing, incoming = build_graph(topology)
    snapshot = load_account_assets_snapshot(match["account_assets_snapshot"])

    impacted_ecs_ids = sorted(find_impacted_ecs(target, nodes, outgoing, incoming, max_depth))
    impacted_ecs_map = {
        node_id: node_brief(nodes[node_id]) for node_id in impacted_ecs_ids if node_id in nodes
    }
    for node_id, ecs in infer_snapshot_impacted_ecs(target, snapshot).items():
        impacted_ecs_map.setdefault(node_id, ecs)

    impacted_ecs = [
        impacted_ecs_map[node_id]
        for node_id in sorted(impacted_ecs_map)
    ]

    application_paths: List[List[Dict[str, Any]]] = []
    impacted_ecs_without_entry_paths: List[Dict[str, Any]] = []
    seen_paths: Set[Tuple[str, ...]] = set()
    for ecs in impacted_ecs:
        ecs_id = str(ecs.get("id") or "").strip()
        if ecs_id not in nodes:
            impacted_ecs_without_entry_paths.append(ecs)
            continue

        ecs_has_entry_path = False
        for path in enumerate_upstream_paths(ecs_id, nodes, incoming, max_depth):
            if len(path) <= 1:
                continue
            key = tuple(path)
            if key in seen_paths:
                continue
            seen_paths.add(key)
            ecs_has_entry_path = True
            application_paths.append([node_brief(nodes[node_id]) for node_id in path])
        if not ecs_has_entry_path:
            impacted_ecs_without_entry_paths.append(ecs)

    distances = shortest_undirected_distances(target["id"], outgoing, incoming, 2)
    related_resources: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    related_seen: Set[Tuple[str, str]] = set()
    for node_id, distance in sorted(distances.items(), key=lambda item: (item[1], item[0])):
        if node_id == target["id"] or distance == 0:
            continue
        node = nodes[node_id]
        group = node.get("type", "unknown")
        key = (str(group), str(node_id))
        if key in related_seen:
            continue
        related_seen.add(key)
        related_resources[group].append(node_brief(node))

    return {
        "business": match["business"],
        "topology_file": match["topology_file"],
        "topology_md": match["topology_md"],
        "match_score": match["match_score"],
        "match_reasons": match["match_reasons"],
        "matched_node": node_brief(target),
        "direct_relations": direct_relations(target["id"], nodes, outgoing, incoming),
        "impacted_ecs": impacted_ecs,
        "application_paths": application_paths,
        "impacted_ecs_without_entry_paths": impacted_ecs_without_entry_paths,
        "related_resources": related_resources,
    }


def format_node_ref(node: Dict[str, Any]) -> str:
    node_type = str(node.get("type") or "unknown").strip()
    node_id = str(node.get("id") or "unknown").strip()
    node_name = str(node.get("name") or "").strip()
    if node_name and node_name != node_id:
        return f"{node_type}:{node_id} ({node_name})"
    return f"{node_type}:{node_id}"


def summarize_related_resources(
    related_resources: Dict[str, List[Dict[str, Any]]]
) -> List[str]:
    lines: List[str] = []
    for resource_type in sorted(related_resources):
        items = related_resources[resource_type]
        if not items:
            continue
        refs = [format_node_ref(item) for item in items[:5]]
        suffix = ""
        if len(items) > 5:
            suffix = f" 等 {len(items)} 个"
        lines.append(f"- {resource_type}: {', '.join(refs)}{suffix}")
    return lines


def build_output(result: Dict[str, Any], output_type: str) -> str:
    if output_type == "json":
        return json.dumps(result, ensure_ascii=False, indent=2)

    # 仅输出结构化文字描述，不生成图。
    matches = result.get("matches", [])
    if not matches:
        return f"未在当前拓扑中命中目标 `{result.get('query', '')}`"

    lines = []
    primary = matches[0]
    node = primary.get("matched_node", {})
    lines.append(
        f"### 匹配目标: {format_node_ref(node)} (业务: {primary.get('business')})"
    )
    lines.append(
        f"- 命中依据: {', '.join(primary.get('match_reasons', [])) or '未返回匹配依据'}"
    )

    impacted_ecs = primary.get("impacted_ecs", [])
    lines.append(f"\n**受影响 ECS ({len(impacted_ecs)}台):**")
    if impacted_ecs:
        for ecs in impacted_ecs:
            lines.append(f"- {format_node_ref(ecs)}")
    else:
        lines.append("- 无")

    direct_rels = primary.get("direct_relations", [])
    lines.append(f"\n**直接关联资源 ({len(direct_rels)}个):**")
    if direct_rels:
        for rel in direct_rels:
            neighbor = rel.get("neighbor", {})
            direction = "来自" if rel.get("direction") == "incoming" else "指向"
            relation = rel.get("relation") or "related_to"
            lines.append(f"- {direction} {format_node_ref(neighbor)}，关系为 `{relation}`")
    else:
        lines.append("- 无")

    paths = primary.get("application_paths", [])
    lines.append(f"\n**上游入口链路 ({len(paths)}条):**")
    if paths:
        for i, path in enumerate(paths, 1):
            path_str = " -> ".join(format_node_ref(n) for n in path)
            lines.append(f"{i}. {path_str}")
    else:
        lines.append("- 无可回溯的入口链路")

    no_entry_ecs = primary.get("impacted_ecs_without_entry_paths", [])
    lines.append(f"\n**未回溯到入口的承载节点 ({len(no_entry_ecs)}台):**")
    if no_entry_ecs:
        for ecs in no_entry_ecs:
            lines.append(f"- {format_node_ref(ecs)}")
    else:
        lines.append("- 无")

    related_resources = primary.get("related_resources", {})
    lines.append("\n**邻近资源概览:**")
    related_lines = summarize_related_resources(related_resources)
    if related_lines:
        lines.extend(related_lines)
    else:
        lines.append("- 无")

    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    root = resolve_root(args.root)
    topologies = load_topologies(root, args.business)
    ranked = match_nodes(topologies, args.node)

    result: Dict[str, Any] = {
        "query": args.node,
        "matches": [],
    }

    for match in ranked[: args.top_k]:
        analyzed = analyze_match(match, args.max_depth)
        result["matches"].append(analyzed)

    print(build_output(result, args.output))


if __name__ == "__main__":
    main()
