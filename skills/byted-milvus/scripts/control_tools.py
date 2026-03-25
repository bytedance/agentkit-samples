# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import argparse
import json
import os
import sys
import hashlib

from api import ApiError


def print_result(data):
    """Print a successful JSON result."""
    print(json.dumps({"status": "success", "data": data}))


def print_error(msg, details=None):
    """Print a JSON error and exit."""
    err = {"error": msg}
    if details:
        err["details"] = details
    print(json.dumps(err))
    sys.exit(1)


# EIP Billing Types mapping (human strings to API integers)
EIP_BILLING_TYPES = {
    "PrePaid": 1,
    "PostPaid": 2,          # Postpaid by Bandwidth
    "PostPaidByTraffic": 3, # Postpaid by Traffic (Recommended)
}


def _resolve_billing_type(billing_type_str):
    if not billing_type_str:
        return None
    return EIP_BILLING_TYPES.get(billing_type_str)


def api_call(fn):
    """Execute an API call with standard error handling."""
    try:
        result = fn()
        print_result(result)
    except ApiError as e:
        msg = str(e)
        instr = ""
        if "TaskIsRunning" in msg:
            instr = "An operation is already in progress for this instance. Please wait a few minutes and try again, or check status with 'detail'."
        elif any(k in msg for k in ["BadRequestParameterEmpty", "InvalidParameter", "NotFound", "Unauthorized", "InvalidAction"]):
            instr = "Verify that all IDs (VPC, Subnet, Instance) are correct and that you have appropriate permissions. Run 'specs' and 'vpc/subnet' to verify valid options."
        details = f"{msg}\n\nInstruction: {instr}" if instr else msg
        print_error("API Error", details)
    except Exception as e:
        print_error("Unexpected Error", f"{str(e)}\n\nInstruction: Internal script error. Please check your network and credentials.")

def api_call_raw(fn):
    """Execute an API call with standard error handling and return the parsed result (no printing)."""
    try:
        return fn()
    except ApiError as e:
        msg = str(e)
        instr = ""
        if "TaskIsRunning" in msg:
            instr = "An operation is already in progress for this instance. Please wait a few minutes and try again, or check status with 'detail'."
        elif any(k in msg for k in ["BadRequestParameterEmpty", "InvalidParameter", "NotFound", "Unauthorized", "InvalidAction"]):
            instr = "Verify that all IDs (VPC, Subnet, Instance) are correct and that you have appropriate permissions. Run 'specs' and 'vpc/subnet' to verify valid options."
        details = f"{msg}\n\nInstruction: {instr}" if instr else msg
        print_error("API Error", details)
    except Exception as e:
        print_error("Unexpected Error", f"{str(e)}\n\nInstruction: Internal script error. Please check your network and credentials.")


def get_clients():
    """Initialize and return (milvus_api, vpc_api, region) using the active shim layer."""
    import ark_shim
    if ark_shim.check_is_ark_env():
        return ark_shim.get_clients()
    import sdk_shim
    return sdk_shim.get_clients()


MS_ENDPOINT_TYPES = {
    "MILVUS_PRIVATE",
    "MILVUS_PUBLIC",
    "MILVUS_INNER",
    "MILVUS_SERVERLESS_PRIVATE",
    "MILVUS_SERVERLESS_PUBLIC",
}

ENDPOINT_TYPES = {
    "MILVUS_PRIVATE",
    "MILVUS_PUBLIC",
    "MILVUS_INNER",
}


def validate_ms_endpoint_type(endpoint_type: str):
    if endpoint_type not in MS_ENDPOINT_TYPES:
        print_error(
            "Invalid Parameters",
            "Invalid --endpoint-type. Allowed values:\n"
            + "\n".join(sorted(MS_ENDPOINT_TYPES)),
        )

def validate_endpoint_type(endpoint_type: str):
    if endpoint_type not in ENDPOINT_TYPES:
        print_error(
            "Invalid Parameters",
            "Invalid --endpoint-type. Allowed values:\n"
            + "\n".join(sorted(ENDPOINT_TYPES)),
        )

