#!/usr/bin/env python3
import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import volcenginesdkcore
from volcenginesdkalb import (
    ALBApi,
    DescribeListenersRequest as DescribeAlbListenersRequest,
    DescribeLoadBalancersRequest as DescribeAlbLoadBalancersRequest,
)
from volcenginesdkclb import (
    CLBApi,
    DescribeListenersRequest as DescribeClbListenersRequest,
    DescribeLoadBalancersRequest,
)
from volcenginesdkcloudmonitor import CLOUDMONITORApi
from volcenginesdkcloudmonitor.models.dimension_for_get_metric_data_input import (
    DimensionForGetMetricDataInput,
)
from volcenginesdkcloudmonitor.models.get_metric_data_request import GetMetricDataRequest
from volcenginesdkcloudmonitor.models.instance_for_get_metric_data_input import (
    InstanceForGetMetricDataInput,
)
from volcenginesdkecs import ECSApi, DescribeInstancesRequest
from volcenginesdkrdsmysql import RDSMYSQLApi, ListDBInstancesRequest

SUPPORTED_TOPOLOGY_RESOURCE_TYPES = {"alb", "clb", "ecs", "rds_mysql"}


def load_env(env_path: Path) -> None:
    if not env_path.exists():
        raise FileNotFoundError(f".env 文件不存在: {env_path}")
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def configure_sdk(region: Optional[str] = None) -> None:
    config = volcenginesdkcore.Configuration()
    config.ak = os.getenv("VOLCENGINE_AK")
    config.sk = os.getenv("VOLCENGINE_SK")
    config.region = region or os.getenv("VOLCENGINE_REGION", "cn-beijing")
    if not config.ak or not config.sk:
        raise RuntimeError("缺少 VOLCENGINE_AK / VOLCENGINE_SK")
    volcenginesdkcore.Configuration.set_default(config)


def percentile(values: List[float], ratio: float) -> Optional[float]:
    if not values:
        return None
    sorted_values = sorted(values)
    index = max(0, min(len(sorted_values) - 1, int(len(sorted_values) * ratio) - 1))
    return sorted_values[index]


def summarize_points(values: Iterable[float]) -> Dict[str, Optional[float]]:
    normalized = [float(v) for v in values]
    if not normalized:
        return {"count": 0, "avg": None, "max": None, "p95": None}
    p95 = percentile(normalized, 0.95)
    return {
        "count": len(normalized),
        "avg": round(sum(normalized) / len(normalized), 4),
        "max": round(max(normalized), 4),
        "p95": round(p95, 4) if p95 is not None else None,
    }


def format_value(value: Optional[float], suffix: str = "%") -> str:
    if value is None:
        return "N/A"
    if suffix:
        return f"{value}{suffix}"
    return str(value)


def load_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def build_empty_summary(
    error: Optional[str] = None,
    source: Optional[Dict[str, str]] = None,
    attempted_sources: Optional[List[str]] = None,
) -> Dict[str, Optional[float]]:
    summary: Dict[str, Optional[float]] = {"count": 0, "avg": None, "max": None, "p95": None}
    if error:
        summary["error"] = error
    if source:
        summary["source"] = source
    if attempted_sources:
        summary["attempted_sources"] = attempted_sources
    return summary


def summary_has_data(summary: Dict) -> bool:
    return bool(summary.get("count")) and any(
        summary.get(key) is not None for key in ("avg", "max", "p95")
    )


def summary_error(summary: Dict) -> Optional[str]:
    error = summary.get("error")
    return str(error) if error else None


def summary_metric_value(summary: Dict) -> Optional[float]:
    for key in ("p95", "max", "avg"):
        value = summary.get(key)
        if value is not None:
            return float(value)
    return None


def source_label(source: Dict[str, str]) -> str:
    return f"{source['namespace']}/{source['sub_namespace']}/{source['metric_name']}"


def node_label(node: Dict, nodes_by_id: Dict[str, Dict]) -> str:
    node_id = str(node.get("id") or "").strip()
    node_type = str(node.get("type") or nodes_by_id.get(node_id, {}).get("type") or "unknown").strip()
    node_name = str(nodes_by_id.get(node_id, {}).get("name") or node_id).strip()
    return f"{node_type}:{node_name}"


def is_topology_route(item: object) -> bool:
    return isinstance(item, dict) and isinstance(item.get("path"), list)


def iter_topology_routes(chains: Dict) -> Iterable[Dict]:
    for root_id, chain in (chains or {}).items():
        if is_topology_route(chain):
            yield {"root_id": root_id, "route_id": root_id, **chain}
            continue
        if not isinstance(chain, dict):
            continue
        for route_id, route in chain.items():
            if is_topology_route(route):
                yield {"root_id": root_id, "route_id": route_id, **route}


def add_resource_id(resource_ids: Dict[str, List[str]], resource_type: Optional[str], resource_id: Optional[str]) -> None:
    normalized_type = str(resource_type or "").strip()
    normalized_id = str(resource_id or "").strip()
    if normalized_type not in SUPPORTED_TOPOLOGY_RESOURCE_TYPES or not normalized_id:
        return
    resource_ids.setdefault(normalized_type, [])
    if normalized_id not in resource_ids[normalized_type]:
        resource_ids[normalized_type].append(normalized_id)


def build_topology_scope(topology: Dict, topology_file: Path) -> Dict:
    nodes_by_id = {
        str(node.get("id") or "").strip(): node
        for node in topology.get("nodes", [])
        if str(node.get("id") or "").strip()
    }
    resource_ids = {resource_type: [] for resource_type in SUPPORTED_TOPOLOGY_RESOURCE_TYPES}
    paths: List[str] = []

    for route in iter_topology_routes(topology.get("chains", {})):
        path = route.get("path") or []
        contexts = route.get("contexts") or {}
        if path:
            paths.append(" -> ".join(node_label(node, nodes_by_id) for node in path))
        for node in path:
            node_id = str(node.get("id") or "").strip()
            node_type = str(node.get("type") or nodes_by_id.get(node_id, {}).get("type") or "").strip()
            add_resource_id(resource_ids, node_type, node_id)
        for owner_id, context_mapping in contexts.items():
            owner_type = str(nodes_by_id.get(owner_id, {}).get("type") or "").strip()
            add_resource_id(resource_ids, owner_type, owner_id)
            if not isinstance(context_mapping, dict):
                continue
            for related_ids in context_mapping.values():
                if not isinstance(related_ids, list):
                    continue
                for related_id in related_ids:
                    related_type = str(nodes_by_id.get(str(related_id), {}).get("type") or "").strip()
                    add_resource_id(resource_ids, related_type, str(related_id))

    return {
        "enabled": True,
        "source": str(topology_file),
        "resource_ids": resource_ids,
        "resource_counts": {resource_type: len(ids) for resource_type, ids in resource_ids.items()},
        "paths": paths,
        "data_gaps": [],
    }


def build_missing_topology_scope(topology_file: Optional[Path], link_name: Optional[str]) -> Dict:
    reference = str(topology_file) if topology_file else (link_name or "未指定")
    return {
        "enabled": False,
        "source": str(topology_file) if topology_file else None,
        "resource_ids": {resource_type: [] for resource_type in SUPPORTED_TOPOLOGY_RESOURCE_TYPES},
        "resource_counts": {resource_type: 0 for resource_type in SUPPORTED_TOPOLOGY_RESOURCE_TYPES},
        "paths": [],
        "data_gaps": [f"未找到可用拓扑文件，无法按链路 `{reference}` 缩小容量评估范围"],
    }


