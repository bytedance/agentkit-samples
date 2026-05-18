#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple


ENTRY_TYPES = {"eip", "clb", "alb", "natgateway"}
# 入口链路回溯时，CLB 往往不是最外层入口，因此不要在 CLB 处提前停止。
PATH_TERMINAL_TYPES = {"eip", "alb", "natgateway"}
INFRA_TYPES = {"security_group", "subnet", "vpc", "ebs"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze business topology and infer impact scope for a node."
    )
    parser.add_argument("--node", required=True, help="Node id, name, ip or keyword.")
    parser.add_argument(
        "--business",
        help="Optional business directory name under the workspace business_topologies.",
    )
    parser.add_argument(
        "--root",
        help=(
            "Business topology root directory. Defaults to auto-detecting "
            ".trae/business_topologies or business_topologies under the current workspace."
        ),
    )
    parser.add_argument(
        "--output",
        choices=("json", "text"),
        default="json",
        help="Output format.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=6,
        help="Traversal depth limit when searching paths.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Maximum number of ranked candidates to return.",
    )
    parser.add_argument(
        "--change",
        help="Optional change description used to generate impact summary and risk tips.",
    )
    return parser.parse_args()


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


def primary_search_terms(node: Dict[str, Any]) -> Set[str]:
    metadata = node.get("metadata", {})
    terms = {
        normalize(node.get("id")),
        normalize(node.get("name")),
    }
    terms.update(normalize(item) for item in metadata.get("private_ips", []))
    terms.update(normalize(item) for item in metadata.get("public_ips", []))
    terms.add(normalize(metadata.get("public_ip")))
    return {term for term in terms if term}