def parse_allow_groups_json(raw: str):
    try:
        data = json.loads(raw)
    except Exception as e:
        print_error("Invalid Parameters", f"--allow-groups-json is not valid JSON: {e}")
        return None

    if not isinstance(data, list):
        print_error("Invalid Parameters", "--allow-groups-json must be a JSON array of objects")
        return None

    groups = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            print_error("Invalid Parameters", f"--allow-groups-json element {idx} must be an object (dict).")
            return None
        group_name = item.get("group_name") or item.get("GroupName")
        ip_list = item.get("list") or item.get("List")

        if not group_name or not isinstance(group_name, str):
            print_error("Invalid Parameters", f"--allow-groups-json element {idx} missing valid group_name (string).")
            return None
        if not isinstance(ip_list, list) or any(not isinstance(x, str) for x in ip_list):
            print_error("Invalid Parameters", f"--allow-groups-json element {idx} missing valid list (array of strings).")
            return None

        groups.append({
            "GroupName": group_name,
            "List": ip_list,
        })
    return groups


def add_eip_alloc_args(p: argparse.ArgumentParser):
    p.add_argument("--eip-bandwidth", type=int, default=None, help="EIP bandwidth (required for auto-allocation)")
    p.add_argument(
        "--eip-billing-type", 
        type=str, 
        default=None, 
        choices=list(EIP_BILLING_TYPES.keys()),
        help=f"EIP billing type (Allowed: {', '.join(EIP_BILLING_TYPES.keys())})"
    )
    p.add_argument("--eip-isp", type=str, default="", help="Optional EIP ISP")
    p.add_argument("--eip-name", type=str, default="", help="Optional EIP name")
    p.add_argument("--eip-description", type=str, default="", help="Optional EIP description")
    p.add_argument("--eip-project-name", type=str, default="", help="Optional EIP project name")
    p.add_argument("--eip-client-token", type=str, default="", help="Optional EIP client token (idempotency)")
    p.add_argument("--eip-auto-reuse", type=str_to_bool, default=False, help="If true, reuse an existing Available EIP before allocating a new one")


def _any_eip_alloc_flags(args) -> bool:
    return any([
        args.eip_bandwidth is not None,
        args.eip_billing_type is not None,
        bool(getattr(args, "eip_isp", "")),
        bool(getattr(args, "eip_name", "")),
        bool(getattr(args, "eip_description", "")),
        bool(getattr(args, "eip_project_name", "")),
        bool(getattr(args, "eip_client_token", "")),
    ])


def _default_eip_client_token(instance_id: str, endpoint_type: str) -> str:
    h = hashlib.sha256(f"milvus:{instance_id}:{endpoint_type}:allocate-eip".encode("utf-8")).hexdigest()
    return h[:32]


def allocate_eip(vpc_api, args) -> dict:
    if args.eip_bandwidth is None or args.eip_billing_type is None:
        print_error("Missing Parameters", "Auto EIP allocation requires both --eip-bandwidth and --eip-billing-type")
    
    billing_type = _resolve_billing_type(args.eip_billing_type)
    if not billing_type:
         print_error("Invalid Parameter", f"Invalid eip-billing-type. Allowed: {', '.join(EIP_BILLING_TYPES.keys())}")

    req = {
        "Bandwidth": args.eip_bandwidth,
        "BillingType": billing_type,
    }
    if args.eip_isp: req["ISP"] = args.eip_isp
    if args.eip_name: req["Name"] = args.eip_name
    if args.eip_description: req["Description"] = args.eip_description
    if args.eip_project_name: req["ProjectName"] = args.eip_project_name
    if args.eip_client_token: req["ClientToken"] = args.eip_client_token

    resp = api_call_raw(lambda: vpc_api.allocate_eip_address(req))
    return resp if isinstance(resp, dict) else {"raw": resp}


def _find_available_eip(vpc_api) -> str | None:
    """Search for an existing EIP with Status=Available and return its AllocationId."""
    try:
        resp = api_call_raw(lambda: vpc_api.describe_eip_addresses({"Status": "Available"}))
        eips = resp.get("Result", resp).get("EipAddresses", []) if isinstance(resp, dict) else []
        for eip in eips:
            alloc_id = eip.get("AllocationId", "")
            if alloc_id and eip.get("Status") == "Available":
                return alloc_id
    except Exception:
        pass  # Fall through to allocation
    return None


