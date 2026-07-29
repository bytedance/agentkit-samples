#!/usr/bin/env python3
"""
Volcengine Cloud Detect API Client (SDK-based)

Usage:
    export VOLC_ACCESSKEY="your-ak"
    export VOLC_SECRETKEY="your-sk"

    python volc_detect.py <command> [args...]

All task-scoped commands accept an optional --project-name (defaults to "default").

Commands:
    create-task --address URL [--name NAME] [--type TYPE] [--node-count N]
                [--interval-seconds SEC] [--finish-time TIMESTAMP]
                [--line-ids ID1,ID2,...] [--http-method METHOD] [--project-name NAME]
    get-result --task-id ID --start-time TS --end-time TS [--page-num N] [--page-size N] [--project-name NAME]
    list-nodes [--is-mainland true|false] [--line-types 1,2] [--project-name NAME]
    list-tasks [--page-size N] [--page-num N] [--name PATTERN] [--address PATTERN] [--project-name NAME]
    stop-task --task-id ID [--project-name NAME]
    restart-task --task-id ID [--project-name NAME]
    delete-task --task-id ID [--project-name NAME]
    get-task --task-id ID [--project-name NAME]
    fuzzy-search-nodes <search_query>
    generate-report --task-id ID --start-time TS --end-time TS [--project-name NAME]
"""

import os
import sys
import json
from datetime import datetime, timezone

import volcenginesdkcore
from volcenginesdkcore.rest import ApiException
from volcenginesdkclouddetect20251031 import (
    CLOUDDETECT20251031Api,
    CreateTaskRequest,
    HttpConfigForCreateTaskInput,
    GetTaskResultRequest,
    ListNodesRequest,
    ListTaskRequest,
    StopTaskRequest,
    RestartTaskRequest,
    DeleteTaskRequest,
    GetTaskRequest,
)
from volcenginesdkclouddetect20251031.models import (
    SelectionConfigForCreateTaskInput,
    GroupConfigForCreateTaskInput,
    GroupListForCreateTaskInput,
)
from volcenginesdkclouddetect20251031 import models as _sdk_models

for _n in dir(_sdk_models):
    _c = getattr(_sdk_models, _n)
    if hasattr(_c, "attribute_map") and isinstance(_c.attribute_map, dict):
        _c.attribute_map = {a: k.replace("Id", "ID") for a, k in _c.attribute_map.items()}

# ============================================================================
# Configuration
# ============================================================================

REGION = "cn-north-1"

# ============================================================================
# SDK Client
# ============================================================================

_api_instance = None


def get_credentials():
    ak = os.environ.get("VOLC_ACCESSKEY", "")
    sk = os.environ.get("VOLC_SECRETKEY", "")
    if not ak or not sk:
        print("Error: VOLC_ACCESSKEY and VOLC_SECRETKEY must be set", file=sys.stderr)
        sys.exit(1)
    return ak, sk


def get_api_client():
    global _api_instance
    if _api_instance is not None:
        return _api_instance

    ak, sk = get_credentials()
    configuration = volcenginesdkcore.Configuration()
    configuration.ak = ak
    configuration.sk = sk
    configuration.region = REGION
    configuration.scheme = "https"

    _api_instance = CLOUDDETECT20251031Api(volcenginesdkcore.ApiClient(configuration))
    return _api_instance


def reset_api_client():
    global _api_instance
    _api_instance = None


# ============================================================================
# Helper: Convert SDK model to dict
# ============================================================================