def score_node_match(node: Dict[str, Any], query: str) -> Tuple[int, List[str]]:
    normalized_query = normalize(query)
    if not normalized_query:
        return 0, []

    metadata = node.get("metadata", {})
    score = 0
    reasons: List[str] = []

    # 主字段命中优先级高于 metadata 模糊命中，用来支撑多候选排序。
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

        # 用资产快照补齐 topology.json/chains 未覆盖到的“孤立 ECS”。
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
            matched = str(instance.get("vpc_id") or "").strip() == target_id or any(
                str(nic.get("vpc_id") or "").strip() == target_id
                for nic in network_interfaces
                if isinstance(nic, dict)
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


def match_nodes(
    topologies: Sequence[Dict[str, Any]], query: str
) -> List[Dict[str, Any]]:
    ranked_matches: List[Dict[str, Any]] = []

    for item in topologies:
        for node in item["topology"].get("nodes", []):
            score, reasons = score_node_match(node, query)
            if score <= 0:
                continue
            payload = {
                "business": item["business"],
                "topology_file": item["topology_file"],
                "topology_md": item["topology_md"],
                "account_assets_snapshot": item["account_assets_snapshot"],
                "topology": item["topology"],
                "node": node,
                "match_score": score,
                "match_reasons": reasons,
            }
            ranked_matches.append(payload)

    return sorted(
        ranked_matches,
        key=lambda item: (
            -item["match_score"],
            item["business"],
            item["node"].get("type", ""),
            item["node"].get("id", ""),
        ),
    )


def extract_ports(change_text: str) -> List[int]:
    if not change_text:
        return []

    normalized = change_text.lower()
    if "端口" not in change_text and "port" not in normalized:
        return []

    ports: List[int] = []
    for value in re.findall(r"\b\d{1,5}\b", change_text):
        port = int(value)
        if 1 <= port <= 65535 and port not in ports:
            ports.append(port)
    return ports


def classify_change_action(change_text: str) -> Dict[str, Any]:
    normalized = normalize(change_text)
    if not normalized:
        return {
            "category": "unknown",
            "risk_level": "medium",
            "keywords": [],
            "summary": "未提供明确变更动作，按通用变更评估。",
        }

    categories = [
        (
            "high",
            "critical",
            [
                "删除",
                "remove",
                "delete",
                "revoke",
                "释放",
                "detach",
                "终止",
                "stop",
                "重启",
                "reboot",
            ],
            "变更描述包含删除、摘除、停止或中断类动作，属于高风险变更。",
        ),
        (
            "medium",
            "high",
            [
                "修改",
                "change",
                "modify",
                "update",
                "替换",
                "切换",
                "迁移",
                "缩容",
                "扩容",
            ],
            "变更描述包含配置修改或切换类动作，可能影响现有访问链路。",
        ),
        (
            "medium",
            "high",
            [
                "开放",
                "放开",
                "open",
                "authorize",
                "allow",
                "新增规则",
                "添加规则",
                "绑定",
                "attach",
            ],
            "变更描述包含放通、授权或绑定类动作，需要重点确认放通范围。",
        ),
        (
            "low",
            "medium",
            ["查询", "check", "verify", "确认", "核对", "只读"],
            "变更描述更像是检查或核对动作，风险相对较低。",
        ),
    ]

    for category, risk_level, keywords, summary in categories:
        hit_keywords = [keyword for keyword in keywords if keyword in normalized]
        if hit_keywords:
            return {
                "category": category,
                "risk_level": risk_level,
                "keywords": hit_keywords,
                "summary": summary,
            }

    return {
        "category": "medium",
        "risk_level": "high",
        "keywords": [],
        "summary": "未识别到标准动作关键字，按常规配置变更处理。",
    }


def merge_risk_level(current: str, candidate: str) -> str:
    order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    return current if order[current] >= order[candidate] else candidate


def build_change_assessment(
    change_text: str,
    matched_node: Dict[str, Any],
    impacted_ecs: List[Dict[str, Any]],
    application_paths: List[List[Dict[str, Any]]],
    impacted_ecs_without_entry_paths: List[Dict[str, Any]],
) -> Dict[str, Any]:
    # 这里是启发式风险评估，只用于生成变更前摘要，不替代真实变更评审。
    action = classify_change_action(change_text)
    ports = extract_ports(change_text)
    node_type = matched_node.get("type")

    risk_level = action["risk_level"]
    risk_reasons = [action["summary"]]
    summary_lines = [f"目标节点类型为 `{node_type}`，需要结合其关联链路评估影响。"]

    if impacted_ecs:
        summary_lines.append(f"当前可明确关联到 {len(impacted_ecs)} 台 ECS。")
    else:
        summary_lines.append("当前没有直接推断到受影响 ECS，需要人工补充确认。")

    if application_paths:
        summary_lines.append(f"当前可回溯出 {len(application_paths)} 条入口链路。")
    else:
        summary_lines.append("当前未回溯出完整入口链路，可能只定位到基础设施层。")

    if impacted_ecs_without_entry_paths:
        summary_lines.append(
            f"其中 {len(impacted_ecs_without_entry_paths)} 台 ECS 当前未形成可回溯的入口链路。"
        )

    if ports:
        summary_lines.append(
            "变更描述中提到了端口: " + ", ".join(str(port) for port in ports) + "。"
        )

    validation_checklist = [
        "确认变更是否只覆盖目标业务和目标环境。",
        "确认是否存在可回滚方案，以及变更窗口内的观测指标。",
        "在变更后复核入口链路和核心探活结果。",
    ]
    rollback_suggestions = [
        "保留原始配置快照，确保可以快速回退。",
        "优先在低峰期执行，并观察入口流量与错误率。",
    ]

    if node_type == "security_group":
        risk_level = merge_risk_level(risk_level, "high")
        risk_reasons.append("安全组规则直接影响挂载该安全组的 ECS 入出方向访问控制。")
        validation_checklist.extend(
            [
                "核对入方向/出方向、协议、端口、源地址段是否符合预期。",
                "确认是否会放大暴露面，例如 0.0.0.0/0 或过宽的办公网段。",
            ]
        )
        rollback_suggestions.append("保留旧规则集，必要时整组回滚。")
    elif node_type in {"clb", "alb", "natgateway"}:
        risk_level = merge_risk_level(risk_level, "high")
        risk_reasons.append("入口或转发层资源变更可能影响整条上游访问链路。")
        validation_checklist.extend(
            [
                "确认监听器、后端组、健康检查和转发策略是否同步更新。",
                "确认是否存在双活入口或备用切换路径。",
            ]
        )
    elif node_type in {"vpc", "subnet"}:
        risk_level = merge_risk_level(risk_level, "critical")
        risk_reasons.append("网络平面资源变更可能影响同域内多台计算节点。")
        validation_checklist.extend(
            [
                "确认路由、ACL、网段规划和依赖资源是否受影响。",
                "核对同 VPC 或同子网内其他节点是否共享该网络边界。",
            ]
        )
    elif node_type == "ebs":
        risk_level = merge_risk_level(risk_level, "high")
        risk_reasons.append("块存储变更可能直接影响挂载实例的读写能力。")
        validation_checklist.append(
            "确认实例侧的挂载点、文件系统和应用写入是否已保护。"
        )
    elif node_type == "ecs":
        risk_level = merge_risk_level(risk_level, "high")
        risk_reasons.append("计算节点变更会直接影响其对应入口链路上的流量承载。")
    elif node_type == "eip":
        risk_level = merge_risk_level(risk_level, "high")
        risk_reasons.append("公网入口地址变更会直接影响外部访问入口或回源目标。")

    return {
        "change_text": change_text,
        "action": action,
        "risk_level": risk_level,
        "summary_lines": summary_lines,
        "risk_reasons": risk_reasons,
        "validation_checklist": validation_checklist,
        "rollback_suggestions": rollback_suggestions,
        "ports": ports,
    }


def build_graph(
    topology: Dict[str, Any],
) -> Tuple[
    Dict[str, Any], Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]
]:
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
                        if not isinstance(current, dict) or not isinstance(
                            previous, dict
                        ):
                            continue
                        add_relation(
                            previous.get("id", ""),
                            current.get("id", ""),
                            current.get("relation", ""),
                        )

                contexts = route.get("contexts")
                if isinstance(contexts, dict):
                    for context_node_id, context_groups in contexts.items():
                        node_id = str(context_node_id or "").strip()
                        if not node_id or not isinstance(context_groups, dict):
                            continue
                        for context_type, items in context_groups.items():
                            relation = context_relation_by_type.get(
                                str(context_type), ""
                            )
                            if not relation or not isinstance(items, list):
                                continue
                            for item in items:
                                if isinstance(item, dict):
                                    add_relation(node_id, item.get("id", ""), relation)
                                else:
                                    add_relation(node_id, str(item), relation)
                else:
                    # 兼容旧结构：attachments 仅表达终点 ECS 的上下文。
                    ecs_id = ""
                    if isinstance(path, list) and path and isinstance(path[-1], dict):
                        ecs_id = str(path[-1].get("id") or "").strip()
                    attachments = route.get("attachments")
                    if ecs_id and isinstance(attachments, dict):
                        for attachment_type, items in attachments.items():
                            relation = context_relation_by_type.get(
                                str(attachment_type), ""
                            )
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

    # 去重，避免多条边导致相同链路重复输出。
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