def ensure_eip_id_for_enable(args, vpc_api) -> tuple[str | None, dict | None]:
    if not args.enable:
        if getattr(args, "eip_id", ""):
            print_error("Invalid Parameters", "--eip-id can only be used when --enable true.")
        if _any_eip_alloc_flags(args):
            print_error("Invalid Parameters", "EIP allocation flags can only be used when --enable true.")
        return None, None

    if getattr(args, "eip_id", ""):
        if _any_eip_alloc_flags(args):
            print_error("Invalid Parameters", "Provide either --eip-id or EIP allocation flags, not both.")
        return args.eip_id, None

    # Try to reuse an existing Available EIP if the flag is set
    if getattr(args, 'eip_auto_reuse', False):
        reused_id = _find_available_eip(vpc_api)
        if reused_id:
            return reused_id, {"reused": True, "AllocationId": reused_id}

    if not args.eip_client_token:
        args.eip_client_token = _default_eip_client_token(args.id, args.endpoint_type)
    alloc = allocate_eip(vpc_api, args)
    eip_id = alloc.get("AllocationId") or alloc.get("allocation_id")
    if not eip_id:
        print_error("API Error", f"AllocateEipAddress returned no AllocationId: {alloc!r}")
    return eip_id, alloc


# --- Command handlers ---

def cmd_list(args, milvus_api, vpc_api, region):
    body = {
        "PageNumber": args.page_number,
        "PageSize": args.page_size
    }
    api_call(lambda: milvus_api.describe_instances(body))


def _get_list(obj, *keys):
    """Extract a list from a dict, also searching inside 'Result'."""
    for key in keys:
        value = obj.get(key)
        if isinstance(value, list):
            return value
    result = obj.get("Result") or obj.get("result")
    if isinstance(result, dict):
        for key in keys:
            value = result.get(key)
            if isinstance(value, list):
                return value
    return []


def _resolve_spec_name(milvus_api, node_type, cpu, mem, cu_type):
    """Find the best ResourceSpecName for a node type from V2 specs."""
    specs_resp = api_call_raw(lambda: milvus_api.describe_available_spec_v2({}))
    if not specs_resp:
        return None
    spec_list = _get_list(specs_resp, "SpecList")
    node_support = _get_list(specs_resp, "NodeSupportSpecList")

    allowed = set()
    for ns in node_support:
        if ns.get("NodeType") == node_type:
            allowed = set(ns.get("SpecName", []))
            break

    cu_label = (cu_type or "performance").lower()

    # Exact match: cpu, mem, and cu_label
    for s in spec_list:
        sn = s.get("SpecName", "")
        if sn in allowed and s.get("Cpu") == cpu and s.get("Memory") == mem and cu_label in sn:
            return sn
    # Relaxed: cpu, mem, any cu_label
    for s in spec_list:
        sn = s.get("SpecName", "")
        if sn in allowed and s.get("Cpu") == cpu and s.get("Memory") == mem:
            return sn
    # Smallest allowed spec with matching cu_label
    smallest, smallest_cpu = None, float("inf")
    for s in spec_list:
        sn = s.get("SpecName", "")
        if sn in allowed and cu_label in sn and s.get("Cpu", 999) < smallest_cpu:
            smallest_cpu = s.get("Cpu", 999)
            smallest = sn
    return smallest


def _resolve_spec_names_for_create(milvus_api, cpu, mem, cu_type):
    """Resolve ResourceSpecName for all node types used in create."""
    specs_resp = api_call_raw(lambda: milvus_api.describe_available_spec_v2({}))
    if not specs_resp:
        print_error("API Error", "Failed to fetch V2 specs for spec name resolution.")
        return {}

    spec_list = _get_list(specs_resp, "SpecList")
    node_support = _get_list(specs_resp, "NodeSupportSpecList")

    node_allowed = {}
    for ns in node_support:
        nt = ns.get("NodeType", "")
        node_allowed[nt] = set(ns.get("SpecName", []))

    cu_label = (cu_type or "performance").lower()
    result = {}
    for node_type in ["PROXY_NODE", "META_NODE", "DATA_NODE", "QUERY_NODE", "INDEX_NODE"]:
        allowed = node_allowed.get(node_type, set())
        found = None
        # Exact match
        for s in spec_list:
            sn = s.get("SpecName", "")
            if sn in allowed and s.get("Cpu") == cpu and s.get("Memory") == mem and cu_label in sn:
                found = sn
                break
        if not found:
            for s in spec_list:
                sn = s.get("SpecName", "")
                if sn in allowed and s.get("Cpu") == cpu and s.get("Memory") == mem:
                    found = sn
                    break
        if not found:
            smallest, smallest_cpu = None, float("inf")
            for s in spec_list:
                sn = s.get("SpecName", "")
                if sn in allowed and cu_label in sn and s.get("Cpu", 999) < smallest_cpu:
                    smallest_cpu = s.get("Cpu", 999)
                    smallest = sn
            found = smallest
        if not found:
            print_error("No Matching Spec", f"Cannot resolve ResourceSpecName for {node_type} with cpu={cpu}, mem={mem}.")
        result[node_type] = found
    return result


