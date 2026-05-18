#!/usr/bin/env python3
import argparse
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Optional

TERMINAL_NODE_TYPES = {"ecs", "eni", "ip", "rds_mysql", "redis"}
ROOT_PRIORITY = {
    "eip": 0,
    "clb": 1,
    "alb": 2,
    "natgateway": 3,
    "rds_mysql": 4,
    "redis": 5,
}
PROJECT_NODE_PREFIX = "project:"


def parse_csv(values: Optional[List[str]]) -> List[str]:
    result: List[str] = []
    for raw in values or []:
        for item in (raw or "").split(","):
            normalized = item.strip()
            if normalized:
                result.append(normalized)
    return result


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def pick_first(mapping: Dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, "", [], {}):
            return mapping[key]
    return None


def pick_first_str(mapping: Dict[str, Any], keys: Iterable[str]) -> Optional[str]:
    value = pick_first(mapping, keys)
    if value is None:
        return None
    return str(value).strip() or None


def find_list(mapping: Dict[str, Any], preferred_keys: List[str]) -> List[Any]:
    # 各产品 SDK 的响应字段名不统一，这里优先按常见字段名取列表；
    # 如果找不到，再从所有 value 里取“第一个 list”兜底。
    for key in preferred_keys:
        value = mapping.get(key)
        if isinstance(value, list):
            return value
    for value in mapping.values():
        if isinstance(value, list):
            return value
    return []


def normalize_ip_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    return []


def dedupe_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in values:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def normalize_project_name(value: Any) -> Optional[str]:
    normalized = str(value or "").strip()
    return normalized or None


def project_node_id(project_name: str) -> str:
    return f"{PROJECT_NODE_PREFIX}{project_name.strip().lower()}"