def display_node(node: Dict[str, Any]) -> str:
    node_type = str(node.get("type") or "").strip()
    node_id = str(node.get("id") or "").strip()
    node_name = str(node.get("name") or "").strip()
    if node_type == "eip":
        preferred = str(node.get("public_ip") or node_name or node_id).strip()
        if preferred and preferred != node_id:
            return f"{node_type}:{preferred}({node_id})"
    return f"{node_type}:{node_id}"


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


def format_text(result: Dict[str, Any]) -> str:
    if not result["matches"]:
        return f"未找到节点: {result['query']}"

    lines: List[str] = []
    if len(result["matches"]) > 1:
        lines.append("候选节点按相关性排序如下：")
        for index, match in enumerate(result["matches"], start=1):
            matched_node = match["matched_node"]
            reason_text = ", ".join(match["match_reasons"]) or "unknown"
            lines.append(
                f"- 候选 {index}: score={match['match_score']} / "
                f"{match['business']} / {display_node(matched_node)} / {reason_text}"
            )
        lines.append("")

    for index, match in enumerate(result["matches"], start=1):
        matched_node = match["matched_node"]
        lines.append(f"[匹配 {index}] 业务: {match['business']}")
        lines.append(f"节点: {display_node(matched_node)}")
        reason_text = ", ".join(match["match_reasons"]) or "unknown"
        lines.append(f"命中得分: {match['match_score']} ({reason_text})")
        lines.append(f"拓扑文件: {match['topology_file']}")
        lines.append("直接关联:")
        if match["direct_relations"]:
            for relation in match["direct_relations"]:
                neighbor = relation["neighbor"]
                lines.append(
                    f"- {relation['direction']} {relation['relation']} -> "
                    f"{display_node(neighbor)}"
                )
        else:
            lines.append("- 无")

        lines.append("受影响的 ECS:")
        if match["impacted_ecs"]:
            for ecs in match["impacted_ecs"]:
                lines.append(f"- {display_node(ecs)}")
        else:
            lines.append("- 未推断到直接受影响 ECS")

        lines.append("推断出的应用入口链路:")
        if match["application_paths"]:
            for path in match["application_paths"]:
                chain = " -> ".join(display_node(node) for node in path)
                lines.append(f"- {chain}")
        else:
            lines.append("- 未推断到完整入口链路")

        lines.append("无入口链路但仍受影响的节点:")
        if match["impacted_ecs_without_entry_paths"]:
            for ecs in match["impacted_ecs_without_entry_paths"]:
                lines.append(f"- {display_node(ecs)}")
        else:
            lines.append("- 无")

        lines.append("关联资源概览:")
        for relation_group, items in match["related_resources"].items():
            if not items:
                continue
            display = ", ".join(display_node(item) for item in items)
            lines.append(f"- {relation_group}: {display}")
        if match.get("change_assessment"):
            assessment = match["change_assessment"]
            lines.append("变更影响摘要:")
            lines.append(f"- 风险等级: {assessment['risk_level']}")
            for item in assessment["summary_lines"]:
                lines.append(f"- {item}")
            lines.append("风险提示:")
            for item in assessment["risk_reasons"]:
                lines.append(f"- {item}")
            lines.append("校验建议:")
            for item in assessment["validation_checklist"]:
                lines.append(f"- {item}")
            lines.append("回滚建议:")
            for item in assessment["rollback_suggestions"]:
                lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines).strip()