def cmd_create(args, milvus_api, vpc_api, region):
    subnet_resp = vpc_api.describe_subnets({"SubnetIds": [args.subnet_id]})
    subnets = subnet_resp.get("Subnets") or subnet_resp.get("subnets")
    if not subnets:
        print_error("Subnet Not Found", f"Subnet ID '{args.subnet_id}' does not exist.")
        return
    zone_id = subnets[0].get("ZoneId") or subnets[0].get("zone_id")

    has_ha = args.ha
    node_num = 2 if has_ha else 1
    cu_type = args.cu_type.upper() if args.cu_type else None

    spec_names = _resolve_spec_names_for_create(milvus_api, args.cpu, args.mem, cu_type)

    def create_spec(node_type):
        spec = {
            "NodeType": node_type,
            "NodeNum": float(node_num),
            "CpuNum": float(args.cpu),
            "MemSize": float(args.mem),
            "ResourceSpecName": spec_names[node_type],
        }
        if cu_type:
            spec["NodeCuType"] = cu_type
        return spec

    body = {
        "Region": region,
        "ProjectName": "default",
        "Zones": [zone_id],
        "InstanceConfiguration": {
            "InstanceName": args.name,
            "InstanceVersion": args.version,
            "AdminPassword": args.password,
            "HaEnabled": has_ha,
            "ComponentSpecList": [
                create_spec("PROXY_NODE"), create_spec("META_NODE"), create_spec("DATA_NODE"),
                create_spec("QUERY_NODE"), create_spec("INDEX_NODE")
            ]
        },
        "NetworkConfig": {
            "VpcInfo": {"VpcId": args.vpc_id},
            "SubnetInfo": {"SubnetId": args.subnet_id}
        },
        "ChargeConfig": {"ChargeType": "POST"}
    }
    api_call(lambda: milvus_api.create_instance_one_step(body))


def cmd_scale(args, milvus_api, vpc_api, region):
    if args.cpu is None or args.mem is None:
        print_error("Missing Parameters", "Both --cpu and --mem must be provided.")
        return

    cu_type = args.cu_type.upper() if args.cu_type else None
    spec_name = _resolve_spec_name(milvus_api, args.type, args.cpu, args.mem, cu_type)
    if not spec_name:
        print_error("No Matching Spec", f"Cannot resolve ResourceSpecName for {args.type} with cpu={args.cpu}, mem={args.mem}.")

    spec = {
        "NodeType": args.type,
        "NodeNum": float(args.count),
        "CpuNum": float(args.cpu),
        "MemSize": float(args.mem),
        "ResourceSpecName": spec_name,
    }
    if cu_type:
        spec["NodeCuType"] = cu_type

    body = {
        "InstanceId": args.id,
        "HaEnabled": args.ha,
        "OneStep": True,
        "ComponentSpecList": [spec]
    }
    api_call(lambda: milvus_api.scale_instance(body))


def cmd_delete(args, milvus_api, vpc_api, region):
    if not args.confirm or args.confirm != args.id:
        print_error("Confirmation required", f"--confirm must exactly match the instance id {args.id!r}.")
    body = {"InstanceId": args.id}
    api_call(lambda: milvus_api.release_instance(body))


def cmd_detail(args, milvus_api, vpc_api, region):
    body = {"InstanceId": args.id}
    api_call(lambda: milvus_api.describe_instance_detail(body))


def cmd_vpc(args, milvus_api, vpc_api, region):
    api_call(lambda: vpc_api.describe_vpcs({}))


def cmd_subnet(args, milvus_api, vpc_api, region):
    body = {"VpcId": args.vpc_id}
    api_call(lambda: vpc_api.describe_subnets(body))


def cmd_versions(args, milvus_api, vpc_api, region):
    api_call(lambda: milvus_api.describe_available_version({}))


