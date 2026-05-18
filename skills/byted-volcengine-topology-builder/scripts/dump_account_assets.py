#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sdk_runtime import DEFAULT_REGION, ScriptError, call_action
from topology_constants import DEFAULT_INCLUDE_TYPES


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def parse_csv(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_multi_csv(values: Optional[List[str]]) -> List[str]:
    result: List[str] = []
    for raw in values or []:
        result.extend(parse_csv(raw))
    return result


def normalize_project_name(value: Any) -> str:
    return str(value or "").strip().lower()


def extract_project_name(item: Dict[str, Any]) -> str:
    value = item.get("project_name")
    if value not in (None, ""):
        return normalize_project_name(value)
    project_block = item.get("project")
    if isinstance(project_block, dict):
        for key in ("name", "project_name", "projectName"):
            nested_value = project_block.get(key)
            if nested_value not in (None, ""):
                return normalize_project_name(nested_value)
    if project_block not in (None, "") and not isinstance(project_block, dict):
        return normalize_project_name(project_block)
    return ""


def matches_project_filter(item: Dict[str, Any], project_names: List[str]) -> bool:
    if not project_names:
        return True
    return extract_project_name(item) in set(project_names)


def filter_items_by_project(
    items: Any, project_names: List[str]
) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [
        item
        for item in items
        if isinstance(item, dict) and matches_project_filter(item, project_names)
    ]


def update_items_block(block: Any, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    result = block if isinstance(block, dict) else {}
    result["items"] = items
    if "total_count" in result:
        result["total_count"] = len(items)
    return result


def collect_ids(items: Any, keys: List[str]) -> set:
    ids = set()
    if not isinstance(items, list):
        return ids
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in keys:
            value = str(item.get(key) or "").strip()
            if value:
                ids.add(value)
                break
    return ids


def has_reference(item: Dict[str, Any], keys: List[str], allowed_ids: set) -> bool:
    for key in keys:
        value = str(item.get(key) or "").strip()
        if value and value in allowed_ids:
            return True
    return False


def filter_items_by_project_or_reference(
    items: Any,
    project_names: List[str],
    *,
    reference_keys: List[str],
    allowed_ids: set,
) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    result: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if matches_project_filter(item, project_names) or has_reference(
            item, reference_keys, allowed_ids
        ):
            result.append(item)
    return result


def prune_assets_by_projects(assets: Dict[str, Any], project_names: List[str]) -> None:
    if not project_names:
        return

    ecs_items = filter_items_by_project(
        (assets.get("ecs") or {}).get("instances"), project_names
    )
    ecs_block = assets.get("ecs") or {}
    if isinstance(ecs_block, dict):
        ecs_block["instances"] = ecs_items
        if "total_count" in ecs_block:
            ecs_block["total_count"] = len(ecs_items)
        assets["ecs"] = ecs_block

    assets["eip"] = update_items_block(
        assets.get("eip"),
        filter_items_by_project((assets.get("eip") or {}).get("items"), project_names),
    )
    assets["clb_load_balancers"] = update_items_block(
        assets.get("clb_load_balancers"),
        filter_items_by_project(
            (assets.get("clb_load_balancers") or {}).get("items"), project_names
        ),
    )
    assets["alb_load_balancers"] = update_items_block(
        assets.get("alb_load_balancers"),
        filter_items_by_project(
            (assets.get("alb_load_balancers") or {}).get("items"), project_names
        ),
    )
    assets["nat_gateways"] = update_items_block(
        assets.get("nat_gateways"),
        filter_items_by_project(
            (assets.get("nat_gateways") or {}).get("items"), project_names
        ),
    )
    assets["rds_mysql_instances"] = update_items_block(
        assets.get("rds_mysql_instances"),
        filter_items_by_project(
            (assets.get("rds_mysql_instances") or {}).get("items"), project_names
        ),
    )
    assets["redis_instances"] = update_items_block(
        assets.get("redis_instances"),
        filter_items_by_project(
            (assets.get("redis_instances") or {}).get("items"), project_names
        ),
    )

    clb_lb_ids = collect_ids(
        (assets.get("clb_load_balancers") or {}).get("items"),
        ["load_balancer_id", "id"],
    )
    alb_lb_ids = collect_ids(
        (assets.get("alb_load_balancers") or {}).get("items"),
        ["load_balancer_id", "id"],
    )
    nat_ids = collect_ids(
        (assets.get("nat_gateways") or {}).get("items"),
        ["nat_gateway_id", "natgateway_id", "id"],
    )

    clb_attrs = assets.get("clb_server_group_attributes") or {}
    if isinstance(clb_attrs, dict):
        assets["clb_server_group_attributes"] = {
            server_group_id: attrs
            for server_group_id, attrs in clb_attrs.items()
            if isinstance(attrs, dict)
            and (
                matches_project_filter(attrs, project_names)
                or has_reference(
                    attrs, ["load_balancer_id", "loadbalancer_id", "lb_id"], clb_lb_ids
                )
            )
        }
    clb_server_group_ids = set((assets.get("clb_server_group_attributes") or {}).keys())
    assets["clb_server_groups"] = update_items_block(
        assets.get("clb_server_groups"),
        filter_items_by_project_or_reference(
            (assets.get("clb_server_groups") or {}).get("items"),
            project_names,
            reference_keys=["server_group_id", "id"],
            allowed_ids=clb_server_group_ids,
        ),
    )
    assets["clb_listeners"] = update_items_block(
        assets.get("clb_listeners"),
        filter_items_by_project_or_reference(
            (assets.get("clb_listeners") or {}).get("items"),
            project_names,
            reference_keys=[
                "load_balancer_id",
                "loadbalancer_id",
                "lb_id",
                "server_group_id",
            ],
            allowed_ids=clb_lb_ids | clb_server_group_ids,
        ),
    )

    alb_backends = assets.get("alb_server_group_backends") or {}
    if isinstance(alb_backends, dict):
        assets["alb_server_group_backends"] = {
            server_group_id: backend_block
            for server_group_id, backend_block in alb_backends.items()
            if server_group_id
        }
    alb_server_group_ids = set((assets.get("alb_server_group_backends") or {}).keys())
    assets["alb_server_groups"] = update_items_block(
        assets.get("alb_server_groups"),
        filter_items_by_project_or_reference(
            (assets.get("alb_server_groups") or {}).get("items"),
            project_names,
            reference_keys=[
                "load_balancer_id",
                "loadbalancer_id",
                "lb_id",
                "server_group_id",
                "id",
            ],
            allowed_ids=alb_lb_ids | alb_server_group_ids,
        ),
    )
    alb_server_group_ids = collect_ids(
        (assets.get("alb_server_groups") or {}).get("items"), ["server_group_id", "id"]
    )
    alb_backends = assets.get("alb_server_group_backends") or {}
    if isinstance(alb_backends, dict):
        assets["alb_server_group_backends"] = {
            server_group_id: backend_block
            for server_group_id, backend_block in alb_backends.items()
            if server_group_id in alb_server_group_ids
        }

    assets["alb_listeners"] = update_items_block(
        assets.get("alb_listeners"),
        filter_items_by_project_or_reference(
            (assets.get("alb_listeners") or {}).get("items"),
            project_names,
            reference_keys=[
                "load_balancer_id",
                "loadbalancer_id",
                "lb_id",
                "server_group_id",
            ],
            allowed_ids=alb_lb_ids | alb_server_group_ids,
        ),
    )
    assets["dnat_entries"] = update_items_block(
        assets.get("dnat_entries"),
        filter_items_by_project_or_reference(
            (assets.get("dnat_entries") or {}).get("items"),
            project_names,
            reference_keys=["nat_gateway_id", "natgateway_id"],
            allowed_ids=nat_ids,
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"全量拉取单地域账号资产快照（{DEFAULT_REGION} 优先）"
    )
    parser.add_argument(
        "--region",
        default=DEFAULT_REGION,
        help=f"地域，默认 {DEFAULT_REGION}",
    )
    parser.add_argument(
        "--include",
        default=",".join(DEFAULT_INCLUDE_TYPES),
        help="需要拉取的资源类型，逗号分隔。默认包含入口相关资源",
    )
    parser.add_argument(
        "--output-file",
        required=True,
        help="快照输出文件路径（JSON）",
    )
    parser.add_argument(
        "--env-path",
        default=None,
        help="可选 .env 路径；不传则由 SDK 默认逻辑读取",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=50,
        help="分页大小（对支持分页的接口生效），默认 50",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=200,
        help="最大页数上限（防止误配置导致无限循环），默认 200",
    )
    parser.add_argument(
        "--max-server-groups",
        type=int,
        default=200,
        help="最多下钻的服务器组数量上限（CLB/ALB），默认 200",
    )
    parser.add_argument(
        "--project",
        action="append",
        default=[],
        help="按火山引擎项目组过滤，可重复传入或用逗号分隔；不传默认不过滤",
    )
    parser.add_argument("--output", choices=["json"], default="json")
    return parser


def safe_call(
    service_key: str,
    action_name: str,
    params: Dict[str, Any],
    *,
    region: str,
    env_path: Optional[str],
) -> Dict[str, Any]:
    try:
        if env_path:
            return call_action(
                service_key,
                action_name,
                params,
                region=region,
                env_path=env_path,
            )
        return call_action(service_key, action_name, params, region=region)
    except Exception as exc:
        raise ScriptError(f"{service_key}.{action_name} 拉取失败: {exc}") from exc


def paged_fetch(
    service_key: str,
    action_name: str,
    *,
    region: str,
    env_path: Optional[str],
    page_size: int,
    max_pages: int,
    page_param: str = "page_number",
    size_param: str = "page_size",
) -> Dict[str, Any]:
    aggregated: List[Any] = []
    last_response: Dict[str, Any] = {}

    for page in range(1, max_pages + 1):
        resp = safe_call(
            service_key,
            action_name,
            {page_param: page, size_param: page_size},
            region=region,
            env_path=env_path,
        )
        last_response = resp

        # 不同服务字段名不同，这里做“尽量收集”的通用合并策略：
        # - list 类型字段：追加
        # - 其它字段：保留最后一次
        batch_items = None
        for value in resp.values():
            if isinstance(value, list):
                batch_items = value
                break
        if not batch_items:
            break

        aggregated.extend(batch_items)
        if len(batch_items) < page_size:
            break

    # 输出结构仍保留最后一次响应的非列表字段，同时把主要列表字段统一为 `items`
    result = {k: v for k, v in last_response.items() if not isinstance(v, list)}
    result["items"] = aggregated
    return result


def main() -> int:
    args = build_parser().parse_args()
    include = parse_csv(args.include)
    project_names = [
        normalize_project_name(item) for item in parse_multi_csv(args.project)
    ]
    region = args.region
    env_path = args.env_path

    snapshot: Dict[str, Any] = {
        "version": "0.1",
        "generated_at": utc_now_iso(),
        "region": region,
        "included": include,
        "project_names": project_names,
        "assets": {},
        "errors": [],
    }

    # 说明：这里优先用分页拉取（PageNumber/PageSize 模式）；
    # 对不支持分页的接口，内部会在第一页就结束。
    for resource_type in include:
        try:
            if resource_type == "ecs":
                snapshot["assets"]["ecs"] = safe_call(
                    "ecs",
                    "DescribeInstances",
                    {"max_results": args.page_size},
                    region=region,
                    env_path=env_path,
                )
            elif resource_type == "eip":
                snapshot["assets"]["eip"] = paged_fetch(
                    "eip",
                    "DescribeEipAddresses",
                    region=region,
                    env_path=env_path,
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                )
            elif resource_type == "clb":
                snapshot["assets"]["clb_load_balancers"] = paged_fetch(
                    "clb",
                    "DescribeLoadBalancers",
                    region=region,
                    env_path=env_path,
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                )
                snapshot["assets"]["clb_listeners"] = paged_fetch(
                    "clb",
                    "DescribeListeners",
                    region=region,
                    env_path=env_path,
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                )
                snapshot["assets"]["clb_server_groups"] = paged_fetch(
                    "clb",
                    "DescribeServerGroups",
                    region=region,
                    env_path=env_path,
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                )
                # 为了后续构建 lb -> ecs 关系，下钻服务器组详情，获取后端服务器列表。
                server_groups = (
                    snapshot["assets"]["clb_server_groups"].get("items") or []
                )
                server_group_attrs: Dict[str, Any] = {}
                for item in server_groups[: args.max_server_groups]:
                    server_group_id = str(item.get("server_group_id") or "").strip()
                    if not server_group_id:
                        continue
                    server_group_attrs[server_group_id] = safe_call(
                        "clb",
                        "DescribeServerGroupAttributes",
                        {"server_group_id": server_group_id},
                        region=region,
                        env_path=env_path,
                    )
                snapshot["assets"]["clb_server_group_attributes"] = server_group_attrs
            elif resource_type == "alb":
                snapshot["assets"]["alb_load_balancers"] = paged_fetch(
                    "alb",
                    "DescribeLoadBalancers",
                    region=region,
                    env_path=env_path,
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                )
                snapshot["assets"]["alb_listeners"] = paged_fetch(
                    "alb",
                    "DescribeListeners",
                    region=region,
                    env_path=env_path,
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                )
                snapshot["assets"]["alb_server_groups"] = paged_fetch(
                    "alb",
                    "DescribeServerGroups",
                    region=region,
                    env_path=env_path,
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                )
                # ALB 获取后端服务器列表需要调用 DescribeServerGroupBackendServers。
                server_groups = (
                    snapshot["assets"]["alb_server_groups"].get("items") or []
                )
                server_group_backends: Dict[str, Any] = {}
                for item in server_groups[: args.max_server_groups]:
                    server_group_id = str(item.get("server_group_id") or "").strip()
                    if not server_group_id:
                        continue
                    # 这里也做分页拉取，避免服务器组后端数量较多被截断。
                    aggregated: List[Any] = []
                    for page in range(1, args.max_pages + 1):
                        resp = safe_call(
                            "alb",
                            "DescribeServerGroupBackendServers",
                            {
                                "server_group_id": server_group_id,
                                "page_number": page,
                                "page_size": args.page_size,
                            },
                            region=region,
                            env_path=env_path,
                        )
                        servers = resp.get("servers") or []
                        if not isinstance(servers, list) or not servers:
                            break
                        aggregated.extend(servers)
                        if len(servers) < args.page_size:
                            break
                    server_group_backends[server_group_id] = {"servers": aggregated}
                snapshot["assets"]["alb_server_group_backends"] = server_group_backends
            elif resource_type == "natgateway":
                snapshot["assets"]["nat_gateways"] = paged_fetch(
                    "natgateway",
                    "DescribeNatGateways",
                    region=region,
                    env_path=env_path,
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                )
                snapshot["assets"]["dnat_entries"] = paged_fetch(
                    "natgateway",
                    "DescribeDnatEntries",
                    region=region,
                    env_path=env_path,
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                )
            elif resource_type == "rds_mysql":
                # RDS MySQL 使用 limit/offset，不是 PageNumber/PageSize。
                # 这里先按 offset 增量拉取，直到不足一页为止。
                aggregated: List[Any] = []
                for index in range(args.max_pages):
                    resp = safe_call(
                        "rds_mysql",
                        "ListDBInstances",
                        {
                            "limit": args.page_size,
                            "offset": index * args.page_size,
                            "region": region,
                        },
                        region=region,
                        env_path=env_path,
                    )
                    datas = resp.get("datas") or []
                    if not isinstance(datas, list) or not datas:
                        break
                    aggregated.extend(datas)
                    if len(datas) < args.page_size:
                        break
                snapshot["assets"]["rds_mysql_instances"] = {"items": aggregated}
            elif resource_type == "redis":
                snapshot["assets"]["redis_instances"] = paged_fetch(
                    "redis",
                    "DescribeDBInstances",
                    region=region,
                    env_path=env_path,
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                )
            else:
                snapshot["errors"].append(
                    {"resource_type": resource_type, "error": "unknown resource type"}
                )
        except ScriptError as exc:
            snapshot["errors"].append(
                {"resource_type": resource_type, "error": str(exc)}
            )

    # 采集完成后统一按项目组过滤，并补齐与入口资源关联的监听器/服务器组等附属资源。
    prune_assets_by_projects(snapshot["assets"], project_names)

    ensure_parent_dir(args.output_file)
    with open(args.output_file, "w", encoding="utf-8") as file_obj:
        json.dump(snapshot, file_obj, ensure_ascii=False, indent=2)
    print(
        json.dumps(
            {"output_file": args.output_file, "errors": snapshot["errors"]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