def analyze_match(match: Dict[str, Any], max_depth: int) -> Dict[str, Any]:
    topology = match["topology"]
    target = match["node"]
    nodes, outgoing, incoming = build_graph(topology)
    snapshot = load_account_assets_snapshot(match["account_assets_snapshot"])

    impacted_ecs_ids = sorted(
        find_impacted_ecs(target, nodes, outgoing, incoming, max_depth)
    )
    impacted_ecs_map = {
        node_id: node_brief(nodes[node_id])
        for node_id in impacted_ecs_ids
        if node_id in nodes
    }
    for node_id, ecs in infer_snapshot_impacted_ecs(target, snapshot).items():
        impacted_ecs_map.setdefault(node_id, ecs)

    impacted_ecs = [impacted_ecs_map[node_id] for node_id in sorted(impacted_ecs_map)]

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
    for node_id, distance in sorted(
        distances.items(), key=lambda item: (item[1], item[0])
    ):
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


def main() -> None:
    args = parse_args()
    root = resolve_root(args.root)
    topologies = load_topologies(root, args.business)
    matches = match_nodes(topologies, args.node)

    result = {
        "query": args.node,
        "matches": [
            analyze_match(match, args.max_depth) for match in matches[: args.top_k]
        ],
    }

    if args.change:
        for match in result["matches"]:
            match["change_assessment"] = build_change_assessment(
                args.change,
                match["matched_node"],
                match["impacted_ecs"],
                match["application_paths"],
                match["impacted_ecs_without_entry_paths"],
            )

    if args.output == "text":
        print(format_text(result))
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