def cmd_specs(args, milvus_api, vpc_api, region):
    api_call(lambda: milvus_api.describe_available_spec_v2({}))


def cmd_ms_list(args, milvus_api, vpc_api, region):
    body = {
        "PageNumber": args.page_number,
        "PageSize": args.page_size
    }
    if args.instance_id: body["InstanceId"] = args.instance_id
    if args.instance_name: body["InstanceName"] = args.instance_name
    if args.project_name: body["ProjectName"] = args.project_name
    api_call(lambda: milvus_api.m_s_describe_instances(body))


def cmd_ms_detail(args, milvus_api, vpc_api, region):
    body = {"InstanceId": args.id}
    if args.project_name: body["ProjectName"] = args.project_name
    api_call(lambda: milvus_api.m_s_describe_instance(body))


def cmd_ms_create_one_step(args, milvus_api, vpc_api, region):
    allowed_versions = {"V2_5", "V2_6"}
    if args.version not in allowed_versions:
        print_error("Invalid Parameters", f"Invalid --version {args.version!r}.")

    body = {
        "InstanceName": args.name,
        "InstanceVersion": args.version,
        "Password": args.password,
        "ProjectName": args.project_name,
        "DeleteProtectEnabled": args.delete_protect,
        "NetworkConfig": {
            "VpcInfo": {"VpcId": args.vpc_id},
            "SubnetInfo": {"SubnetId": args.subnet_id}
        }
    }
    api_call(lambda: milvus_api.m_s_create_instance_one_step(body))


def cmd_ms_release(args, milvus_api, vpc_api, region):
    if not args.confirm or args.confirm != args.id:
        print_error("Confirmation required", f"--confirm must exactly match the instance id {args.id!r}.")
    body = {"InstanceId": args.id}
    api_call(lambda: milvus_api.m_s_release_instance(body))


def cmd_ms_modify_public_domain(args, milvus_api, vpc_api, region):
    validate_ms_endpoint_type(args.endpoint_type)
    eip_id, allocated = ensure_eip_id_for_enable(args, vpc_api)
    body = {
        "InstanceId": args.id,
        "Enable": args.enable,
        "EndpointType": args.endpoint_type
    }
    if eip_id:
        body["EipId"] = eip_id
    
    resp = api_call_raw(lambda: milvus_api.m_s_modify_public_domain(body))
    out = {"response": resp}
    if allocated: out["allocated_eip"] = allocated
    print_result(out)


def cmd_ms_modify_endpoint_allow_group(args, milvus_api, vpc_api, region):
    validate_ms_endpoint_type(args.endpoint_type)
    allow_groups = parse_allow_groups_json(args.allow_groups_json)
    body = {
        "InstanceId": args.id,
        "EndpointType": args.endpoint_type,
        "AllowGroups": allow_groups
    }
    api_call(lambda: milvus_api.m_s_modify_endpoint_allow_group(body))


def cmd_modify_public_domain(args, milvus_api, vpc_api, region):
    validate_endpoint_type(args.endpoint_type)
    eip_id, allocated = ensure_eip_id_for_enable(args, vpc_api)
    body = {
        "InstanceId": args.id,
        "Enable": args.enable,
        "EndpointType": args.endpoint_type,
    }
    if eip_id: body["EipId"] = eip_id

    resp = api_call_raw(lambda: milvus_api.modify_public_domain(body))
    out = {"response": resp}
    if allocated: out["allocated_eip"] = allocated
    print_result(out)


def cmd_modify_endpoint_allow_group(args, milvus_api, vpc_api, region):
    validate_endpoint_type(args.endpoint_type)
    allow_groups = parse_allow_groups_json(args.allow_groups_json)
    body = {
        "InstanceId": args.id,
        "EndpointType": args.endpoint_type,
        "AllowGroups": allow_groups
    }
    api_call(lambda: milvus_api.modify_endpoint_allow_group(body))


def cmd_eip_list(args, milvus_api, vpc_api, region):
    body = {
        "PageNumber": args.page_number,
        "PageSize": args.page_size
    }
    if args.allocation_id: body["AllocationIds"] = args.allocation_id
    if args.eip: body["EipAddresses"] = args.eip
    if args.status: body["Status"] = args.status
    if args.project_name: body["ProjectName"] = args.project_name
    api_call(lambda: vpc_api.describe_eip_addresses(body))