def model_to_dict(obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [model_to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {k: model_to_dict(v) for k, v in obj.items()}
    if hasattr(obj, "attribute_map"):
        result = {}
        for attr in obj.attribute_map.keys():
            val = getattr(obj, attr, None)
            if val is not None:
                result[attr] = model_to_dict(val)
        return result
    if isinstance(obj, (int, float, bool, str)):
        return obj
    return str(obj)


# ============================================================================
# API Functions
# ============================================================================

def create_task(name, address, task_type=1, node_count=5, interval_seconds=60,
                finish_time=0, line_id_list=None, http_method=1, timeout=30,
                project_name="default", selection_config=None):
    api = get_api_client()

    http_config = None
    if task_type == 1:
        http_config = HttpConfigForCreateTaskInput(
            http_method=http_method,
            timeout=timeout,
        )

    request = CreateTaskRequest(
        name=name,
        address=address,
        type=task_type,
        node_count=node_count,
        interval_seconds=interval_seconds,
        finish_time=finish_time,
        line_id_list=line_id_list or [],
        http_config=http_config,
        project_name=project_name,
        selection_config=selection_config,
    )

    try:
        resp = api.create_task(request)
        return resp.task_id
    except ApiException as e:
        print(f"API Error: {e}", file=sys.stderr)
        return None


def build_selection_config_by_group(groups, group_names, node_count=1):
    group_list = [
        GroupListForCreateTaskInput(name=name, node_count=node_count)
        for name in group_names
    ]
    group_config = GroupConfigForCreateTaskInput(
        groups=groups,
        group_list=group_list,
    )
    return SelectionConfigForCreateTaskInput(
        mode=3,
        group_config=group_config,
    )


def get_task_result(task_id, start_time, end_time, page_num=1, page_size=100, project_name=None):
    api = get_api_client()

    request = GetTaskResultRequest(
        task_id=int(task_id),
        start_time=int(start_time),
        end_time=int(end_time),
        page_num=int(page_num),
        page_size=int(min(page_size, 500)),
        project_name=project_name,
    )

    try:
        resp = api.get_task_result(request)
        result = {}
        if resp.data is not None:
            result["Data"] = [model_to_dict(d) for d in resp.data]
        if resp.pagination is not None:
            result["Pagination"] = model_to_dict(resp.pagination)
        return result
    except ApiException as e:
        print(f"API Error: {e}", file=sys.stderr)
        return None


def list_nodes(is_mainland=None, line_types=None, project_name=None):
    api = get_api_client()

    request = ListNodesRequest(
        is_mainland=is_mainland,
        line_type=line_types,
        project_name=project_name,
    )

    try:
        resp = api.list_nodes(request)
        if resp.line_list is not None:
            return [model_to_dict(item) for item in resp.line_list]
        return []
    except ApiException as e:
        print(f"API Error: {e}", file=sys.stderr)
        return []


def list_tasks(page_size=20, page_num=1, name=None, address=None, owner=None, task_id=None, project_name=None):
    api = get_api_client()

    request = ListTaskRequest(
        page_size=int(page_size),
        page_num=int(page_num),
        name=name,
        address=address,
        owner=owner,
        id=task_id,
        project_name=project_name,
    )

    try:
        resp = api.list_task(request)
        result = {}
        if resp.task_list is not None:
            result["TaskList"] = [model_to_dict(t) for t in resp.task_list]
        if resp.pagination is not None:
            result["Pagination"] = model_to_dict(resp.pagination)
        if resp.total is not None:
            result["Total"] = resp.total
        if resp.page_num is not None:
            result["PageNum"] = resp.page_num
        if resp.page_size is not None:
            result["PageSize"] = resp.page_size
        return result
    except ApiException as e:
        print(f"API Error: {e}", file=sys.stderr)
        return None


def stop_task(task_id, project_name=None):
    api = get_api_client()

    request = StopTaskRequest(
        id=int(task_id),
        project_name=project_name,
    )

    try:
        api.stop_task(request)
        return True
    except ApiException as e:
        print(f"API Error: {e}", file=sys.stderr)
        return False


def restart_task(task_id, project_name=None):
    api = get_api_client()

    request = RestartTaskRequest(
        id=int(task_id),
        project_name=project_name,
    )

    try:
        api.restart_task(request)
        return True
    except ApiException as e:
        print(f"API Error: {e}", file=sys.stderr)
        return False


def delete_task(task_id, project_name=None):
    api = get_api_client()

    request = DeleteTaskRequest(
        id=int(task_id),
        project_name=project_name,
    )

    try:
        api.delete_task(request)
        return True
    except ApiException as e:
        print(f"API Error: {e}", file=sys.stderr)
        return False


def get_task(task_id, project_name=None):
    api = get_api_client()

    request = GetTaskRequest(
        id=int(task_id),
        project_name=project_name,
    )

    try:
        resp = api.get_task(request)
        if resp.task is not None:
            return model_to_dict(resp.task)
        return None
    except ApiException as e:
        print(f"API Error: {e}", file=sys.stderr)
        return None


# ============================================================================
# Utility Functions
# ============================================================================

def fuzzy_search_nodes(search_query, is_mainland=None, line_types=None):
    all_nodes = list_nodes(is_mainland, line_types)
    if not all_nodes:
        return []

    query_parts = search_query.lower().split()
    matched = []

    for node in all_nodes:
        name = node.get("name", "").lower()
        if all(part in name for part in query_parts):
            matched.append(node)

    return matched


def generate_task_report(task_id, start_time, end_time, project_name=None):
    result = get_task_result(task_id, start_time, end_time, page_num=1, page_size=500, project_name=project_name)
    if not result or "Data" not in result:
        return None

    data = result["Data"]
    if not data:
        return {"message": "No data available for the specified time range"}

    total = len(data)
    success_count = sum(1 for d in data if _is_success(d))
    failed_count = total - success_count
    success_rate = (success_count / total * 100) if total > 0 else 0

    http_details = [d.get("http_detail") for d in data if d.get("http_detail")]

    report = {
        "task_id": task_id,
        "total_samples": total,
        "success_count": success_count,
        "failed_count": failed_count,
        "success_rate": round(success_rate, 2),
        "time_range": {
            "start": datetime.fromtimestamp(int(start_time), tz=timezone.utc).isoformat(),
            "end": datetime.fromtimestamp(int(end_time), tz=timezone.utc).isoformat(),
        },
    }

    if http_details:
        valid_details = [h for h in http_details if h]
        if valid_details:
            status_codes = {}
            for h in valid_details:
                code = h.get("http_code", "Unknown")
                status_codes[str(code)] = status_codes.get(str(code), 0) + 1
            report["status_code_distribution"] = status_codes

            latencies = []
            for h in valid_details:
                total_time = h.get("total_cost")
                if total_time and total_time > 0:
                    latencies.append(total_time)

            if latencies:
                latencies.sort()
                report["latency_ms"] = {
                    "avg": round(sum(latencies) / len(latencies), 2),
                    "min": round(latencies[0], 2),
                    "max": round(latencies[-1], 2),
                    "p50": round(latencies[int(len(latencies) * 0.5)], 2),
                    "p90": round(latencies[int(len(latencies) * 0.9)], 2),
                    "p99": round(latencies[int(len(latencies) * 0.99)], 2) if len(latencies) >= 100 else round(latencies[-1], 2),
                }

            errors = {}
            for d in data:
                basic = d.get("basic_detail")
                if basic:
                    err = basic.get("error_msg")
                    if err:
                        errors[err] = errors.get(err, 0) + 1
            if errors:
                report["error_distribution"] = errors

    node_stats = {}
    for d in data:
        basic = d.get("basic_detail") or {}
        client = basic.get("client_info") or {}
        node_key = f"{client.get('region', 'Unknown')}-{client.get('isp', 'Unknown')}"
        if node_key not in node_stats:
            node_stats[node_key] = {"total": 0, "success": 0, "failures": 0}
        node_stats[node_key]["total"] += 1
        if _is_success(d):
            node_stats[node_key]["success"] += 1
        else:
            node_stats[node_key]["failures"] += 1

    failing_nodes = {k: v for k, v in node_stats.items() if v["failures"] > 0}
    if failing_nodes:
        report["failing_nodes"] = dict(sorted(
            failing_nodes.items(),
            key=lambda x: x[1]["failures"],
            reverse=True
        )[:10])

    return report


def _is_success(data_item):
    basic = data_item.get("basic_detail")
    if basic:
        usability = basic.get("usability_info")
        if usability:
            # The Cloud Detect API returns usability_info.status as either boolean or string.
            # Live results commonly use "success"/"fail". Keep backwards compatibility.
            status = usability.get("status", False)
            return status is True or status == "success"
        error_msg = basic.get("error_msg")
        if error_msg:
            return False
    http_detail = data_item.get("http_detail")
    if http_detail:
        code = http_detail.get("http_code", 0)
        return isinstance(code, int) and 200 <= code < 400
    return True


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    def get_arg(flag, default=None):
        try:
            idx = args.index(flag)
            return args[idx + 1]
        except (ValueError, IndexError):
            return default

    def has_flag(flag):
        return flag in args

    if cmd == "create-task":
        address = get_arg("--address")
        if not address:
            print("Error: --address is required", file=sys.stderr)
            sys.exit(1)
        name = get_arg("--name", f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_detect")
        task_type = int(get_arg("--type", "1"))
        node_count = int(get_arg("--node-count", "5"))
        interval = int(get_arg("--interval-seconds", "60"))
        finish = int(get_arg("--finish-time", "0"))
        line_ids_str = get_arg("--line-ids", "")
        line_ids = [int(x.strip()) for x in line_ids_str.split(",") if x.strip()] if line_ids_str else []
        http_method = int(get_arg("--http-method", "1"))
        project_name = get_arg("--project-name", "default")

        task_id = create_task(name, address, task_type, node_count, interval, finish, line_ids,
                              http_method, project_name=project_name)
        if task_id:
            print(json.dumps({"task_id": task_id, "name": name}, ensure_ascii=False, indent=2))
        else:
            sys.exit(1)

    elif cmd == "get-result":
        task_id = get_arg("--task-id")
        start = get_arg("--start-time")
        end = get_arg("--end-time")
        if not all([task_id, start, end]):
            print("Error: --task-id, --start-time, --end-time are required", file=sys.stderr)
            sys.exit(1)
        page_num = int(get_arg("--page-num", "1"))
        page_size = int(get_arg("--page-size", "100"))
        project_name = get_arg("--project-name")
        result = get_task_result(task_id, start, end, page_num, page_size, project_name=project_name)
        print(json.dumps(result, ensure_ascii=False, indent=2) if result else "{}")

    elif cmd == "list-nodes":
        is_mainland = get_arg("--is-mainland")
        if is_mainland:
            is_mainland = is_mainland.lower() == "true"
        line_types_str = get_arg("--line-types", "")
        line_types = [int(x) for x in line_types_str.split(",") if x] if line_types_str else None
        project_name = get_arg("--project-name")
        nodes = list_nodes(is_mainland, line_types, project_name=project_name)
        print(json.dumps(nodes, ensure_ascii=False, indent=2))

    elif cmd == "fuzzy-search-nodes":
        if len(args) < 1:
            print("Error: search query required", file=sys.stderr)
            sys.exit(1)
        query = args[0]
        is_mainland = get_arg("--is-mainland")
        if is_mainland:
            is_mainland = is_mainland.lower() == "true"
        line_types_str = get_arg("--line-types", "")
        line_types = [int(x) for x in line_types_str.split(",") if x] if line_types_str else None
        nodes = fuzzy_search_nodes(query, is_mainland, line_types)
        print(json.dumps(nodes, ensure_ascii=False, indent=2))

    elif cmd == "list-tasks":
        page_size = int(get_arg("--page-size", "20"))
        page_num = int(get_arg("--page-num", "1"))
        name = get_arg("--name")
        address = get_arg("--address")
        owner = get_arg("--owner")
        task_id = get_arg("--task-id")
        project_name = get_arg("--project-name")
        result = list_tasks(page_size, page_num, name, address, owner, task_id, project_name=project_name)
        print(json.dumps(result, ensure_ascii=False, indent=2) if result else "{}")

    elif cmd == "stop-task":
        task_id = get_arg("--task-id")
        if not task_id:
            print("Error: --task-id is required", file=sys.stderr)
            sys.exit(1)
        if stop_task(task_id, project_name=get_arg("--project-name")):
            print(json.dumps({"success": True}))
        else:
            sys.exit(1)

    elif cmd == "restart-task":
        task_id = get_arg("--task-id")
        if not task_id:
            print("Error: --task-id is required", file=sys.stderr)
            sys.exit(1)
        if restart_task(task_id, project_name=get_arg("--project-name")):
            print(json.dumps({"success": True}))
        else:
            sys.exit(1)

    elif cmd == "delete-task":
        task_id = get_arg("--task-id")
        if not task_id:
            print("Error: --task-id is required", file=sys.stderr)
            sys.exit(1)
        if delete_task(task_id, project_name=get_arg("--project-name")):
            print(json.dumps({"success": True}))
        else:
            sys.exit(1)

    elif cmd == "get-task":
        task_id = get_arg("--task-id")
        if not task_id:
            print("Error: --task-id is required", file=sys.stderr)
            sys.exit(1)
        task = get_task(task_id, project_name=get_arg("--project-name"))
        print(json.dumps(task, ensure_ascii=False, indent=2) if task else "{}")

    elif cmd == "generate-report":
        task_id = get_arg("--task-id")
        start = get_arg("--start-time")
        end = get_arg("--end-time")
        if not all([task_id, start, end]):
            print("Error: --task-id, --start-time, --end-time are required", file=sys.stderr)
            sys.exit(1)
        report = generate_task_report(task_id, start, end, project_name=get_arg("--project-name"))
        print(json.dumps(report, ensure_ascii=False, indent=2) if report else "{}")

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