def has_vke_marker(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return False
    return any(
        marker in normalized
        for marker in (
            "managed.vke",
            "cluster.vke",
            "volc:vke",
            "apiserver-lb",
            "k8s",
            "kubernetes",
            "-vke-",
        )
    )


def tags_contain_vke(tags: Any) -> bool:
    if not isinstance(tags, list):
        return False
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        if has_vke_marker(tag.get("key")) or has_vke_marker(tag.get("value")):
            return True
    return False


def extract_private_ips_from_network_interfaces(instance: Dict[str, Any]) -> List[str]:
    # ECS 的私网 IP 在不同接口/版本下字段名差异较大：
    # - network_interfaces[].primary_ip_address
    # - network_interfaces[].private_ip_address / private_ip_addresses
    # - 顶层 private_ip_address / private_ip_addresses
    private_ips: List[str] = []

    nics = instance.get("network_interfaces")
    if isinstance(nics, list):
        for nic in nics:
            if not isinstance(nic, dict):
                continue
            private_ips.extend(
                normalize_ip_list(
                    pick_first(
                        nic,
                        [
                            "primary_ip_address",
                            "private_ip_address",
                            "private_ip_addresses",
                            "private_ips",
                        ],
                    )
                )
            )

    private_ips.extend(
        normalize_ip_list(
            pick_first(
                instance, ["private_ip_address", "private_ip_addresses", "private_ips"]
            )
        )
    )
    return dedupe_preserve_order([ip for ip in private_ips if ip])


def extract_public_ips_from_instance(instance: Dict[str, Any]) -> List[str]:
    # 公网 IP 可能在：
    # - eip_address.ip_address
    # - 顶层 public_ip_address / public_ip_addresses
    public_ips: List[str] = []
    eip_block = instance.get("eip_address")
    if isinstance(eip_block, dict):
        ip = pick_first_str(eip_block, ["ip_address", "eip_address", "public_ip"])
        if ip:
            public_ips.append(ip)
    public_ips.extend(
        normalize_ip_list(
            pick_first(
                instance, ["public_ip_address", "public_ip_addresses", "public_ips"]
            )
        )
    )
    return dedupe_preserve_order([ip for ip in public_ips if ip])


def add_node(nodes_by_id: Dict[str, Dict[str, Any]], node: Dict[str, Any]) -> None:
    node_id = str(node.get("id") or "").strip()
    if not node_id:
        return
    # 去重策略：同 id 的节点合并 metadata（不做深拷贝，避免不必要复制）。
    existing = nodes_by_id.get(node_id)
    if not existing:
        nodes_by_id[node_id] = node
        return
    existing_meta = existing.setdefault("metadata", {})
    new_meta = node.get("metadata") or {}
    if isinstance(existing_meta, dict) and isinstance(new_meta, dict):
        for key, value in new_meta.items():
            if key not in existing_meta:
                existing_meta[key] = value


def add_edge(edges: List[Dict[str, Any]], edge: Dict[str, Any]) -> None:
    frm = str(edge.get("from") or "").strip()
    to = str(edge.get("to") or "").strip()
    if not frm or not to or frm == to:
        return
    edges.append(edge)


def dedupe_edges(edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # 去重维度：同一对节点 + 同一 relation 视为同一条关系边。
    # 说明：metadata 不参与去重，避免因为多处补边导致输出重复（尤其是 ECS 归属资源）。
    seen = set()
    result: List[Dict[str, Any]] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        frm = str(edge.get("from") or "").strip()
        to = str(edge.get("to") or "").strip()
        rel = str(edge.get("relation") or "").strip()
        key = (frm, to, rel)
        if not frm or not to or frm == to or not rel:
            continue
        if key in seen:
            continue
        seen.add(key)
        result.append(edge)
    return result


def node_brief(node: Dict[str, Any]) -> Dict[str, Any]:
    # 仅保留链路展示和后续分析必需字段，避免冗余复制大对象。
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
    node_id = str(node.get("id") or "").strip()
    # 展示层统一以资源实例 ID 为主，避免名称重复带来的歧义；
    # EIP 仍优先展示可读的公网 IP。
    if node_type == "eip":
        label_value = name or node_id
    elif node_type == "project":
        label_value = name or node_id
    else:
        label_value = node_id or name
    return {
        "id": node_id,
        "type": node_type,
        "name": name,
        "label": f"{type_display}:{label_value}",
    }


def path_node_brief(
    node: Dict[str, Any], relation: Optional[str] = None
) -> Dict[str, Any]:
    item = {
        "id": str(node.get("id") or "").strip(),
        "type": str(node.get("type") or "").strip(),
    }
    normalized_relation = str(relation or "").strip()
    if normalized_relation:
        item["relation"] = normalized_relation
    return item


def build_chains_from_edges(
    nodes_by_id: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    # 目标：把离散边聚合成“入口 -> 主链路 + 节点级上下文”的 key-value 结构。
    outgoing: Dict[str, List[Dict[str, Any]]] = {}
    inbound_count: Dict[str, int] = {}
    for edge in edges:
        frm = str(edge.get("from") or "").strip()
        to = str(edge.get("to") or "").strip()
        if not frm or not to:
            continue
        outgoing.setdefault(frm, []).append(edge)
        inbound_count[to] = inbound_count.get(to, 0) + 1

    for node_id in nodes_by_id:
        inbound_count.setdefault(node_id, 0)

    entry_types = {"eip", "clb", "alb", "natgateway"}
    roots = [node_id for node_id, count in inbound_count.items() if count == 0]

    def sort_root_key(node_id: str) -> Any:
        node_type = str((nodes_by_id.get(node_id) or {}).get("type") or "").strip()
        return (ROOT_PRIORITY.get(node_type, 100), node_id)

    roots = sorted(set(roots), key=sort_root_key)
    if not roots:
        roots = [
            node_id
            for node_id, node in nodes_by_id.items()
            if str(node.get("type") or "").strip() in set(ROOT_PRIORITY) | entry_types
        ]
    if not roots:
        roots = list(nodes_by_id.keys())

    def sort_edge_key(edge: Dict[str, Any]) -> Any:
        return (str(edge.get("relation") or ""), str(edge.get("to") or ""))

    infra_types = {"security_group", "subnet", "vpc", "ebs", "listener", "project"}
    context_types = {"security_group", "subnet", "vpc", "ebs", "listener", "project"}
    route_relations = {"attached_to", "has", "contains"}
    chains: Dict[str, Dict[str, Any]] = {}

    def walk_routes(
        current_id: str,
        path: List[Dict[str, Any]],
        visiting: set,
        result: Dict[str, Dict[str, Any]],
    ) -> None:
        current_node = nodes_by_id.get(current_id) or {
            "id": current_id,
            "type": "unknown",
            "name": current_id,
        }
        current_type = str(current_node.get("type") or "").strip()
        if current_type in TERMINAL_NODE_TYPES:
            result[current_id] = {
                "path": path,
            }
            return

        children = []
        for edge in sorted(outgoing.get(current_id, []), key=sort_edge_key):
            to_id = str(edge.get("to") or "").strip()
            if not to_id or to_id in visiting:
                continue
            to_node = nodes_by_id.get(to_id) or {}
            to_type = str(to_node.get("type") or "").strip()
            relation = str(edge.get("relation") or "").strip()
            if to_type in infra_types or relation not in route_relations:
                continue
            children.append((to_id, path_node_brief(to_node, relation)))

        for to_id, child_brief in children:
            walk_routes(
                to_id,
                path + [child_brief],
                visiting | {to_id},
                result,
            )

    def collect_contexts(path: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[str]]]:
        contexts: Dict[str, Dict[str, List[str]]] = {}
        path_ids = {
            str(item.get("id") or "").strip()
            for item in path
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        }
        for item in path:
            if not isinstance(item, dict):
                continue
            node_id = str(item.get("id") or "").strip()
            if not node_id:
                continue
            node_context: Dict[str, List[str]] = {}
            seen = set()
            for edge in sorted(outgoing.get(node_id, []), key=sort_edge_key):
                to_id = str(edge.get("to") or "").strip()
                if not to_id or to_id in path_ids:
                    continue
                target_node = nodes_by_id.get(to_id) or {}
                target_type = str(target_node.get("type") or "").strip()
                if target_type not in context_types:
                    continue
                key = (target_type, to_id)
                if key in seen:
                    continue
                seen.add(key)
                node_context.setdefault(target_type, []).append(to_id)
            if node_context:
                contexts[node_id] = node_context
        return contexts

    for root_id in sorted(set(roots)):
        entry_node = nodes_by_id.get(root_id) or {
            "id": root_id,
            "type": "unknown",
            "name": root_id,
        }
        entry_brief = node_brief(entry_node)
        routes: Dict[str, Dict[str, Any]] = {}
        walk_routes(root_id, [path_node_brief(entry_node)], {root_id}, routes)
        if not routes and entry_brief["type"] in TERMINAL_NODE_TYPES:
            routes[root_id] = {
                "path": [path_node_brief(entry_node)],
            }
        route_items: Dict[str, Dict[str, Any]] = {}
        for target_id, route in sorted(routes.items()):
            contexts = collect_contexts(route["path"])
            route_items[target_id] = {
                "path": route["path"],
                "contexts": contexts,
            }
        if not route_items:
            continue
        if len(route_items) == 1:
            chains[root_id] = next(iter(route_items.values()))
        else:
            chains[root_id] = route_items

    return chains


def augment_clb_related_resources(
    nodes_by_id: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
    lb: Dict[str, Any],
    clb_listeners_by_lb_id: Dict[str, List[Dict[str, Any]]],
) -> None:
    lb_id = try_extract_lb_id(lb)
    if not lb_id:
        return

    subnet_id = pick_first_str(lb, ["subnet_id"])
    if subnet_id:
        add_simple_node(
            nodes_by_id, node_id=subnet_id, node_type="subnet", name=subnet_id
        )
        add_edge(
            edges,
            {
                "from": lb_id,
                "to": subnet_id,
                "relation": "belongs_to",
                "strength": "medium",
                "impact": "soft",
            },
        )

    vpc_id = pick_first_str(lb, ["vpc_id"])
    if vpc_id:
        add_simple_node(nodes_by_id, node_id=vpc_id, node_type="vpc", name=vpc_id)
        add_edge(
            edges,
            {
                "from": lb_id,
                "to": vpc_id,
                "relation": "belongs_to",
                "strength": "medium",
                "impact": "soft",
            },
        )

    for listener in clb_listeners_by_lb_id.get(lb_id, []):
        if not isinstance(listener, dict):
            continue
        listener_id = pick_first_str(listener, ["listener_id", "id"])
        if not listener_id:
            continue
        listener_name = (
            pick_first_str(listener, ["listener_name", "name"]) or listener_id
        )
        add_simple_node(
            nodes_by_id,
            node_id=listener_id,
            node_type="listener",
            name=listener_name,
            metadata={"raw": listener, "source": "assets_snapshot"},
        )
        add_edge(
            edges,
            {
                "from": lb_id,
                "to": listener_id,
                "relation": "has",
                "strength": "medium",
                "impact": "soft",
            },
        )


def add_simple_node(
    nodes_by_id: Dict[str, Dict[str, Any]],
    *,
    node_id: str,
    node_type: str,
    name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    normalized_id = (node_id or "").strip()
    if not normalized_id:
        return
    add_node(
        nodes_by_id,
        {
            "id": normalized_id,
            "type": node_type,
            "name": (name or "").strip() or normalized_id,
            "metadata": metadata or {"source": "assets_snapshot"},
        },
    )


def augment_ecs_related_resources(
    nodes_by_id: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
    instance: Dict[str, Any],
) -> None:
    # 目标：把 “ECS 绑定/归属资源” 显式成图，便于输出 attached_to / belongs_to 关系。
    instance_id = pick_first_str(instance, ["instance_id", "id"])
    if not instance_id:
        return

    vpc_id = pick_first_str(instance, ["vpc_id"])
    if vpc_id:
        add_simple_node(nodes_by_id, node_id=vpc_id, node_type="vpc", name=vpc_id)
        add_edge(
            edges,
            {
                "from": instance_id,
                "to": vpc_id,
                "relation": "belongs_to",
                "strength": "strong",
                "impact": "hard",
            },
        )

    nics = instance.get("network_interfaces")
    if isinstance(nics, list):
        for nic in nics:
            if not isinstance(nic, dict):
                continue
            subnet_id = pick_first_str(nic, ["subnet_id"])
            if subnet_id:
                add_simple_node(
                    nodes_by_id, node_id=subnet_id, node_type="subnet", name=subnet_id
                )
                add_edge(
                    edges,
                    {
                        "from": instance_id,
                        "to": subnet_id,
                        "relation": "belongs_to",
                        "strength": "strong",
                        "impact": "hard",
                    },
                )
                if vpc_id:
                    add_edge(
                        edges,
                        {
                            "from": vpc_id,
                            "to": subnet_id,
                            "relation": "contains",
                            "strength": "strong",
                            "impact": "hard",
                        },
                    )

            sg_ids = nic.get("security_group_ids")
            if isinstance(sg_ids, list):
                for sg_id in [str(x).strip() for x in sg_ids if x not in (None, "")]:
                    if not sg_id:
                        continue
                    add_simple_node(
                        nodes_by_id,
                        node_id=sg_id,
                        node_type="security_group",
                        name=sg_id,
                    )
                    add_edge(
                        edges,
                        {
                            "from": instance_id,
                            "to": sg_id,
                            "relation": "belongs_to",
                            "strength": "strong",
                            "impact": "hard",
                        },
                    )

    vols = instance.get("volumes")
    if isinstance(vols, list):
        for vol in vols:
            if not isinstance(vol, dict):
                continue
            vol_id = pick_first_str(vol, ["volume_id", "id"])
            if not vol_id:
                continue
            add_simple_node(nodes_by_id, node_id=vol_id, node_type="ebs", name=vol_id)
            add_edge(
                edges,
                {
                    "from": instance_id,
                    "to": vol_id,
                    "relation": "attached_to",
                    "strength": "strong",
                    "impact": "hard",
                },
            )


def add_project_relation(
    nodes_by_id: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
    owner_id: str,
    project_name: Optional[str],
) -> None:
    normalized_project_name = normalize_project_name(project_name)
    if not owner_id or not normalized_project_name:
        return
    add_simple_node(
        nodes_by_id,
        node_id=project_node_id(normalized_project_name),
        node_type="project",
        name=normalized_project_name,
        metadata={"project_name": normalized_project_name, "source": "assets_snapshot"},
    )
    add_edge(
        edges,
        {
            "from": owner_id,
            "to": project_node_id(normalized_project_name),
            "relation": "belongs_to",
            "strength": "medium",
            "impact": "soft",
        },
    )


def augment_managed_db_related_resources(
    nodes_by_id: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
    instance: Dict[str, Any],
) -> None:
    instance_id = pick_first_str(instance, ["instance_id", "id"])
    if not instance_id:
        return

    add_project_relation(
        nodes_by_id, edges, instance_id, pick_first_str(instance, ["project_name"])
    )

    vpc_id = pick_first_str(instance, ["vpc_id", "vpcid"])
    if vpc_id:
        add_simple_node(nodes_by_id, node_id=vpc_id, node_type="vpc", name=vpc_id)
        add_edge(
            edges,
            {
                "from": instance_id,
                "to": vpc_id,
                "relation": "belongs_to",
                "strength": "strong",
                "impact": "hard",
            },
        )

    subnet_id = pick_first_str(instance, ["subnet_id"])
    if subnet_id:
        add_simple_node(
            nodes_by_id, node_id=subnet_id, node_type="subnet", name=subnet_id
        )
        add_edge(
            edges,
            {
                "from": instance_id,
                "to": subnet_id,
                "relation": "belongs_to",
                "strength": "strong",
                "impact": "hard",
            },
        )
        if vpc_id:
            add_edge(
                edges,
                {
                    "from": vpc_id,
                    "to": subnet_id,
                    "relation": "contains",
                    "strength": "strong",
                    "impact": "hard",
                },
            )


def build_ecs_index(ecs_resp: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    instances = find_list(ecs_resp, ["instances", "instance_set", "items"])
    index: Dict[str, Dict[str, Any]] = {}
    for inst in instances:
        if not isinstance(inst, dict):
            continue
        instance_id = pick_first_str(inst, ["instance_id", "id"])
        if not instance_id:
            continue
        index[instance_id] = inst
    return index


def ecs_node_from_instance(instance: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    instance_id = pick_first_str(instance, ["instance_id", "id"])
    if not instance_id:
        return None
    name = pick_first_str(instance, ["instance_name", "name"]) or instance_id
    private_ips = extract_private_ips_from_network_interfaces(instance)
    public_ips = extract_public_ips_from_instance(instance)
    return {
        "id": instance_id,
        "type": "ecs",
        "name": name,
        "metadata": {
            "private_ips": private_ips,
            "public_ips": public_ips,
            "source": "assets_snapshot",
        },
    }


def infer_backend_node_type(
    backend: Dict[str, Any], ecs_index: Dict[str, Dict[str, Any]]
) -> str:
    # 后端节点既可能是 ECS，也可能直接按 ENI/IP 注册到后端服务器组。
    backend_type = (
        pick_first_str(
            backend, ["type", "server_type", "backend_type", "instance_type"]
        )
        or ""
    ).lower()
    instance_id = (
        pick_first_str(backend, ["instance_id", "ecs_instance_id", "server_id", "id"])
        or ""
    )
    if backend_type in TERMINAL_NODE_TYPES:
        return backend_type
    if instance_id in ecs_index or instance_id.startswith("i-"):
        return "ecs"
    if instance_id.startswith("eni-"):
        return "eni"
    if pick_first_str(backend, ["ip", "private_ip", "private_ip_address", "server_ip"]):
        return "ip"
    return "ecs"


def infer_backend_workload(
    backend: Dict[str, Any],
    server_group_info: Dict[str, Any],
    lb_info: Dict[str, Any],
) -> Optional[str]:
    candidates = [
        pick_first_str(backend, ["description", "name"]),
        pick_first_str(server_group_info, ["server_group_name", "description", "name"]),
        pick_first_str(lb_info, ["load_balancer_name", "description", "name"]),
    ]
    if any(has_vke_marker(item) for item in candidates):
        return "vke"
    if tags_contain_vke(server_group_info.get("tags")) or tags_contain_vke(
        lb_info.get("tags")
    ):
        return "vke"
    return None


def backend_node_from_target(
    backend: Dict[str, Any],
    ecs_index: Dict[str, Dict[str, Any]],
    workload: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    backend_id = pick_first_str(
        backend, ["instance_id", "ecs_instance_id", "server_id", "id"]
    )
    backend_ip = pick_first_str(
        backend, ["ip", "private_ip", "private_ip_address", "server_ip"]
    )
    backend_type = infer_backend_node_type(backend, ecs_index)

    if backend_type == "ecs":
        ecs = ecs_index.get(backend_id or "") or {"instance_id": backend_id}
        return ecs_node_from_instance(ecs)

    node_id = backend_id or backend_ip
    if not node_id:
        return None
    return {
        "id": node_id,
        "type": backend_type,
        "name": backend_ip or backend_id or node_id,
        "metadata": {
            "private_ips": [backend_ip] if backend_ip else [],
            "public_ips": [],
            "raw": backend,
            "source": "assets_snapshot",
            "workload": workload,
        },
    }


def add_server_group_backend(
    nodes_by_id: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
    server_group_id: str,
    backend: Dict[str, Any],
    ecs_index: Dict[str, Dict[str, Any]],
    via: str,
    workload: Optional[str] = None,
) -> None:
    backend_node = backend_node_from_target(backend, ecs_index, workload=workload)
    if not backend_node:
        return

    add_node(nodes_by_id, backend_node)
    if backend_node["type"] == "ecs":
        ecs = ecs_index.get(backend_node["id"])
        if ecs:
            augment_ecs_related_resources(nodes_by_id, edges, ecs)

    add_edge(
        edges,
        {
            "from": server_group_id,
            "to": backend_node["id"],
            "relation": "contains",
            "strength": "strong",
            "impact": "hard",
            "metadata": {"via": via},
        },
    )


def try_extract_lb_id(item: Dict[str, Any]) -> Optional[str]:
    return pick_first_str(
        item,
        [
            "load_balancer_id",
            "loadbalancer_id",
            "lb_id",
            "id",
        ],
    )


def try_extract_eip_id(item: Dict[str, Any]) -> Optional[str]:
    # 火山不同接口里可能是 allocation_id / eip_id / eip_address_id 等。
    return pick_first_str(
        item,
        [
            "allocation_id",
            "eip_id",
            "eip_address_id",
            "id",
        ],
    )


def try_extract_public_ip(item: Dict[str, Any]) -> Optional[str]:
    return pick_first_str(item, ["eip_address", "public_ip", "ip_address", "ip"])


def node_for_eip(eip: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    eip_id = try_extract_eip_id(eip)
    public_ip = try_extract_public_ip(eip)
    if not eip_id and not public_ip:
        return None
    node_id = eip_id or f"eip:{public_ip}"
    name = public_ip or node_id
    return {
        "id": node_id,
        "type": "eip",
        "name": name,
        "metadata": {
            "public_ip": public_ip,
            "raw": eip,
            "source": "assets_snapshot",
        },
    }


def node_for_clb(lb: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    lb_id = try_extract_lb_id(lb)
    if not lb_id:
        return None
    name = pick_first_str(lb, ["load_balancer_name", "name"]) or lb_id
    return {
        "id": lb_id,
        "type": "clb",
        "name": name,
        "metadata": {"raw": lb, "source": "assets_snapshot"},
    }


def node_for_alb(lb: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    lb_id = try_extract_lb_id(lb)
    if not lb_id:
        return None
    name = pick_first_str(lb, ["load_balancer_name", "name"]) or lb_id
    return {
        "id": lb_id,
        "type": "alb",
        "name": name,
        "metadata": {"raw": lb, "source": "assets_snapshot"},
    }


def node_for_nat(nat: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    nat_id = pick_first_str(nat, ["nat_gateway_id", "natgateway_id", "id"])
    if not nat_id:
        return None
    name = pick_first_str(nat, ["nat_gateway_name", "name"]) or nat_id
    return {
        "id": nat_id,
        "type": "natgateway",
        "name": name,
        "metadata": {"raw": nat, "source": "assets_snapshot"},
    }


def node_for_rds_mysql(instance: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    instance_id = pick_first_str(instance, ["instance_id", "id"])
    if not instance_id:
        return None
    name = pick_first_str(instance, ["instance_name", "name"]) or instance_id
    return {
        "id": instance_id,
        "type": "rds_mysql",
        "name": name,
        "metadata": {
            "project_name": pick_first_str(instance, ["project_name"]),
            "vpc_id": pick_first_str(instance, ["vpc_id", "vpcid"]),
            "subnet_id": pick_first_str(instance, ["subnet_id"]),
            "zone_ids": pick_first(instance, ["zone_ids"]) or [],
            "raw": instance,
            "source": "assets_snapshot",
        },
    }


def node_for_redis(instance: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    instance_id = pick_first_str(instance, ["instance_id", "id"])
    if not instance_id:
        return None
    name = pick_first_str(instance, ["instance_name", "name"]) or instance_id
    return {
        "id": instance_id,
        "type": "redis",
        "name": name,
        "metadata": {
            "project_name": pick_first_str(instance, ["project_name"]),
            "vpc_id": pick_first_str(instance, ["vpc_id", "vpcid"]),
            "subnet_id": pick_first_str(instance, ["subnet_id"]),
            "private_address": pick_first_str(instance, ["private_address"]),
            "private_port": pick_first_str(instance, ["private_port"]),
            "zone_ids": pick_first(instance, ["zone_ids"]) or [],
            "raw": instance,
            "source": "assets_snapshot",
        },
    }


def build_edges_from_clb(
    nodes_by_id: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
    clb_server_group_attrs: Dict[str, Any],
    clb_server_groups_index: Dict[str, Dict[str, Any]],
    ecs_index: Dict[str, Dict[str, Any]],
) -> None:
    # CLB: server_group_attributes 里一般会带后端服务器列表，用来构建：
    # - clb --has--> server_group
    # - server_group --contains--> ecs
    for server_group_id, attrs in (clb_server_group_attrs or {}).items():
        if not isinstance(attrs, dict):
            continue

        # 从服务器组属性里尽量找到关联的 LB ID
        lb_id = pick_first_str(attrs, ["load_balancer_id", "loadbalancer_id", "lb_id"])
        # 同时也兼容 attrs 内 nested 的结构（比如 attrs["server_group"] 里含 lb_id）
        if not lb_id and isinstance(attrs.get("server_group"), dict):
            lb_id = try_extract_lb_id(attrs["server_group"])
        if not lb_id:
            continue

        # 服务器组节点（名称优先用 DescribeServerGroups 返回）
        sg_info = clb_server_groups_index.get(server_group_id) or {}
        sg_name = (
            pick_first_str(sg_info, ["server_group_name", "name"]) or server_group_id
        )
        lb_node = nodes_by_id.get(lb_id) or {}
        lb_raw = {}
        if isinstance(lb_node.get("metadata"), dict) and isinstance(
            lb_node["metadata"].get("raw"), dict
        ):
            lb_raw = lb_node["metadata"]["raw"]
        add_simple_node(
            nodes_by_id,
            node_id=server_group_id,
            node_type="server_group",
            name=sg_name,
            metadata={"raw": sg_info, "source": "assets_snapshot"},
        )
        add_edge(
            edges,
            {
                "from": lb_id,
                "to": server_group_id,
                "relation": "has",
                "strength": "strong",
                "impact": "hard",
            },
        )

        backends = find_list(attrs, ["servers", "backend_servers", "items"])
        for backend in backends:
            if not isinstance(backend, dict):
                continue
            workload = infer_backend_workload(backend, sg_info, lb_raw)
            add_server_group_backend(
                nodes_by_id,
                edges,
                server_group_id,
                backend,
                ecs_index,
                via=f"clb_server_group:{server_group_id}",
                workload=workload,
            )


def build_edges_from_alb(
    nodes_by_id: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
    alb_server_groups: Dict[str, Any],
    alb_server_group_backends: Dict[str, Any],
    alb_server_groups_index: Dict[str, Dict[str, Any]],
    ecs_index: Dict[str, Dict[str, Any]],
) -> None:
    # ALB: server_groups + DescribeServerGroupBackendServers 拉到后端 server 列表
    groups = (
        alb_server_groups.get("items") if isinstance(alb_server_groups, dict) else []
    )
    if not isinstance(groups, list):
        groups = []

    for group in groups:
        if not isinstance(group, dict):
            continue
        server_group_id = pick_first_str(group, ["server_group_id", "id"])
        lb_id = try_extract_lb_id(group) or pick_first_str(
            group, ["load_balancer_id", "loadbalancer_id"]
        )
        if not server_group_id or not lb_id:
            continue

        sg_info = alb_server_groups_index.get(server_group_id) or group
        sg_name = (
            pick_first_str(sg_info, ["server_group_name", "name"]) or server_group_id
        )
        lb_node = nodes_by_id.get(lb_id) or {}
        lb_raw = {}
        if isinstance(lb_node.get("metadata"), dict) and isinstance(
            lb_node["metadata"].get("raw"), dict
        ):
            lb_raw = lb_node["metadata"]["raw"]
        add_simple_node(
            nodes_by_id,
            node_id=server_group_id,
            node_type="server_group",
            name=sg_name,
            metadata={"raw": sg_info, "source": "assets_snapshot"},
        )
        add_edge(
            edges,
            {
                "from": lb_id,
                "to": server_group_id,
                "relation": "has",
                "strength": "strong",
                "impact": "hard",
            },
        )

        backend_block = (
            alb_server_group_backends.get(server_group_id)
            if isinstance(alb_server_group_backends, dict)
            else None
        )
        servers = []
        if isinstance(backend_block, dict):
            servers = backend_block.get("servers") or []
        if not isinstance(servers, list):
            servers = []

        for server in servers:
            if not isinstance(server, dict):
                continue
            workload = infer_backend_workload(server, sg_info, lb_raw)
            add_server_group_backend(
                nodes_by_id,
                edges,
                server_group_id,
                server,
                ecs_index,
                via=f"alb_server_group:{server_group_id}",
                workload=workload,
            )


def build_edges_from_nat_dnat(
    nodes_by_id: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
    nat_gateways: Dict[str, Any],
    dnat_entries: Dict[str, Any],
    ecs_index: Dict[str, Dict[str, Any]],
) -> None:
    # NAT: dnat_entries 里通常能映射 public_ip:public_port -> private_ip:private_port
    nats = nat_gateways.get("items") if isinstance(nat_gateways, dict) else []
    if not isinstance(nats, list):
        nats = []
    nat_ids = {
        pick_first_str(item, ["nat_gateway_id", "id"]): item
        for item in nats
        if isinstance(item, dict)
    }

    entries = dnat_entries.get("items") if isinstance(dnat_entries, dict) else []
    if not isinstance(entries, list):
        entries = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        nat_id = pick_first_str(entry, ["nat_gateway_id", "natgateway_id"])
        if not nat_id:
            continue
        nat_node = node_for_nat(nat_ids.get(nat_id) or {"nat_gateway_id": nat_id})
        if nat_node:
            add_node(nodes_by_id, nat_node)

        private_ip = pick_first_str(entry, ["internal_ip", "private_ip", "ip_address"])
        # DNAT 不一定能直接给 instance_id，这里仅能“尽量”反查 ECS（私有 IP 匹配）。
        target_instance_id = pick_first_str(entry, ["instance_id", "ecs_instance_id"])
        ecs_candidate = None
        if target_instance_id and target_instance_id in ecs_index:
            ecs_candidate = ecs_index[target_instance_id]
        elif private_ip:
            for ecs in ecs_index.values():
                if private_ip in normalize_ip_list(
                    pick_first(
                        ecs,
                        ["private_ip_address", "private_ip_addresses", "private_ips"],
                    )
                ):
                    ecs_candidate = ecs
                    break

        ecs_node = ecs_node_from_instance(ecs_candidate) if ecs_candidate else None
        if ecs_node and nat_node:
            add_node(nodes_by_id, ecs_node)
            if ecs_candidate:
                augment_ecs_related_resources(nodes_by_id, edges, ecs_candidate)
            add_edge(
                edges,
                {
                    "from": nat_node["id"],
                    "to": ecs_node["id"],
                    "relation": "attached_to",
                    "strength": "strong",
                    "impact": "hard",
                    "metadata": {"via": "dnat", "raw": entry},
                },
            )


def attach_eip_edges(
    nodes_by_id: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
    eip_items: List[Dict[str, Any]],
    lb_ids: List[str],
    nat_ids: List[str],
    ecs_index: Dict[str, Dict[str, Any]],
) -> None:
    # EIP 绑定关系字段在不同返回里差异较大，这里采取保守策略：
    # - 优先从 eip item 里找 instance_id / instance_type / resource_id 之类字段
    # - 找到则构建 eip -> clb/alb/natgateway 的边；找不到就只保留 eip 节点
    lb_id_set = set(lb_ids)
    nat_id_set = set(nat_ids)

    for eip in eip_items:
        if not isinstance(eip, dict):
            continue
        eip_node = node_for_eip(eip)
        if not eip_node:
            continue
        add_node(nodes_by_id, eip_node)

        bound_id = pick_first_str(
            eip,
            [
                "instance_id",
                "resource_id",
                "associated_instance_id",
                "bind_instance_id",
            ],
        )
        bound_type = (
            pick_first_str(
                eip, ["instance_type", "resource_type", "associated_instance_type"]
            )
            or ""
        ).lower()

        # 兜底：如果 type 没给，但 bound_id 恰好落在已知集合里，也可以判断目标类型。
        to_type = None
        if bound_id in lb_id_set:
            to_type = "lb"
        elif bound_id in nat_id_set:
            to_type = "nat"
        elif bound_id in ecs_index or (bound_id or "").startswith("i-"):
            # 常见 ECS instance_id 以 i- 开头；同时也用 index 做一次确认。
            to_type = "ecs"
        elif "nat" in bound_type:
            to_type = "nat"
        elif "ecs" in bound_type:
            to_type = "ecs"
        elif (
            "clb" in bound_type
            or "alb" in bound_type
            or "load" in bound_type
            or "lb" in bound_type
        ):
            to_type = "lb"

        if not bound_id or not to_type:
            continue

        if to_type == "ecs":
            ecs = ecs_index.get(bound_id) or {"instance_id": bound_id}
            ecs_node = ecs_node_from_instance(ecs)
            if ecs_node:
                add_node(nodes_by_id, ecs_node)
                augment_ecs_related_resources(nodes_by_id, edges, ecs)

        add_edge(
            edges,
            {
                "from": eip_node["id"],
                "to": bound_id,
                "relation": "attached_to",
                "strength": "strong",
                "impact": "hard",
                "metadata": {
                    "bind_type": bound_type or "unknown",
                    "source": "eip_binding",
                },
            },
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="从账号资产快照构建最小可用主链路拓扑（version 0.7）"
    )
    parser.add_argument(
        "--assets-file", required=True, help="dump_account_assets.py 生成的快照 JSON"
    )
    parser.add_argument(
        "--region", default=None, help="地域（可选，用于校验/写入输出）"
    )
    parser.add_argument(
        "--entry",
        action="append",
        default=[],
        help="入口类型，可重复传入，如 --entry eip --entry clb（支持 eip/clb/alb/natgateway）",
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="可选：输出 topology.json 路径；不传则打印到 stdout",
    )
    parser.add_argument("--output", choices=["json"], default="json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    entries = [item.lower() for item in parse_csv(args.entry)] or [
        "eip",
        "clb",
        "alb",
        "natgateway",
    ]

    snapshot = load_json(args.assets_file)
    assets = snapshot.get("assets") if isinstance(snapshot, dict) else {}
    if not isinstance(assets, dict):
        raise ValueError("assets-file 不是合法快照：缺少 assets 字段")

    ecs_resp = assets.get("ecs") or {}
    eip_resp = assets.get("eip") or {}
    clb_lbs_resp = assets.get("clb_load_balancers") or {}
    alb_lbs_resp = assets.get("alb_load_balancers") or {}
    nat_gateways_resp = assets.get("nat_gateways") or {}
    rds_mysql_resp = assets.get("rds_mysql_instances") or {}
    redis_resp = assets.get("redis_instances") or {}

    ecs_index = build_ecs_index(ecs_resp if isinstance(ecs_resp, dict) else {})

    clb_server_groups_index: Dict[str, Dict[str, Any]] = {}
    clb_server_groups_resp = assets.get("clb_server_groups") or {}
    clb_server_groups = (
        clb_server_groups_resp.get("items")
        if isinstance(clb_server_groups_resp, dict)
        else []
    )
    if isinstance(clb_server_groups, list):
        for item in clb_server_groups:
            if not isinstance(item, dict):
                continue
            sg_id = pick_first_str(item, ["server_group_id", "id"])
            if sg_id:
                clb_server_groups_index[sg_id] = item

    alb_server_groups_index: Dict[str, Dict[str, Any]] = {}
    alb_server_groups_resp = assets.get("alb_server_groups") or {}
    alb_server_groups = (
        alb_server_groups_resp.get("items")
        if isinstance(alb_server_groups_resp, dict)
        else []
    )
    if isinstance(alb_server_groups, list):
        for item in alb_server_groups:
            if not isinstance(item, dict):
                continue
            sg_id = pick_first_str(item, ["server_group_id", "id"])
            if sg_id:
                alb_server_groups_index[sg_id] = item

    clb_listeners_by_lb_id: Dict[str, List[Dict[str, Any]]] = {}
    clb_listeners_resp = assets.get("clb_listeners") or {}
    clb_listeners = (
        clb_listeners_resp.get("items") if isinstance(clb_listeners_resp, dict) else []
    )
    if isinstance(clb_listeners, list):
        for item in clb_listeners:
            if not isinstance(item, dict):
                continue
            lb_id = pick_first_str(
                item, ["load_balancer_id", "loadbalancer_id", "lb_id"]
            )
            if not lb_id:
                continue
            clb_listeners_by_lb_id.setdefault(lb_id, []).append(item)

    nodes_by_id: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []

    # 先把入口类节点放进去，便于后续建立 eip -> target 边。
    clb_ids: List[str] = []
    if "clb" in entries:
        clb_lbs = clb_lbs_resp.get("items") if isinstance(clb_lbs_resp, dict) else []
        for lb in clb_lbs if isinstance(clb_lbs, list) else []:
            if not isinstance(lb, dict):
                continue
            node = node_for_clb(lb)
            if not node:
                continue
            clb_ids.append(node["id"])
            add_node(nodes_by_id, node)
            augment_clb_related_resources(
                nodes_by_id, edges, lb, clb_listeners_by_lb_id
            )

    alb_ids: List[str] = []
    if "alb" in entries:
        alb_lbs = alb_lbs_resp.get("items") if isinstance(alb_lbs_resp, dict) else []
        for lb in alb_lbs if isinstance(alb_lbs, list) else []:
            if not isinstance(lb, dict):
                continue
            node = node_for_alb(lb)
            if not node:
                continue
            alb_ids.append(node["id"])
            add_node(nodes_by_id, node)

    nat_ids: List[str] = []
    if "natgateway" in entries:
        nats = (
            nat_gateways_resp.get("items")
            if isinstance(nat_gateways_resp, dict)
            else []
        )
        for nat in nats if isinstance(nats, list) else []:
            if not isinstance(nat, dict):
                continue
            node = node_for_nat(nat)
            if not node:
                continue
            nat_ids.append(node["id"])
            add_node(nodes_by_id, node)

    rds_mysql_items = (
        rds_mysql_resp.get("items") if isinstance(rds_mysql_resp, dict) else []
    )
    if isinstance(rds_mysql_items, list):
        for instance in rds_mysql_items:
            if not isinstance(instance, dict):
                continue
            node = node_for_rds_mysql(instance)
            if not node:
                continue
            add_node(nodes_by_id, node)
            augment_managed_db_related_resources(nodes_by_id, edges, instance)

    redis_items = redis_resp.get("items") if isinstance(redis_resp, dict) else []
    if isinstance(redis_items, list):
        for instance in redis_items:
            if not isinstance(instance, dict):
                continue
            node = node_for_redis(instance)
            if not node:
                continue
            add_node(nodes_by_id, node)
            augment_managed_db_related_resources(nodes_by_id, edges, instance)

    # 构建 lb/nat -> ecs 的主链路边
    if "clb" in entries:
        build_edges_from_clb(
            nodes_by_id,
            edges,
            assets.get("clb_server_group_attributes") or {},
            clb_server_groups_index,
            ecs_index,
        )
    if "alb" in entries:
        build_edges_from_alb(
            nodes_by_id,
            edges,
            assets.get("alb_server_groups") or {},
            assets.get("alb_server_group_backends") or {},
            alb_server_groups_index,
            ecs_index,
        )
    if "natgateway" in entries:
        build_edges_from_nat_dnat(
            nodes_by_id,
            edges,
            assets.get("nat_gateways") or {},
            assets.get("dnat_entries") or {},
            ecs_index,
        )

    # 构建 eip -> (clb/alb/natgateway) 的入口边（如果能识别绑定关系）
    if "eip" in entries:
        eip_items = eip_resp.get("items") if isinstance(eip_resp, dict) else []
        attach_eip_edges(
            nodes_by_id,
            edges,
            eip_items if isinstance(eip_items, list) else [],
            lb_ids=clb_ids + alb_ids,
            nat_ids=nat_ids,
            ecs_index=ecs_index,
        )

    normalized_edges = dedupe_edges(edges)
    topology = {
        "version": "0.7",
        "region": args.region or snapshot.get("region") or None,
        "nodes": list(nodes_by_id.values()),
        "chains": build_chains_from_edges(nodes_by_id, normalized_edges),
        "metadata": {
            "source": "build_topology_from_account_assets",
            "assets_file": os.path.abspath(args.assets_file),
            "entries": entries,
            "project_names": (
                snapshot.get("project_names") if isinstance(snapshot, dict) else []
            ),
            "topology_model": "chains_path_contexts",
        },
    }

    if args.output_file:
        os.makedirs(os.path.dirname(os.path.abspath(args.output_file)), exist_ok=True)
        with open(args.output_file, "w", encoding="utf-8") as file_obj:
            file_obj.write(dump_json(topology) + "\n")
    else:
        print(dump_json(topology))

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(dump_json({"error": str(exc)}))
        sys.exit(1)