def cmd_eip_detail(args, milvus_api, vpc_api, region):
    body = {"AllocationId": args.allocation_id}
    api_call(lambda: vpc_api.describe_eip_address_attributes(body))


def cmd_eip_allocate(args, milvus_api, vpc_api, region):
    if args.eip_bandwidth is None or args.eip_billing_type is None:
        print_error("Missing Parameters", "--eip-bandwidth and --eip-billing-type are required.")
    if not args.eip_client_token:
        args.eip_client_token = _default_eip_client_token("manual", "EIP")
    alloc = allocate_eip(vpc_api, args)
    print_result(alloc)


def cmd_eip_release(args, milvus_api, vpc_api, region):
    if not args.confirm or args.confirm != args.allocation_id:
        print_error("Confirmation required", f"--confirm must exactly match {args.allocation_id!r}.")
    body = {"AllocationId": args.allocation_id}
    api_call(lambda: vpc_api.release_eip_address(body))


# --- Argument parser ---

def str_to_bool(v):
    if v.lower() in ("true", "1", "yes"): return True
    elif v.lower() in ("false", "0", "no"): return False
    raise argparse.ArgumentTypeError(f"Boolean value expected, got '{v}'")


def build_parser():
    parser = argparse.ArgumentParser(description="Volcano Engine Milvus control plane CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p = subparsers.add_parser("list", help="List all Milvus instances")
    p.add_argument("--page-number", type=int, default=1)
    p.add_argument("--page-size", type=int, default=10)
    p.set_defaults(func=cmd_list)

    # create
    p = subparsers.add_parser("create", help="Create a new Milvus instance")
    p.add_argument("--name", required=True, help="Instance name")
    p.add_argument("--vpc-id", required=True, help="VPC ID")
    p.add_argument("--subnet-id", required=True, help="Subnet ID")
    p.add_argument("--cpu", type=int, required=True, help="CPU cores per node")
    p.add_argument("--mem", type=int, required=True, help="Memory size in GiB per node")
    p.add_argument("--cu-type", type=str, help="CU type (e.g., PERFORMANCE, CAPACITY)")
    p.add_argument("--version", default="V2_5", help="Milvus version")
    p.add_argument("--password", required=True, help="Admin password")
    p.add_argument("--ha", type=str_to_bool, default=True, help="High availability (default: true)")
    p.set_defaults(func=cmd_create)

    # scale
    p = subparsers.add_parser("scale", help="Scale an instance component")
    p.add_argument("--id", required=True, help="Instance ID")
    p.add_argument("--type", required=True, help="Node type (QUERY_NODE, DATA_NODE, etc.)")
    p.add_argument("--cpu", type=int, required=True, help="CPU cores per node")
    p.add_argument("--mem", type=int, required=True, help="Memory size in GiB per node")
    p.add_argument("--cu-type", type=str, help="CU type")
    p.add_argument("--count", type=int, required=True, help="Node count")
    p.add_argument("--ha", type=str_to_bool, default=True, help="High availability (default: true)")
    p.set_defaults(func=cmd_scale)

    # delete
    p = subparsers.add_parser("delete", help="Delete a Milvus instance")
    p.add_argument("--id", required=True, help="Instance ID")
    p.add_argument("--confirm", default="", help="Must exactly match the instance id")
    p.set_defaults(func=cmd_delete)

    # detail
    p = subparsers.add_parser("detail", help="Get instance details")
    p.add_argument("--id", required=True, help="Instance ID")
    p.set_defaults(func=cmd_detail)

    # vpc
    p = subparsers.add_parser("vpc", help="List available VPCs")
    p.set_defaults(func=cmd_vpc)

    # subnet
    p = subparsers.add_parser("subnet", help="List subnets for a VPC")
    p.add_argument("--vpc-id", required=True, help="VPC ID")
    p.set_defaults(func=cmd_subnet)

    # versions
    p = subparsers.add_parser("versions", help="List available Milvus versions")
    p.set_defaults(func=cmd_versions)

    # specs
    p = subparsers.add_parser("specs", help="List available node specifications")
    p.set_defaults(func=cmd_specs)

    # --- Serverless ---

    p = subparsers.add_parser("ms-list", help="List Milvus Serverless instances")
    p.add_argument("--page-number", type=int, default=1)
    p.add_argument("--page-size", type=int, default=10)
    p.add_argument("--instance-id", default="", help="Filter by instance id")
    p.add_argument("--instance-name", default="", help="Filter by instance name")
    p.add_argument("--project-name", default="", help="Filter by project name")
    p.set_defaults(func=cmd_ms_list)

    p = subparsers.add_parser("ms-detail", help="Get Milvus Serverless instance details")
    p.add_argument("--id", required=True, help="Instance ID")
    p.add_argument("--project-name", default="", help="Optional project name")
    p.set_defaults(func=cmd_ms_detail)

    p = subparsers.add_parser("ms-create-one-step", help="Create Milvus Serverless instance")
    p.add_argument("--name", required=True, help="Instance name")
    p.add_argument("--vpc-id", required=True, help="VPC ID")
    p.add_argument("--subnet-id", required=True, help="Subnet ID")
    p.add_argument("--version", default="V2_5", help="Milvus version")
    p.add_argument("--password", required=True, help="Admin password")
    p.add_argument("--project-name", default="default", help="Project name")
    p.add_argument("--delete-protect", type=str_to_bool, default=False, help="Delete protection")
    p.set_defaults(func=cmd_ms_create_one_step)

    p = subparsers.add_parser("ms-release", help="Release Serverless instance")
    p.add_argument("--id", required=True, help="Instance ID")
    p.add_argument("--confirm", default="", help="Must match instance id")
    p.set_defaults(func=cmd_ms_release)

    p = subparsers.add_parser("ms-modify-public-domain", help="Enable/disable public domain")
    p.add_argument("--id", required=True, help="Instance ID")
    p.add_argument("--enable", type=str_to_bool, required=True, help="true/false")
    p.add_argument("--endpoint-type", required=True, help="Endpoint type")
    p.add_argument("--eip-id", default="", help="EIP id")
    add_eip_alloc_args(p)
    p.set_defaults(func=cmd_ms_modify_public_domain)

    p = subparsers.add_parser("ms-modify-endpoint-allow-group", help="Update endpoint allow groups")
    p.add_argument("--id", required=True, help="Instance ID")
    p.add_argument("--endpoint-type", required=True, help="Endpoint type")
    p.add_argument("--allow-groups-json", required=True, help="JSON array of allow-groups")
    p.set_defaults(func=cmd_ms_modify_endpoint_allow_group)

    p = subparsers.add_parser("modify-public-domain", help="Enable/disable public domain")
    p.add_argument("--id", required=True, help="Instance ID")
    p.add_argument("--enable", type=str_to_bool, required=True, help="true/false")
    p.add_argument("--endpoint-type", required=True, help="Endpoint type")
    p.add_argument("--eip-id", default="", help="EIP id")
    add_eip_alloc_args(p)
    p.set_defaults(func=cmd_modify_public_domain)

    p = subparsers.add_parser("modify-endpoint-allow-group", help="Update endpoint allow groups")
    p.add_argument("--id", required=True, help="Instance ID")
    p.add_argument("--endpoint-type", required=True, help="Endpoint type")
    p.add_argument("--allow-groups-json", required=True, help="JSON array of allow-groups")
    p.set_defaults(func=cmd_modify_endpoint_allow_group)

    p = subparsers.add_parser("eip-list", help="List EIPs")
    p.add_argument("--page-number", type=int, default=1)
    p.add_argument("--page-size", type=int, default=10)
    p.add_argument("--allocation-id", action="append", default=[], help="Filter by id")
    p.add_argument("--eip", action="append", default=[], help="Filter by IP")
    p.add_argument("--status", default="", help="Filter by status")
    p.add_argument("--project-name", default="", help="Filter by project name")
    p.set_defaults(func=cmd_eip_list)

    p = subparsers.add_parser("eip-detail", help="Get EIP attributes")
    p.add_argument("--allocation-id", required=True, help="EIP allocation id")
    p.set_defaults(func=cmd_eip_detail)

    p = subparsers.add_parser("eip-allocate", help="Allocate an EIP")
    add_eip_alloc_args(p)
    p.set_defaults(func=cmd_eip_allocate)

    p = subparsers.add_parser("eip-release", help="Release an EIP")
    p.add_argument("--allocation-id", required=True, help="EIP allocation id")
    p.add_argument("--confirm", default="", help="Must match allocation id")
    p.set_defaults(func=cmd_eip_release)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    milvus_api, vpc_api, region = get_clients()
    args.func(args, milvus_api, vpc_api, region)


if __name__ == '__main__':
    main()