def resolve_topology_file(env_path: Path, link_name: Optional[str], topology_file: Optional[str]) -> Optional[Path]:
    if topology_file:
        candidate = Path(topology_file).expanduser()
        if not candidate.is_absolute():
            candidate = (Path.cwd() / candidate).resolve()
        return candidate
    if not link_name:
        return None
    candidates = [
        Path.cwd() / "business_topologies" / link_name / "topology.json",
        env_path.parent.resolve() / "business_topologies" / link_name / "topology.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def build_instance(resource_id: str, extra_dimensions: Optional[List[Dict[str, str]]] = None):
    dimensions = [DimensionForGetMetricDataInput(name="ResourceID", value=resource_id)]
    for item in extra_dimensions or []:
        dimensions.append(
            DimensionForGetMetricDataInput(name=item["name"], value=item["value"])
        )
    return [InstanceForGetMetricDataInput(dimensions=dimensions)]


def fetch_metric_summary(
    namespace: str,
    sub_namespace: str,
    metric_name: str,
    resource_id: str,
    period: str,
    start_time: int,
    end_time: int,
    extra_dimensions: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Optional[float]]:
    request = GetMetricDataRequest(
        namespace=namespace,
        sub_namespace=sub_namespace,
        metric_name=metric_name,
        start_time=start_time,
        end_time=end_time,
        period=period,
        instances=build_instance(resource_id, extra_dimensions),
    )
    response = CLOUDMONITORApi().get_metric_data(request).to_dict()["data"]
    results = response.get("metric_data_results") or []

    # 某些磁盘指标会返回多个分区，这里统一拉平再汇总，方便做第一版巡检。
    values: List[float] = []
    for item in results:
        for point in item.get("data_points", []):
            value = point.get("value")
            if value is not None:
                values.append(float(value))
    return summarize_points(values)


def safe_fetch_metric_summary(**kwargs) -> Dict[str, Optional[float]]:
    try:
        return fetch_metric_summary(**kwargs)
    except Exception as exc:
        return build_empty_summary(error=str(exc).split("\n")[0])


def safe_fetch_metric_summary_candidates(
    candidates: List[Dict[str, str]],
    resource_id: str,
    period: str,
    start_time: int,
    end_time: int,
    extra_dimensions: Optional[List[Dict[str, str]]] = None,
) -> Dict:
    attempted_sources: List[str] = []
    errors: List[str] = []

    for candidate in candidates:
        source = {
            "namespace": candidate["namespace"],
            "sub_namespace": candidate["sub_namespace"],
            "metric_name": candidate["metric_name"],
        }
        attempted_sources.append(source_label(source))
        summary = safe_fetch_metric_summary(
            namespace=candidate["namespace"],
            sub_namespace=candidate["sub_namespace"],
            metric_name=candidate["metric_name"],
            resource_id=resource_id,
            period=period,
            start_time=start_time,
            end_time=end_time,
            extra_dimensions=extra_dimensions,
        )
        if summary_has_data(summary):
            summary["source"] = source
            if attempted_sources:
                summary["attempted_sources"] = attempted_sources
            return summary
        if summary_error(summary):
            errors.append(f"{source_label(source)}: {summary_error(summary)}")

    error = "; ".join(errors[:3]) if errors else "所有候选监控口径均无数据"
    return build_empty_summary(error=error, attempted_sources=attempted_sources)


def fetch_ecs_instances(limit: int = 100) -> List[Dict]:
    response = ECSApi().describe_instances(DescribeInstancesRequest(max_results=limit))
    return response.to_dict().get("instances", [])


def fetch_clb_instances(limit: int = 100) -> List[Dict]:
    response = CLBApi().describe_load_balancers(
        DescribeLoadBalancersRequest(page_size=limit, page_number=1)
    )
    return response.to_dict().get("load_balancers", [])


def normalize_listener_page_size(limit: int) -> int:
    # CLB/ALB 监听器分页对 page_size 较敏感，统一限制在常见可接受范围内。
    return max(1, min(limit, 100))


def fetch_clb_listeners(limit: int = 200, load_balancer_id: Optional[str] = None) -> List[Dict]:
    normalized_limit = normalize_listener_page_size(limit)
    request = DescribeClbListenersRequest(
        page_size=normalized_limit,
        page_number=1,
        load_balancer_id=load_balancer_id,
    )
    try:
        response = CLBApi().describe_listeners(request)
    except Exception as exc:
        if "InvalidPaging.Malformed" not in str(exc):
            raise
        # 个别地域或 SDK 版本下即使传了合法值也可能被接口拒绝，降到更保守值后再试一次。
        response = CLBApi().describe_listeners(
            DescribeClbListenersRequest(
                page_size=20,
                page_number=1,
                load_balancer_id=load_balancer_id,
            )
        )
    response_dict = response.to_dict()
    return (
        response_dict.get("listeners")
        or response_dict.get("items")
        or response_dict.get("listener_set")
        or response_dict.get("ListenerSet")
        or []
    )


def fetch_alb_instances(limit: int = 100) -> List[Dict]:
    response = ALBApi().describe_load_balancers(
        DescribeAlbLoadBalancersRequest(page_size=limit, page_number=1)
    )
    response_dict = response.to_dict()
    return response_dict.get("load_balancers") or response_dict.get("items") or []


def fetch_alb_listeners(limit: int = 200, load_balancer_id: Optional[str] = None) -> List[Dict]:
    response = ALBApi().describe_listeners(
        DescribeAlbListenersRequest(
            page_size=normalize_listener_page_size(limit),
            page_number=1,
            load_balancer_id=load_balancer_id,
        )
    )
    response_dict = response.to_dict()
    return response_dict.get("listeners") or response_dict.get("items") or []


def fetch_rds_instances() -> List[Dict]:
    # 这里直接取 object，绕过 SDK 对 SingleNode 枚举的错误校验。
    api = RDSMYSQLApi()
    body = ListDBInstancesRequest(region=os.getenv("VOLCENGINE_REGION", "cn-beijing"))
    response = api.api_client.call_api(
        "/ListDBInstances/2018-01-01/rds_mysql/post/",
        "POST",
        {},
        [],
        {"Accept": "application/json", "Content-Type": "application/json"},
        body=body,
        post_params=[],
        files={},
        response_type="object",
        auth_settings=["volcengineSign"],
        async_req=False,
        _return_http_data_only=True,
        _preload_content=True,
    )
    return response.get("Datas", [])


def risk_level(value: Optional[float]) -> str:
    if value is None:
        return "unknown"
    if value >= 90:
        return "high"
    if value >= 80:
        return "medium"
    if value >= 70:
        return "low"
    return "safe"


def missing_metrics(metric_map: Dict[str, Dict]) -> List[str]:
    return [name for name, summary in metric_map.items() if not summary_has_data(summary)]


def format_metric_gap(metric_names: List[str]) -> str:
    return "、".join(metric_names)


def pick_primary_metric_value(history_summary: Dict, fallback_value: Optional[float]) -> Optional[float]:
    history_value = summary_metric_value(history_summary)
    if history_value is not None:
        return history_value
    return fallback_value


def ecs_recommendation(cpu_summary: Dict, mem_summary: Dict, disk_summary: Dict) -> str:
    gaps = missing_metrics({"CPU": cpu_summary, "内存": mem_summary, "磁盘": disk_summary})
    if gaps:
        return f"关键监控缺失（{format_metric_gap(gaps)}），暂不下稳定性结论"
    cpu_p95 = cpu_summary.get("p95")
    mem_p95 = mem_summary.get("p95")
    disk_p95 = disk_summary.get("p95")
    if (
        cpu_p95 is not None
        and cpu_p95 < 20
        and mem_p95 is not None
        and mem_p95 < 30
        and disk_p95 is not None
        and disk_p95 < 50
    ):
        return "低利用率，建议进入缩容候选池"
    if any(risk_level(value) in {"medium", "high"} for value in (cpu_p95, mem_p95, disk_p95)):
        return "存在容量风险，建议优先关注"
    return "当前水位平稳，建议继续观察"


def rds_recommendation(
    cpu_history: Dict,
    mem_history: Dict,
    disk_history: Dict,
    cpu_snapshot: Optional[float],
    mem_snapshot: Optional[float],
    disk_snapshot: Optional[float],
    conn_summary: Dict,
) -> str:
    cpu_value = pick_primary_metric_value(cpu_history, cpu_snapshot)
    mem_value = pick_primary_metric_value(mem_history, mem_snapshot)
    disk_value = pick_primary_metric_value(disk_history, disk_snapshot)
    conn_p95 = conn_summary.get("p95")
    if cpu_value is None or mem_value is None or disk_value is None:
        return "关键监控缺失，暂不下结论，建议先补齐历史资源监控"
    if (
        cpu_value < 20
        and mem_value < 30
        and disk_value < 50
        and conn_p95 is not None
        and conn_p95 < 10
    ):
        return "更像成本优化型资源，建议评估降规格"
    if any(risk_level(value) in {"medium", "high"} for value in (cpu_value, mem_value, disk_value, conn_p95)):
        return "存在容量风险，建议优先排查"
    return "当前无明显容量风险，建议继续观察"


def rds_metric_candidates(metric_name: str) -> List[Dict[str, str]]:
    if metric_name == "cpu":
        return [
            {"namespace": "VCM_RDS_MySQL", "sub_namespace": "resource_monitor_new", "metric_name": "CpuUtil"},
            {"namespace": "VCM_RDS_MySQL", "sub_namespace": "resource_monitor", "metric_name": "CpuUtil"},
            {"namespace": "VCM_RDS_MySQL", "sub_namespace": "resource_monitor_new", "metric_name": "CpuUtilDev"},
        ]
    if metric_name == "mem":
        return [
            {"namespace": "VCM_RDS_MySQL", "sub_namespace": "resource_monitor_new", "metric_name": "MemUtil"},
            {"namespace": "VCM_RDS_MySQL", "sub_namespace": "resource_monitor", "metric_name": "MemUtil"},
        ]
    if metric_name == "disk":
        return [
            {"namespace": "VCM_RDS_MySQL", "sub_namespace": "resource_monitor_new", "metric_name": "DiskUtil"},
            {"namespace": "VCM_RDS_MySQL", "sub_namespace": "resource_monitor", "metric_name": "DiskUtil"},
        ]
    if metric_name == "qps":
        return [
            {"namespace": "VCM_RDS_MySQL", "sub_namespace": "engine_monitor", "metric_name": "QPS"},
            {"namespace": "VCM_RDS_MySQL", "sub_namespace": "proxy_monitor", "metric_name": "ProxyEndpointQPS"},
        ]
    if metric_name == "conn_usage":
        return [
            {"namespace": "VCM_RDS_MySQL", "sub_namespace": "engine_monitor", "metric_name": "ConnUsage"},
            {
                "namespace": "VCM_RDS_MySQL",
                "sub_namespace": "proxy_monitor",
                "metric_name": "ProxyEndpointUsedConnRatio",
            },
        ]
    raise ValueError(f"未知 RDS 指标类型: {metric_name}")


def alb_metric_candidates(metric_name: str) -> List[Dict[str, str]]:
    if metric_name == "qps":
        return [{"namespace": "VCM_ALB", "sub_namespace": "listener", "metric_name": "listener_qps"}]
    if metric_name == "max_conn":
        return [{"namespace": "VCM_ALB", "sub_namespace": "listener", "metric_name": "listener_max_conn"}]
    if metric_name == "new_conn":
        return [{"namespace": "VCM_ALB", "sub_namespace": "listener", "metric_name": "listener_new_conn"}]
    if metric_name == "in_bytes":
        return [{"namespace": "VCM_ALB", "sub_namespace": "listener", "metric_name": "listener_in_bytes"}]
    if metric_name == "out_bytes":
        return [{"namespace": "VCM_ALB", "sub_namespace": "listener", "metric_name": "listener_out_bytes"}]
    if metric_name == "lost_conn":
        return [{"namespace": "VCM_ALB", "sub_namespace": "listener", "metric_name": "listener_lost_conn"}]
    if metric_name == "http_5xx":
        return [{"namespace": "VCM_ALB", "sub_namespace": "listener", "metric_name": "listener_http_5xx_recv_count"}]
    raise ValueError(f"未知 ALB 指标类型: {metric_name}")


def clb_metric_candidates(metric_name: str) -> List[Dict[str, str]]:
    if metric_name == "qps":
        return [{"namespace": "VCM_CLB", "sub_namespace": "listener", "metric_name": "listener_qps"}]
    if metric_name == "max_conn":
        return [{"namespace": "VCM_CLB", "sub_namespace": "listener", "metric_name": "listener_max_conn"}]
    if metric_name == "new_conn":
        return [{"namespace": "VCM_CLB", "sub_namespace": "listener", "metric_name": "listener_new_conn"}]
    if metric_name == "in_bytes":
        return [{"namespace": "VCM_CLB", "sub_namespace": "listener", "metric_name": "listener_in_bytes"}]
    if metric_name == "out_bytes":
        return [{"namespace": "VCM_CLB", "sub_namespace": "listener", "metric_name": "listener_out_bytes"}]
    raise ValueError(f"未知 CLB 指标类型: {metric_name}")


def alb_extra_dimensions(listener_id: str) -> List[Dict[str, str]]:
    return [{"name": "ListenerID", "value": listener_id}]


def clb_extra_dimensions(listener_id: str) -> List[Dict[str, str]]:
    return [{"name": "ListenerID", "value": listener_id}]


def summarize_summary_field(summaries: List[Dict], field: str) -> Optional[float]:
    values = [summary.get(field) for summary in summaries if summary.get(field) is not None]
    if not values:
        return None
    return round(max(float(value) for value in values), 4)


def merge_summary_candidates(summaries: List[Dict]) -> Dict[str, Optional[float]]:
    merged: Dict[str, Optional[float]] = {
        "count": sum(int(summary.get("count") or 0) for summary in summaries),
        "avg": summarize_summary_field(summaries, "avg"),
        "max": summarize_summary_field(summaries, "max"),
        "p95": summarize_summary_field(summaries, "p95"),
    }
    sources = []
    attempted_sources = []
    errors = []
    for summary in summaries:
        source = summary.get("source")
        if source and source not in sources:
            sources.append(source)
        for item in summary.get("attempted_sources") or []:
            if item not in attempted_sources:
                attempted_sources.append(item)
        error = summary.get("error")
        if error:
            errors.append(str(error))
    if sources:
        merged["sources"] = sources
    if attempted_sources:
        merged["attempted_sources"] = attempted_sources
    if errors and not merged["count"]:
        merged["error"] = "; ".join(errors[:3])
    return merged


def alb_recommendation(qps_summary: Dict, max_conn_summary: Dict, new_conn_summary: Dict, lost_conn_summary: Dict, http_5xx_summary: Dict) -> str:
    gaps = missing_metrics({"QPS": qps_summary, "并发连接": max_conn_summary, "新建连接": new_conn_summary})
    if gaps:
        return f"关键监控缺失（{format_metric_gap(gaps)}），暂不下结论"
    lost_conn_p95 = lost_conn_summary.get("p95") or 0
    http_5xx_p95 = http_5xx_summary.get("p95") or 0
    if lost_conn_p95 > 0 or http_5xx_p95 > 0:
        return "入口层存在异常信号，建议优先排查"
    return "已纳入入口层流量观测，当前未见明确异常，建议继续观察"


def clb_recommendation(
    qps_summary: Dict,
    max_conn_summary: Dict,
    new_conn_summary: Dict,
    in_bytes_summary: Dict,
    out_bytes_summary: Dict,
    missing_primary_metrics: List[str],
) -> str:
    if missing_primary_metrics:
        return f"关键监控缺失（{format_metric_gap(missing_primary_metrics)}），暂不下结论"
    if any(summary_has_data(summary) for summary in (qps_summary, max_conn_summary, new_conn_summary, in_bytes_summary, out_bytes_summary)):
        return "已获取入口层监控摘要，后续需结合实例规格上限做使用率换算"
    return "当前未取到可用监控，建议先核对计费方式、监听器协议和云监控口径"


def infer_clb_billing_type(instance: Dict) -> Optional[str]:
    for key in (
        "load_balancer_billing_type",
        "LoadBalancerBillingType",
        "billing_type",
        "BillingType",
    ):
        value = instance.get(key)
        if value:
            return str(value)
    return None


def clb_monitoring_capability(instance: Dict) -> Dict[str, Optional[str]]:
    billing_type = infer_clb_billing_type(instance)
    if not billing_type:
        return {
            "billing_type": None,
            "auto_metrics_supported": None,
            "reason": "未返回计费方式字段，无法自动判断 CLB 监控口径是否完整",
        }

    normalized = billing_type.lower()
    if any(keyword in normalized for keyword in ("lcu", "usage", "used", "traffic", "flow", "actual")):
        return {
            "billing_type": billing_type,
            "auto_metrics_supported": False,
            "reason": "按使用量或按实际流量类计费的 CLB，连接/QPS/带宽使用率类指标可能不上报到云监控",
        }
    return {
        "billing_type": billing_type,
        "auto_metrics_supported": True,
        "reason": "可以继续在云监控 VCM_CLB 指标文档里补齐带宽、连接数和 QPS 口径",
    }


def infer_alb_billing_type(instance: Dict) -> Optional[str]:
    for key in (
        "load_balancer_billing_type",
        "LoadBalancerBillingType",
        "billing_type",
        "BillingType",
    ):
        value = instance.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def alb_monitoring_capability(instance: Dict) -> Dict[str, Optional[str]]:
    billing_type = infer_alb_billing_type(instance)
    return {
        "billing_type": billing_type,
        "auto_metrics_supported": True,
        "reason": "ALB 已接入监听器维度的 QPS、连接数与带宽摘要，结论仍需结合异常指标和业务规则继续校验",
    }


def collect_data_gaps(items: List[Dict], key: str = "data_gaps") -> List[str]:
    gaps: List[str] = []
    for item in items:
        gaps.extend(item.get(key, []))
    return gaps


def forecast_confidence(data_gaps: List[str], has_growth_factor: bool) -> str:
    if len(data_gaps) >= 4:
        return "低"
    if len(data_gaps) >= 2 or not has_growth_factor:
        return "中"
    return "高"


def scale_metric(value: Optional[float], growth_factor: Optional[float]) -> Optional[float]:
    if value is None or growth_factor is None:
        return value
    return round(value * (1 + growth_factor), 4)


def ecs_layer_signal(item: Dict, growth_factor: Optional[float]) -> Optional[Dict]:
    candidates = [
        ("CPU", item["cpu_total_30d"].get("p95")),
        ("内存", item["memory_used_utilization_30d"].get("p95")),
        ("磁盘", item["disk_usage_utilization_30d"].get("p95")),
    ]
    valid = [(name, value) for name, value in candidates if value is not None]
    if not valid:
        return None
    metric_name, metric_value = max(valid, key=lambda item: item[1])
    return {
        "layer": "ECS",
        "resource_name": item.get("instance_name") or item.get("instance_id"),
        "metric_name": metric_name,
        "current_value": round(metric_value, 4),
        "projected_value": scale_metric(metric_value, growth_factor),
    }


def rds_layer_signal(item: Dict, growth_factor: Optional[float]) -> Optional[Dict]:
    candidates = [
        ("CPU", pick_primary_metric_value(item["cpu_pct_30d"], item.get("cpu_pct_snapshot"))),
        ("内存", pick_primary_metric_value(item["mem_pct_30d"], item.get("mem_pct_snapshot"))),
        ("磁盘", pick_primary_metric_value(item["disk_pct_30d"], item.get("disk_pct_snapshot"))),
        ("连接", item["conn_usage_30d"].get("p95")),
    ]
    valid = [(name, value) for name, value in candidates if value is not None]
    if not valid:
        return None
    metric_name, metric_value = max(valid, key=lambda item: item[1])
    return {
        "layer": "RDS MySQL",
        "resource_name": item.get("instance_name") or item.get("instance_id"),
        "metric_name": metric_name,
        "current_value": round(metric_value, 4),
        "projected_value": scale_metric(metric_value, growth_factor),
    }


def alb_layer_signal(item: Dict, growth_factor: Optional[float]) -> Optional[Dict]:
    if (item.get("lost_conn_30d") or {}).get("p95"):
        current_value = float(item["lost_conn_30d"]["p95"])
        return {
            "layer": "ALB",
            "resource_name": item.get("load_balancer_name") or item.get("load_balancer_id"),
            "metric_name": "丢连接",
            "current_value": round(current_value, 4),
            "projected_value": scale_metric(current_value, growth_factor),
        }
    if (item.get("http_5xx_30d") or {}).get("p95"):
        current_value = float(item["http_5xx_30d"]["p95"])
        return {
            "layer": "ALB",
            "resource_name": item.get("load_balancer_name") or item.get("load_balancer_id"),
            "metric_name": "5xx",
            "current_value": round(current_value, 4),
            "projected_value": scale_metric(current_value, growth_factor),
        }
    return None


def pick_top_signal(signals: List[Optional[Dict]], key: str) -> Optional[Dict]:
    valid = [signal for signal in signals if signal and signal.get(key) is not None]
    if not valid:
        return None
    return max(valid, key=lambda item: item[key])


def filter_by_resource_ids(items: List[Dict], resource_ids: Optional[List[str]], key: str) -> List[Dict]:
    if resource_ids is None:
        return items
    allowed_ids = {str(item) for item in resource_ids}
    return [item for item in items if str(item.get(key) or "") in allowed_ids]


def build_forecast(report: Dict, growth_factor: Optional[float], link_name: Optional[str]) -> Dict:
    topology_scope = report.get("topology_scope")
    ecs_signal = pick_top_signal(
        [ecs_layer_signal(item, growth_factor) for item in report["ecs"]],
        "projected_value" if growth_factor is not None else "current_value",
    )
    alb_signal = pick_top_signal(
        [alb_layer_signal(item, growth_factor) for item in report["alb"]["instances"]],
        "projected_value" if growth_factor is not None else "current_value",
    )
    rds_signal = pick_top_signal(
        [rds_layer_signal(item, growth_factor) for item in report["rds"]],
        "projected_value" if growth_factor is not None else "current_value",
    )
    signals = [signal for signal in (alb_signal, ecs_signal, rds_signal) if signal]
    current_bottleneck = pick_top_signal(signals, "current_value")
    projected_bottleneck = pick_top_signal(
        signals,
        "projected_value" if growth_factor is not None else "current_value",
    )

    clb_metric_gaps = [item for item in report["clb"]["instances"] if item.get("missing_primary_metrics")]
    data_gaps = (
        collect_data_gaps(report["ecs"])
        + collect_data_gaps(report["rds"])
        + report["clb"].get("data_gaps", [])
        + report["alb"].get("data_gaps", [])
        + (topology_scope or {}).get("data_gaps", [])
    )
    if report["alb"]["instances"]:
        missing_metric_albs = [item for item in report["alb"]["instances"] if item.get("missing_primary_metrics")]
        data_gaps.extend(
            [
                f"{item.get('load_balancer_name') or item.get('load_balancer_id')}: 已命中当前拓扑链路，但仍缺少 {format_metric_gap(item['missing_primary_metrics'])} 监控"
                for item in missing_metric_albs
            ]
        )

    scaling_order: List[str] = []
    if topology_scope and topology_scope.get("enabled"):
        counts = topology_scope.get("resource_counts", {})
        scaling_order.append(
            "本次先按拓扑命中的链路资源收敛评估范围："
            f"CLB {counts.get('clb', 0)} 个 / ALB {counts.get('alb', 0)} 个 / ECS {counts.get('ecs', 0)} 台 / RDS MySQL {counts.get('rds_mysql', 0)} 个"
        )
    if projected_bottleneck:
        scaling_order.append(
            f"优先关注 {projected_bottleneck['layer']}，当前最紧的是 `{projected_bottleneck['resource_name']}` 的 {projected_bottleneck['metric_name']}"
        )
    elif topology_scope and topology_scope.get("enabled"):
        scaling_order.append("当前拓扑命中的链路资源里暂未识别出可量化的 ECS/RDS 瓶颈，当前只能先列出数据缺口")
    if clb_metric_gaps:
        scaling_order.append("CLB 已先尝试拉取监听器级监控；对仍缺失的实例，需要继续结合计费方式、监听器协议和云监控口径排查")
    elif report["clb"]["instances"]:
        scaling_order.append("链路内命中的 CLB 资源已纳入监听器级连接/QPS/带宽摘要；若要形成结论性扩容判断，还需结合规格上限做使用率换算")
    if report["alb"]["instances"]:
        scaling_order.append("链路内命中的 ALB 资源已纳入监听器级 QPS/连接/带宽观测，并结合异常信号辅助判断入口层风险")
    scaling_order.append("扩容后优先回看延迟、错误率、CPU/内存、连接和带宽是否回落到安全区间")

    assumptions = ["默认不假设所有资源与客户数严格线性增长，只把增长因子作为场景输入"]
    if topology_scope and topology_scope.get("enabled"):
        assumptions.insert(
            0,
            f"评估范围优先来自拓扑文件 `{topology_scope['source']}`，仅分析当前拓扑命中的已支持资源类型（当前为 CLB/ALB/ECS/RDS MySQL）",
        )
    else:
        assumptions.insert(0, f"未命中可用拓扑文件时，默认按项目 `{report['meta']['project_name']}` 下的资源集合做容量评估，不预设固定链路结构")
    if growth_factor is not None:
        assumptions.append(f"场景增长假设为 {round(growth_factor * 100, 2)}%")
    else:
        assumptions.append("未提供明确增长因子，本次只基于当前水位做链路瓶颈排序")

    return {
        "link_name": link_name or report["meta"]["project_name"],
        "current_bottleneck": current_bottleneck,
        "projected_bottleneck": projected_bottleneck,
        "scaling_order": scaling_order,
        "validation_metrics": [
            "链路入口资源（如 CLB/ALB）：连接数、新建连接数、QPS、出入带宽、错误率",
            "链路计算资源（如 ECS）：CPU、内存、线程池/连接池、接口延迟",
            "链路数据资源（如 RDS MySQL）：CPU、内存、磁盘、QPS、连接使用率、慢 SQL",
        ],
        "assumptions": assumptions,
        "topology_scope": topology_scope,
        "topology_paths": (topology_scope or {}).get("paths", []),
        "data_gaps": data_gaps,
        "confidence": forecast_confidence(data_gaps, growth_factor is not None),
    }


def build_ecs_report(instances: List[Dict], now: int) -> List[Dict]:
    items: List[Dict] = []
    thirty_days_ago = now - 30 * 24 * 3600
    seven_days_ago = now - 7 * 24 * 3600

    for instance in instances:
        resource_id = instance.get("instance_id")
        volume_id = (instance.get("volumes") or [{}])[0].get("volume_id")

        cpu_summary = safe_fetch_metric_summary(
            namespace="VCM_ECS",
            sub_namespace="Instance",
            metric_name="CpuTotal",
            resource_id=resource_id,
            period="1h",
            start_time=thirty_days_ago,
            end_time=now,
        )
        memory_summary = safe_fetch_metric_summary(
            namespace="VCM_ECS",
            sub_namespace="Instance",
            metric_name="MemoryUsedUtilization",
            resource_id=resource_id,
            period="1h",
            start_time=thirty_days_ago,
            end_time=now,
        )
        disk_usage_summary = safe_fetch_metric_summary(
            namespace="VCM_ECS",
            sub_namespace="Instance",
            metric_name="DiskUsageUtilization",
            resource_id=resource_id,
            period="1h",
            start_time=thirty_days_ago,
            end_time=now,
            extra_dimensions=[{"name": "VolumeId", "value": volume_id}] if volume_id else None,
        )
        disk_write_iops_summary = safe_fetch_metric_summary(
            namespace="VCM_ECS",
            sub_namespace="Instance",
            metric_name="DiskWriteIOPS",
            resource_id=resource_id,
            period="1h",
            start_time=seven_days_ago,
            end_time=now,
            extra_dimensions=[
                {"name": "VolumeId", "value": volume_id},
                {"name": "DiskName", "value": "vda"},
            ]
            if volume_id
            else None,
        )

        items.append(
            {
                "instance_id": resource_id,
                "instance_name": instance.get("instance_name"),
                "project_name": instance.get("project_name"),
                "instance_type_id": instance.get("instance_type_id"),
                "memory_size_mb": instance.get("memory_size"),
                "status": instance.get("status"),
                "cpu_total_30d": cpu_summary,
                "memory_used_utilization_30d": memory_summary,
                "disk_usage_utilization_30d": disk_usage_summary,
                "disk_write_iops_7d": disk_write_iops_summary,
                "data_gaps": [
                    f"{instance.get('instance_name') or resource_id}: 缺少 {gap} 历史监控"
                    for gap in missing_metrics(
                        {
                            "CPU": cpu_summary,
                            "内存": memory_summary,
                            "磁盘": disk_usage_summary,
                        }
                    )
                ],
                "recommendation": ecs_recommendation(cpu_summary, memory_summary, disk_usage_summary),
            }
        )
    return items


def build_rds_report(instances: List[Dict], now: int) -> List[Dict]:
    items: List[Dict] = []
    thirty_days_ago = now - 30 * 24 * 3600

    for instance in instances:
        resource_id = instance.get("InstanceId")
        cpu_summary = safe_fetch_metric_summary_candidates(
            rds_metric_candidates("cpu"), resource_id, "1h", thirty_days_ago, now
        )
        mem_summary = safe_fetch_metric_summary_candidates(
            rds_metric_candidates("mem"), resource_id, "1h", thirty_days_ago, now
        )
        disk_summary = safe_fetch_metric_summary_candidates(
            rds_metric_candidates("disk"), resource_id, "1h", thirty_days_ago, now
        )
        qps_summary = safe_fetch_metric_summary_candidates(
            rds_metric_candidates("qps"), resource_id, "1h", thirty_days_ago, now
        )
        conn_summary = safe_fetch_metric_summary_candidates(
            rds_metric_candidates("conn_usage"), resource_id, "1h", thirty_days_ago, now
        )

        cpu_snapshot = instance.get("NodeCPUUsedPercentage")
        mem_snapshot = instance.get("NodeMemoryUsedPercentage")
        disk_snapshot = instance.get("NodeSpaceUsedPercentage")
        metric_gaps = []
        if not summary_has_data(cpu_summary) and cpu_snapshot is None:
            metric_gaps.append(f"{instance.get('InstanceName') or resource_id}: 缺少 CPU 历史与快照监控")
        if not summary_has_data(mem_summary) and mem_snapshot is None:
            metric_gaps.append(f"{instance.get('InstanceName') or resource_id}: 缺少内存历史与快照监控")
        if not summary_has_data(disk_summary) and disk_snapshot is None:
            metric_gaps.append(f"{instance.get('InstanceName') or resource_id}: 缺少磁盘历史与快照监控")
        if not summary_has_data(conn_summary):
            metric_gaps.append(f"{instance.get('InstanceName') or resource_id}: 缺少连接使用率历史监控")

        items.append(
            {
                "instance_id": resource_id,
                "instance_name": instance.get("InstanceName"),
                "project_name": instance.get("ProjectName"),
                "instance_spec": instance.get("InstanceSpecStr"),
                "status": instance.get("InstanceStatus"),
                "cpu_pct_snapshot": cpu_snapshot,
                "mem_pct_snapshot": mem_snapshot,
                "disk_pct_snapshot": disk_snapshot,
                "cpu_pct_30d": cpu_summary,
                "mem_pct_30d": mem_summary,
                "disk_pct_30d": disk_summary,
                "qps_30d": qps_summary,
                "conn_usage_30d": conn_summary,
                "data_gaps": metric_gaps,
                "recommendation": rds_recommendation(
                    cpu_summary,
                    mem_summary,
                    disk_summary,
                    cpu_snapshot,
                    mem_snapshot,
                    disk_snapshot,
                    conn_summary,
                ),
            }
        )
    return items


def clb_listener_supports_qps(listener: Dict) -> bool:
    protocol = str(listener.get("protocol") or "").strip().upper()
    return protocol in {"HTTP", "HTTPS"}


def build_clb_gap_reason(
    item: Dict,
    monitoring_capability: Dict[str, Optional[str]],
    missing_primary_metrics: List[str],
    has_l7_listener: bool,
) -> str:
    resource_name = item.get("load_balancer_name") or item.get("load_balancer_id")
    reason = f"{resource_name}: 默认已尝试拉取 CLB 监听器监控，但缺少 {format_metric_gap(missing_primary_metrics)}"
    details: List[str] = []
    if monitoring_capability["auto_metrics_supported"] is False:
        details.append("当前计费方式下这些指标可能不上报到云监控")
    elif monitoring_capability["auto_metrics_supported"] is None:
        details.append("当前未返回计费方式，无法进一步判断产品口径限制")
    if not has_l7_listener:
        details.append("实例下未发现 HTTP/HTTPS 监听器，七层 QPS 指标不适用")
    if details:
        reason = f"{reason}；" + "；".join(details)
    return reason


def build_clb_report(instances: List[Dict], now: int) -> Dict:
    data_gaps: List[str] = []
    normalized_items = []
    thirty_days_ago = now - 30 * 24 * 3600
    for item in instances:
        load_balancer_id = item.get("load_balancer_id")
        monitoring_capability = clb_monitoring_capability(item)
        listeners = fetch_clb_listeners(load_balancer_id=load_balancer_id) if load_balancer_id else []
        listener_items = []
        qps_summaries: List[Dict] = []
        max_conn_summaries: List[Dict] = []
        new_conn_summaries: List[Dict] = []
        in_bytes_summaries: List[Dict] = []
        out_bytes_summaries: List[Dict] = []

        for listener in listeners:
            listener_id = listener.get("listener_id")
            if not listener_id or not load_balancer_id:
                continue
            extra_dimensions = clb_extra_dimensions(listener_id)
            qps_summary = build_empty_summary()
            if clb_listener_supports_qps(listener):
                qps_summary = safe_fetch_metric_summary_candidates(
                    clb_metric_candidates("qps"), load_balancer_id, "1h", thirty_days_ago, now, extra_dimensions=extra_dimensions
                )
                qps_summaries.append(qps_summary)
            max_conn_summary = safe_fetch_metric_summary_candidates(
                clb_metric_candidates("max_conn"), load_balancer_id, "1h", thirty_days_ago, now, extra_dimensions=extra_dimensions
            )
            new_conn_summary = safe_fetch_metric_summary_candidates(
                clb_metric_candidates("new_conn"), load_balancer_id, "1h", thirty_days_ago, now, extra_dimensions=extra_dimensions
            )
            in_bytes_summary = safe_fetch_metric_summary_candidates(
                clb_metric_candidates("in_bytes"), load_balancer_id, "1h", thirty_days_ago, now, extra_dimensions=extra_dimensions
            )
            out_bytes_summary = safe_fetch_metric_summary_candidates(
                clb_metric_candidates("out_bytes"), load_balancer_id, "1h", thirty_days_ago, now, extra_dimensions=extra_dimensions
            )
            max_conn_summaries.append(max_conn_summary)
            new_conn_summaries.append(new_conn_summary)
            in_bytes_summaries.append(in_bytes_summary)
            out_bytes_summaries.append(out_bytes_summary)
            listener_items.append(
                {
                    "listener_id": listener_id,
                    "listener_name": listener.get("listener_name"),
                    "protocol": listener.get("protocol"),
                    "port": listener.get("port"),
                    "qps_30d": qps_summary,
                    "max_conn_30d": max_conn_summary,
                    "new_conn_30d": new_conn_summary,
                    "in_bytes_30d": in_bytes_summary,
                    "out_bytes_30d": out_bytes_summary,
                }
            )

        qps_summary = merge_summary_candidates(qps_summaries)
        max_conn_summary = merge_summary_candidates(max_conn_summaries)
        new_conn_summary = merge_summary_candidates(new_conn_summaries)
        in_bytes_summary = merge_summary_candidates(in_bytes_summaries)
        out_bytes_summary = merge_summary_candidates(out_bytes_summaries)
        has_l7_listener = any(clb_listener_supports_qps(listener) for listener in listener_items)
        metric_map = {
            "并发连接": max_conn_summary,
            "新建连接": new_conn_summary,
            "入向带宽": in_bytes_summary,
            "出向带宽": out_bytes_summary,
        }
        if has_l7_listener:
            metric_map["QPS"] = qps_summary
        missing_primary_metrics = missing_metrics(metric_map)
        item_data_gaps: List[str] = []
        if not listeners:
            item_data_gaps.append(
                f"{item.get('load_balancer_name') or item.get('load_balancer_id')}: 未识别到监听器，当前无法形成监听器级容量评估"
            )
        elif missing_primary_metrics:
            item_data_gaps.append(
                build_clb_gap_reason(item, monitoring_capability, missing_primary_metrics, has_l7_listener)
            )
        data_gaps.extend(item_data_gaps)
        normalized_items.append(
            {
                "load_balancer_id": load_balancer_id,
                "load_balancer_name": item.get("load_balancer_name"),
                "project_name": item.get("project_name"),
                "load_balancer_spec": item.get("load_balancer_spec"),
                "status": item.get("status"),
                "type": item.get("type"),
                "listener_count": len(listener_items),
                "listeners": listener_items,
                "qps_30d": qps_summary,
                "max_conn_30d": max_conn_summary,
                "new_conn_30d": new_conn_summary,
                "in_bytes_30d": in_bytes_summary,
                "out_bytes_30d": out_bytes_summary,
                "qps_expected": has_l7_listener,
                "missing_primary_metrics": missing_primary_metrics,
                "data_gaps": item_data_gaps,
                "recommendation": clb_recommendation(
                    qps_summary,
                    max_conn_summary,
                    new_conn_summary,
                    in_bytes_summary,
                    out_bytes_summary,
                    missing_primary_metrics,
                ),
                "monitoring_capability": monitoring_capability,
                "protocol_note": None if has_l7_listener else "实例下未发现 HTTP/HTTPS 监听器，七层 QPS 默认不纳入判断",
            }
        )
    return {
        "instances": normalized_items,
        "data_gaps": data_gaps,
        "note": "CLB 当前会默认尝试拉取监听器级 QPS、连接和带宽摘要；若云监控无数据，再结合计费方式和监听器协议说明原因，不直接输出结论性扩容判断。",
    }


def build_alb_report(instances: List[Dict], now: int) -> Dict:
    data_gaps: List[str] = []
    normalized_items = []
    thirty_days_ago = now - 30 * 24 * 3600
    for item in instances:
        load_balancer_id = item.get("load_balancer_id")
        monitoring_capability = alb_monitoring_capability(item)
        listeners = fetch_alb_listeners(load_balancer_id=load_balancer_id) if load_balancer_id else []
        listener_items = []
        qps_summaries: List[Dict] = []
        max_conn_summaries: List[Dict] = []
        new_conn_summaries: List[Dict] = []
        in_bytes_summaries: List[Dict] = []
        out_bytes_summaries: List[Dict] = []
        lost_conn_summaries: List[Dict] = []
        http_5xx_summaries: List[Dict] = []

        for listener in listeners:
            listener_id = listener.get("listener_id")
            if not listener_id or not load_balancer_id:
                continue
            extra_dimensions = alb_extra_dimensions(listener_id)
            qps_summary = safe_fetch_metric_summary_candidates(
                alb_metric_candidates("qps"), load_balancer_id, "1h", thirty_days_ago, now, extra_dimensions=extra_dimensions
            )
            max_conn_summary = safe_fetch_metric_summary_candidates(
                alb_metric_candidates("max_conn"), load_balancer_id, "1h", thirty_days_ago, now, extra_dimensions=extra_dimensions
            )
            new_conn_summary = safe_fetch_metric_summary_candidates(
                alb_metric_candidates("new_conn"), load_balancer_id, "1h", thirty_days_ago, now, extra_dimensions=extra_dimensions
            )
            in_bytes_summary = safe_fetch_metric_summary_candidates(
                alb_metric_candidates("in_bytes"), load_balancer_id, "1h", thirty_days_ago, now, extra_dimensions=extra_dimensions
            )
            out_bytes_summary = safe_fetch_metric_summary_candidates(
                alb_metric_candidates("out_bytes"), load_balancer_id, "1h", thirty_days_ago, now, extra_dimensions=extra_dimensions
            )
            lost_conn_summary = safe_fetch_metric_summary_candidates(
                alb_metric_candidates("lost_conn"), load_balancer_id, "1h", thirty_days_ago, now, extra_dimensions=extra_dimensions
            )
            http_5xx_summary = safe_fetch_metric_summary_candidates(
                alb_metric_candidates("http_5xx"), load_balancer_id, "1h", thirty_days_ago, now, extra_dimensions=extra_dimensions
            )
            qps_summaries.append(qps_summary)
            max_conn_summaries.append(max_conn_summary)
            new_conn_summaries.append(new_conn_summary)
            in_bytes_summaries.append(in_bytes_summary)
            out_bytes_summaries.append(out_bytes_summary)
            lost_conn_summaries.append(lost_conn_summary)
            http_5xx_summaries.append(http_5xx_summary)
            listener_items.append(
                {
                    "listener_id": listener_id,
                    "listener_name": listener.get("listener_name"),
                    "protocol": listener.get("protocol"),
                    "port": listener.get("port"),
                    "qps_30d": qps_summary,
                    "max_conn_30d": max_conn_summary,
                    "new_conn_30d": new_conn_summary,
                    "in_bytes_30d": in_bytes_summary,
                    "out_bytes_30d": out_bytes_summary,
                    "lost_conn_30d": lost_conn_summary,
                    "http_5xx_30d": http_5xx_summary,
                }
            )

        qps_summary = merge_summary_candidates(qps_summaries)
        max_conn_summary = merge_summary_candidates(max_conn_summaries)
        new_conn_summary = merge_summary_candidates(new_conn_summaries)
        in_bytes_summary = merge_summary_candidates(in_bytes_summaries)
        out_bytes_summary = merge_summary_candidates(out_bytes_summaries)
        lost_conn_summary = merge_summary_candidates(lost_conn_summaries)
        http_5xx_summary = merge_summary_candidates(http_5xx_summaries)
        missing_primary_metrics = missing_metrics(
            {
                "QPS": qps_summary,
                "并发连接": max_conn_summary,
                "新建连接": new_conn_summary,
            }
        )
        if not listeners:
            data_gaps.append(
                f"{item.get('load_balancer_name') or item.get('load_balancer_id')}: 未识别到监听器，当前无法形成监听器级容量评估"
            )
        elif missing_primary_metrics:
            data_gaps.append(
                f"{item.get('load_balancer_name') or item.get('load_balancer_id')}: 缺少 {format_metric_gap(missing_primary_metrics)} 监控"
            )
        normalized_items.append(
            {
                "load_balancer_id": load_balancer_id,
                "load_balancer_name": item.get("load_balancer_name"),
                "project_name": item.get("project_name"),
                "load_balancer_spec": item.get("load_balancer_spec"),
                "status": item.get("status"),
                "type": item.get("type"),
                "listener_count": len(listener_items),
                "listeners": listener_items,
                "qps_30d": qps_summary,
                "max_conn_30d": max_conn_summary,
                "new_conn_30d": new_conn_summary,
                "in_bytes_30d": in_bytes_summary,
                "out_bytes_30d": out_bytes_summary,
                "lost_conn_30d": lost_conn_summary,
                "http_5xx_30d": http_5xx_summary,
                "missing_primary_metrics": missing_primary_metrics,
                "data_gaps": [
                    f"{item.get('load_balancer_name') or load_balancer_id}: 缺少 {gap} 监听器级监控"
                    for gap in missing_primary_metrics
                ],
                "recommendation": alb_recommendation(
                    qps_summary, max_conn_summary, new_conn_summary, lost_conn_summary, http_5xx_summary
                ),
                "monitoring_capability": monitoring_capability,
            }
        )
    return {
        "instances": normalized_items,
        "data_gaps": data_gaps,
        "note": "ALB 当前已纳入监听器维度的 QPS、连接数、带宽与异常信号观测；若缺少监听器或关键监控，仍只输出保守判断。",
    }


def build_summary(ecs_items: List[Dict], rds_items: List[Dict], clb_items: Dict, alb_items: Dict) -> Dict:
    ecs_low = sum(1 for item in ecs_items if "缩容候选池" in item["recommendation"])
    rds_low = sum(1 for item in rds_items if "成本优化型" in item["recommendation"])
    incomplete_count = sum(1 for item in ecs_items if "关键监控缺失" in item["recommendation"])
    incomplete_count += sum(1 for item in rds_items if "关键监控缺失" in item["recommendation"])
    return {
        "ecs_total": len(ecs_items),
        "ecs_low_utilization_candidates": ecs_low,
        "clb_total": len(clb_items["instances"]),
        "alb_total": len(alb_items["instances"]),
        "rds_total": len(rds_items),
        "rds_cost_optimization_candidates": rds_low,
        "incomplete_resource_count": incomplete_count + len(clb_items.get("data_gaps", [])) + len(alb_items.get("data_gaps", [])),
    }


def render_markdown(report: Dict) -> str:
    summary = report["summary"]
    title = "# 容量预测报告" if report["meta"]["mode"] == "forecast" else "# 资源巡检报告"
    lines = [
        title,
        "",
        "## 摘要",
        f"- ECS: {summary['ecs_total']} 台，其中低利用率候选 {summary['ecs_low_utilization_candidates']} 台",
        f"- CLB: {summary['clb_total']} 个，已默认尝试拉取监听器级 QPS / 连接 / 带宽摘要",
        f"- ALB: {summary['alb_total']} 个，已增加监听器级 QPS / 连接 / 带宽摘要与异常信号判断",
        f"- RDS MySQL: {summary['rds_total']} 个，其中成本优化候选 {summary['rds_cost_optimization_candidates']} 个",
        f"- 数据待补或结论受限的资源/缺口: {summary['incomplete_resource_count']} 个",
        "",
    ]

    if report["meta"]["mode"] == "forecast":
        forecast = report["forecast"]
        current_bottleneck = forecast.get("current_bottleneck")
        projected_bottleneck = forecast.get("projected_bottleneck")
        topology_scope = forecast.get("topology_scope") or {}
        lines.extend(
            [
                "## 链路级趋势判断",
                f"- 链路范围: `{forecast['link_name']}`",
                f"- 置信度: {forecast['confidence']}",
                f"- 拓扑来源: `{topology_scope['source']}`" if topology_scope.get("enabled") and topology_scope.get("source") else "- 拓扑来源: 未指定或未命中，当前按项目范围评估",
                (
                    f"- 纳入评估资源: CLB {topology_scope.get('resource_counts', {}).get('clb', 0)} 个 / "
                    f"ALB {topology_scope.get('resource_counts', {}).get('alb', 0)} 个 / "
                    f"ECS {topology_scope.get('resource_counts', {}).get('ecs', 0)} 台 / "
                    f"RDS MySQL {topology_scope.get('resource_counts', {}).get('rds_mysql', 0)} 个"
                )
                if topology_scope.get("enabled")
                else "- 纳入评估资源: 当前按项目范围汇总",
                f"- 当前瓶颈: {current_bottleneck['layer']} / `{current_bottleneck['resource_name']}` / {current_bottleneck['metric_name']} = {format_value(current_bottleneck['current_value']) if current_bottleneck else 'N/A'}"
                if current_bottleneck
                else "- 当前瓶颈: 受数据缺口影响，暂无法自动判断",
                f"- 增长后最先吃紧的层: {projected_bottleneck['layer']} / `{projected_bottleneck['resource_name']}` / {projected_bottleneck['metric_name']} = {format_value(projected_bottleneck['projected_value']) if projected_bottleneck and projected_bottleneck.get('projected_value') is not None else format_value(projected_bottleneck['current_value'])}"
                if projected_bottleneck
                else "- 增长后最先吃紧的层: 暂无法自动判断",
                "",
            ]
        )
        if forecast.get("topology_paths"):
            lines.extend(["## 拓扑链路"])
            lines.extend([f"- {path}" for path in forecast["topology_paths"]])
            lines.append("")
        lines.extend(
            [
                "## 扩容顺序",
            ]
        )
        lines.extend([f"- {item}" for item in forecast["scaling_order"]])
        lines.extend(["", "## 验证指标"])
        lines.extend([f"- {item}" for item in forecast["validation_metrics"]])
        lines.extend(["", "## 前提假设"])
        lines.extend([f"- {item}" for item in forecast["assumptions"]])
        lines.extend(["", "## 资源明细"])

    lines.extend(
        [
        "## ECS",
        ]
    )

    for item in report["ecs"]:
        lines.extend(
            [
                f"- `{item['instance_name']}` (`{item['instance_id']}`): {item['recommendation']}",
                f"  - CPU 30d p95: {format_value(item['cpu_total_30d'].get('p95'))}",
                f"  - Memory 30d p95: {format_value(item['memory_used_utilization_30d'].get('p95'))}",
                f"  - Disk 30d p95: {format_value(item['disk_usage_utilization_30d'].get('p95'))}",
                f"  - DiskWriteIOPS 7d p95: {format_value(item['disk_write_iops_7d'].get('p95'), '')}",
            ]
        )
        if item["data_gaps"]:
            lines.extend([f"  - 数据缺口: {gap}" for gap in item["data_gaps"]])

    lines.extend(["", "## CLB"])
    for item in report["clb"]["instances"]:
        capability = item["monitoring_capability"]
        lines.extend(
            [
                f"- `{item['load_balancer_name']}` (`{item['load_balancer_id']}`): {item['recommendation']}",
                f"  - 规格: `{item['load_balancer_spec']}`，状态 `{item['status']}`，监听器数 `{item['listener_count']}`",
                f"  - 监控可获取性: {capability['auto_metrics_supported'] if capability['auto_metrics_supported'] is not None else 'unknown'}",
                f"  - 计费方式: {capability['billing_type'] or 'N/A'}",
                f"  - QPS 30d p95: {format_value(item['qps_30d'].get('p95'), '')}",
                f"  - 并发连接 30d p95: {format_value(item['max_conn_30d'].get('p95'), '')}",
                f"  - 新建连接 30d p95: {format_value(item['new_conn_30d'].get('p95'), '')}",
                f"  - 入向带宽 30d p95: {format_value(item['in_bytes_30d'].get('p95'), '')}",
                f"  - 出向带宽 30d p95: {format_value(item['out_bytes_30d'].get('p95'), '')}",
                f"  - 说明: {capability['reason']}",
            ]
        )
        if item.get("protocol_note"):
            lines.append(f"  - 协议说明: {item['protocol_note']}")
        if item["data_gaps"]:
            lines.extend([f"  - 数据缺口: {gap}" for gap in item["data_gaps"]])
    lines.append(f"- 说明: {report['clb']['note']}")

    lines.extend(["", "## ALB"])
    for item in report["alb"]["instances"]:
        capability = item["monitoring_capability"]
        lines.extend(
            [
                f"- `{item['load_balancer_name']}` (`{item['load_balancer_id']}`): {item['recommendation']}",
                f"  - 规格: `{item['load_balancer_spec']}`，状态 `{item['status']}`，监听器数 `{item['listener_count']}`",
                f"  - 监控可获取性: {capability['auto_metrics_supported'] if capability['auto_metrics_supported'] is not None else 'unknown'}",
                f"  - 计费方式: {capability['billing_type'] or 'N/A'}",
                f"  - QPS 30d p95: {format_value(item['qps_30d'].get('p95'), '')}",
                f"  - 并发连接 30d p95: {format_value(item['max_conn_30d'].get('p95'), '')}",
                f"  - 新建连接 30d p95: {format_value(item['new_conn_30d'].get('p95'), '')}",
                f"  - 入向带宽 30d p95: {format_value(item['in_bytes_30d'].get('p95'), '')}",
                f"  - 出向带宽 30d p95: {format_value(item['out_bytes_30d'].get('p95'), '')}",
                f"  - 丢连接 30d p95: {format_value(item['lost_conn_30d'].get('p95'), '')}",
                f"  - HTTP 5xx 30d p95: {format_value(item['http_5xx_30d'].get('p95'), '')}",
                f"  - 说明: {capability['reason']}",
            ]
        )
        if item["data_gaps"]:
            lines.extend([f"  - 数据缺口: {gap}" for gap in item["data_gaps"]])
    lines.append(f"- 说明: {report['alb']['note']}")

    lines.extend(["", "## RDS MySQL"])
    for item in report["rds"]:
        lines.extend(
            [
                f"- `{item['instance_name']}` (`{item['instance_id']}`): {item['recommendation']}",
                f"  - 当前 CPU: {format_value(item['cpu_pct_snapshot'])}",
                f"  - 当前内存: {format_value(item['mem_pct_snapshot'])}",
                f"  - 当前磁盘: {format_value(item['disk_pct_snapshot'])}",
                f"  - CPU 30d p95: {format_value(item['cpu_pct_30d'].get('p95'))}",
                f"  - 内存 30d p95: {format_value(item['mem_pct_30d'].get('p95'))}",
                f"  - 磁盘 30d p95: {format_value(item['disk_pct_30d'].get('p95'))}",
                f"  - QPS 30d p95: {format_value(item['qps_30d'].get('p95'), '')}",
                f"  - ConnUsage 30d p95: {format_value(item['conn_usage_30d'].get('p95'))}",
            ]
        )
        if item["data_gaps"]:
            lines.extend([f"  - 数据缺口: {gap}" for gap in item["data_gaps"]])

    lines.extend(
        [
            "",
            "## 建议清单",
            "- 先对低利用率 ECS 建立缩容候选池，建议保守降配后验证业务峰值。",
            "- 对 RDS MySQL 优先使用历史 CPU/内存/磁盘监控；若缺失，则先补口径再下容量结论。",
            "- CLB 默认先拉取监听器级带宽、连接数和 QPS 摘要；如果仍缺失，再结合计费方式和监听器协议解释原因。",
            "- ALB 当前已纳入监听器级 QPS、连接、带宽和异常信号摘要；如果存在丢连接、5xx 或关键监控缺失，优先回到监听器和转发规则排查。",
            "",
            "## 数据缺口",
            "- 如果某项关键监控取数失败，脚本会标记为“暂不下结论”，不再默认归类为继续观察。",
            "- CLB 当前尚未接入规格上限换算，因此已有监控摘要也只用于事实呈现和保守判断。",
            "- RDS MySQL 的历史资源监控仍依赖候选口径回退，若仍无数据，需要到控制台进一步核对 SubNamespace。",
        ]
    )
    for gap in report["clb"].get("data_gaps", []):
        lines.append(f"- {gap}")
    for gap in report["alb"].get("data_gaps", []):
        lines.append(f"- {gap}")
    forecast_gaps = report.get("forecast", {}).get("data_gaps", [])
    existing_gaps = report["clb"].get("data_gaps", []) + report["alb"].get("data_gaps", [])
    for gap in forecast_gaps:
        if gap not in existing_gaps:
            lines.append(f"- {gap}")
    return "\n".join(lines)


def filter_by_project(items: List[Dict], project_name: Optional[str], key: str) -> List[Dict]:
    if not project_name:
        return items
    return [item for item in items if item.get(key) == project_name]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="火山引擎资源巡检与水位评估")
    parser.add_argument("--env-path", default=".env", help=".env 路径")
    parser.add_argument("--project-name", default=None, help="项目名，可选")
    parser.add_argument("--region", default=None, help="地域，默认读取 .env")
    parser.add_argument(
        "--mode",
        choices=["audit", "forecast"],
        default="audit",
        help="执行模式：audit 为巡检，forecast 为链路级趋势判断",
    )
    parser.add_argument(
        "--growth-factor",
        type=float,
        default=None,
        help="增长因子，例如 0.1 表示增长 10%%",
    )
    parser.add_argument(
        "--link-name",
        default=None,
        help="链路名称；若存在 business_topologies/<link-name>/topology.json，则 forecast 模式会按该拓扑链路收敛资源范围",
    )
    parser.add_argument(
        "--topology-file",
        default=None,
        help="拓扑文件路径，forecast 模式下优先使用该文件做链路级资源筛选",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="markdown",
        help="输出格式",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env_path = Path(args.env_path)
    load_env(env_path)
    configure_sdk(args.region)

    now = int(time.time())
    topology_scope = None
    if args.mode == "forecast" and (args.topology_file or args.link_name):
        topology_path = resolve_topology_file(env_path, args.link_name, args.topology_file)
        if topology_path and topology_path.exists():
            topology_scope = build_topology_scope(load_json(topology_path), topology_path)
        else:
            topology_scope = build_missing_topology_scope(topology_path, args.link_name)

    ecs_items = filter_by_project(fetch_ecs_instances(), args.project_name, "project_name")
    clb_items = filter_by_project(fetch_clb_instances(), args.project_name, "project_name")
    alb_items = filter_by_project(fetch_alb_instances(), args.project_name, "project_name")
    rds_items = filter_by_project(fetch_rds_instances(), args.project_name, "ProjectName")
    if topology_scope and topology_scope.get("enabled"):
        ecs_items = filter_by_resource_ids(
            ecs_items, topology_scope["resource_ids"].get("ecs"), "instance_id"
        )
        clb_items = filter_by_resource_ids(
            clb_items, topology_scope["resource_ids"].get("clb"), "load_balancer_id"
        )
        alb_items = filter_by_resource_ids(
            alb_items, topology_scope["resource_ids"].get("alb"), "load_balancer_id"
        )
        rds_items = filter_by_resource_ids(
            rds_items, topology_scope["resource_ids"].get("rds_mysql"), "InstanceId"
        )

    report = {
        "meta": {
            "region": os.getenv("VOLCENGINE_REGION", "cn-beijing"),
            "project_name": args.project_name or "ALL",
            "generated_at": now,
            "mode": args.mode,
            "growth_factor": args.growth_factor,
            "link_name": args.link_name,
            "topology_file": topology_scope.get("source") if topology_scope else None,
        },
        "summary": {},
        "ecs": build_ecs_report(ecs_items, now),
        "clb": build_clb_report(clb_items, now),
        "alb": build_alb_report(alb_items, now),
        "rds": build_rds_report(rds_items, now),
        "topology_scope": topology_scope,
    }
    report["summary"] = build_summary(report["ecs"], report["rds"], report["clb"], report["alb"])
    if args.mode == "forecast":
        report["forecast"] = build_forecast(report, args.growth_factor, args.link_name)

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
