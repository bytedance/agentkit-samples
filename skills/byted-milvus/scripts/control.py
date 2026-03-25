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
import hashlib
import json
import sys
import time
from typing import Any, Callable

from api import ApiError


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

MS_ALLOWED_VERSIONS = {"V2_5", "V2_6"}


# EIP Billing Types mapping (human strings to API integers)
EIP_BILLING_TYPES = {
    "PrePaid": 1,
    "PostPaid": 2,          # Postpaid by Bandwidth
    "PostPaidByTraffic": 3, # Postpaid by Traffic (Recommended)
}

class WorkflowError(Exception):
    def __init__(
        self,
        error: str,
        details: str = "",
        data: dict[str, Any] | None = None,
        steps_completed: list[str] | None = None,
    ):
        super().__init__(details or error)
        self.error = error
        self.details = details
        self.data = data or {}
        self.steps_completed = list(steps_completed or [])


def emit(payload: dict[str, Any], exit_code: int = 0) -> None:
    print(json.dumps(payload, default=str))
    sys.exit(exit_code)


def first_present(obj: Any, keys: list[str]) -> Any:
    if isinstance(obj, dict):
        for key in keys:
            if key in obj and obj[key] not in (None, ""):
                return obj[key]
        for value in obj.values():
            found = first_present(value, keys)
            if found not in (None, ""):
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = first_present(item, keys)
            if found not in (None, ""):
                return found
    return None


def get_list(obj: dict[str, Any], *keys: str) -> list[Any]:
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


def get_dict(obj: dict[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, dict):
            return value
    result = obj.get("Result") or obj.get("result")
    if isinstance(result, dict):
        for key in keys:
            value = result.get(key)
            if isinstance(value, dict):
                return value
    return {}


def normalize_detail(detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": first_present(detail, ["InstanceId", "instance_id", "Id", "id"]),
        "name": first_present(detail, ["InstanceName", "instance_name", "Name", "name"]),
        "status": first_present(detail, ["Status", "status", "State", "state"]),
        "endpoint_list": first_present(detail, ["EndpointList", "endpoint_list"]) or [],
        "spec_config": first_present(detail, ["SpecConfig", "spec_config"]) or {},
        "raw": detail,
    }


def str_to_bool(v: str) -> bool:
    if isinstance(v, bool):
        return v
    if v.lower() in ("true", "1", "yes"):
        return True
    if v.lower() in ("false", "0", "no"):
        return False
    raise argparse.ArgumentTypeError(f"Boolean value expected, got '{v}'")


def add_eip_alloc_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--eip-id", default="", help="Existing EIP allocation id")
    parser.add_argument("--eip-bandwidth", type=int, default=None, help="EIP bandwidth for auto-allocation")
    parser.add_argument(
        "--eip-billing-type", 
        type=str, 
        default=None, 
        choices=list(EIP_BILLING_TYPES.keys()),
        help=f"EIP billing type for auto-allocation (Allowed: {', '.join(EIP_BILLING_TYPES.keys())})"
    )
    parser.add_argument("--eip-isp", type=str, default="", help="Optional EIP ISP")
    parser.add_argument("--eip-name", type=str, default="", help="Optional EIP name")
    parser.add_argument("--eip-description", type=str, default="", help="Optional EIP description")
    parser.add_argument("--eip-project-name", type=str, default="", help="Optional EIP project name")
    parser.add_argument("--eip-client-token", type=str, default="", help="Optional EIP client token")
    parser.add_argument("--eip-auto-reuse", type=str_to_bool, default=False, help="If true, reuse an existing Available EIP before allocating a new one")


def validate_endpoint_type(endpoint_type: str, allowed: set[str]) -> None:
    if endpoint_type not in allowed:
        raise WorkflowError(
            "Invalid Parameters",
            "Invalid --endpoint-type. Allowed values:\n" + "\n".join(sorted(allowed)),
        )


def default_allow_groups_json() -> str:
    return '[{"group_name":"default","list":["0.0.0.0/0"]}]'


def parse_allow_groups_json(raw: str) -> list[dict[str, Any]]:
    try:
        allow_groups = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WorkflowError("Invalid Parameters", f"--allow-groups-json is not valid JSON: {exc}")
    if not isinstance(allow_groups, list):
        raise WorkflowError("Invalid Parameters", "--allow-groups-json must be a JSON array of objects")
    for idx, item in enumerate(allow_groups):
        if not isinstance(item, dict):
            raise WorkflowError("Invalid Parameters", f"--allow-groups-json element {idx} must be an object (dict).")
        group_name = item.get("group_name")
        cidr_list = item.get("list")
        if not isinstance(group_name, str) or not group_name:
            raise WorkflowError("Invalid Parameters", f"--allow-groups-json element {idx} missing valid group_name (string).")
        if not isinstance(cidr_list, list) or not all(isinstance(x, str) for x in cidr_list):
            raise WorkflowError("Invalid Parameters", f"--allow-groups-json element {idx} missing valid list (array of strings).")
    return allow_groups


def _any_eip_alloc_flags(args: argparse.Namespace) -> bool:
    return any(
        [
            args.eip_bandwidth is not None,
            args.eip_billing_type is not None,
            bool(getattr(args, "eip_isp", "")),
            bool(getattr(args, "eip_name", "")),
            bool(getattr(args, "eip_description", "")),
            bool(getattr(args, "eip_project_name", "")),
            bool(getattr(args, "eip_client_token", "")),
        ]
    )


def _default_eip_client_token(instance_id: str, endpoint_type: str) -> str:
    digest = hashlib.sha256(
        f"milvus:{instance_id}:{endpoint_type}:allocate-eip".encode("utf-8")
    ).hexdigest()
    return digest[:32]

def _get_clients():
    import ark_shim
    if ark_shim.check_is_ark_env():
        return ark_shim.get_clients()
    import sdk_shim
    return sdk_shim.get_clients()

class ControlPlane:
    def __init__(self):
        self.milvus, self.vpc, self.region = _get_clients()

    def _run_api(self, fn: Callable[[], Any], context_data: dict[str, Any] | None = None) -> Any:
        try:
            return fn()
        except WorkflowError:
            raise
        except ApiError as exc:
            msg = str(exc)
            instruction = ""
            if "TaskIsRunning" in msg:
                instruction = (
                    "An operation is already in progress for this instance. "
                    "Wait for the instance to return to Running and retry."
                )
            elif any(
                key in msg
                for key in [
                    "BadRequestParameterEmpty",
                    "InvalidParameter",
                    "NotFound",
                    "Unauthorized",
                    "InvalidAction",
                ]
            ):
                instruction = (
                    "Verify that all IDs and parameters are valid and that the current credentials "
                    "have access to the target VPC, subnet, and instance."
                )
            details = f"{msg}\n\nInstruction: {instruction}" if instruction else msg
            raise WorkflowError("API Error", details, context_data)
        except Exception as exc:
            raise WorkflowError(
                "Unexpected Error",
                f"{exc}\n\nInstruction: Internal script error. Check credentials, network, and parameters.",
                context_data,
            )

    def _success(self, goal: str, data: dict[str, Any], steps_completed: list[str]) -> dict[str, Any]:
        return {
            "status": "success",
            "goal": goal,
            "data": data,
            "steps_completed": steps_completed,
        }

    def _error(
        self,
        goal: str,
        error: str,
        details: str,
        steps_completed: list[str],
        data: dict[str, Any] | None = None,
        status: str = "error",
    ) -> dict[str, Any]:
        payload = {
            "status": status,
            "goal": goal,
            "error": error,
            "details": details,
            "data": data or {},
            "steps_completed": steps_completed,
        }
        return payload

    def _fetch_detail(self, instance_id: str) -> dict[str, Any]:
        body = {"InstanceId": instance_id}
        return self._run_api(lambda: self.milvus.describe_instance_detail(body), {"instance_id": instance_id})

    def _fetch_ms_detail(self, instance_id: str, project_name: str = "") -> dict[str, Any]:
        body = {"InstanceId": instance_id}
        if project_name:
            body["ProjectName"] = project_name
        context = {"instance_id": instance_id}
        if project_name:
            context["project_name"] = project_name
        return self._run_api(lambda: self.milvus.m_s_describe_instance(body), context)

    def _fetch_subnets_for_vpc(self, vpc_id: str) -> dict[str, Any]:
        return self._run_api(lambda: self.vpc.describe_subnets({"VpcId": vpc_id}), {"vpc_id": vpc_id})

    def _find_subnet(self, subnet_response: dict[str, Any], subnet_id: str) -> dict[str, Any] | None:
        for subnet in get_list(subnet_response, "Subnets", "subnets"):
            current = subnet.get("SubnetId") or subnet.get("subnet_id")
            if current == subnet_id:
                return subnet
        return None

    def _wait_for_condition(
        self,
        fetch_fn: Callable[[], dict[str, Any]],
        condition_fn: Callable[[dict[str, Any]], bool],
        poll_interval: int,
        timeout: int,
        consecutive_successes: int = 1,
    ) -> tuple[bool, dict[str, Any]]:
        deadline = time.time() + timeout
        last_detail: dict[str, Any] = {}
        success_count = 0
        while True:
            last_detail = fetch_fn()
            if condition_fn(last_detail):
                success_count += 1
                if success_count >= consecutive_successes:
                    return True, last_detail
            else:
                success_count = 0
            
            if time.time() >= deadline:
                return False, last_detail
            time.sleep(poll_interval)

    def _extract_instance_id(self, response: dict[str, Any], fallback_detail: dict[str, Any] | None = None) -> str | None:
        instance_id = first_present(response, ["InstanceId", "instance_id", "Id", "id"])
        if instance_id:
            return instance_id
        if fallback_detail:
            return normalize_detail(fallback_detail)["id"]
        return None

    def _find_available_eip(self) -> str | None:
        """Search for an existing EIP with Status=Available and return its AllocationId."""
        try:
            resp = self._run_api(lambda: self.vpc.describe_eip_addresses({"Status": "Available"}))
            eips = resp.get("Result", resp).get("EipAddresses", []) if isinstance(resp, dict) else []
            for eip in eips:
                alloc_id = eip.get("AllocationId", "")
                if alloc_id and eip.get("Status") == "Available":
                    return alloc_id
        except Exception:
            pass  # Fall through to allocation
        return None

    def _validate_enable_public_args(self, instance_id: str, endpoint_type: str, enable: bool, args: argparse.Namespace) -> tuple[str | None, dict[str, Any] | None]:
        if not enable:
            if args.eip_id:
                raise WorkflowError("Invalid Parameters", "--eip-id can only be used when --enable true.")
            if _any_eip_alloc_flags(args):
                raise WorkflowError("Invalid Parameters", "EIP allocation flags can only be used when --enable true.")
            return None, None

        if args.eip_id:
            if _any_eip_alloc_flags(args):
                raise WorkflowError("Invalid Parameters", "Provide either --eip-id or EIP allocation flags, not both.")
            return args.eip_id, None

        # Optimization: Check if an EIP is already bound for this endpoint type
        try:
            is_ms = endpoint_type.startswith("MILVUS_SERVERLESS_")
            if is_ms:
                detail_resp = self.milvus.m_s_describe_instance({"InstanceId": instance_id})
            else:
                detail_resp = self.milvus.describe_instance_detail({"InstanceId": instance_id})
            
            detail = normalize_detail(detail_resp)
            for ep in detail.get("endpoint_list", []):
                if ep["Type"] == endpoint_type and ep.get("EipId"):
                    return ep["EipId"], {"reused": True, "AllocationId": ep["EipId"], "AlreadyBound": True}
        except Exception:
            pass  # Fallback to allocation flow if detail fetch fails

        # Try to reuse an existing Available EIP if the flag is set
        if getattr(args, 'eip_auto_reuse', False):
            reused_id = self._find_available_eip()
            if reused_id:
                return reused_id, {"reused": True, "AllocationId": reused_id}

        billing_type = EIP_BILLING_TYPES.get(args.eip_billing_type)
        if billing_type is None:
            raise WorkflowError("Invalid Parameter", f"Invalid --eip-billing-type. Allowed: {', '.join(EIP_BILLING_TYPES.keys())}")

        token = args.eip_client_token or _default_eip_client_token(instance_id, endpoint_type)
        req = {
            "Bandwidth": args.eip_bandwidth,
            "BillingType": billing_type,
            "ClientToken": token,
        }
        if args.eip_isp:
            req["ISP"] = args.eip_isp
        if args.eip_name:
            req["Name"] = args.eip_name
        if args.eip_description:
            req["Description"] = args.eip_description
        if args.eip_project_name:
            req["ProjectName"] = args.eip_project_name

        allocated = self._run_api(
            lambda: self.vpc.allocate_eip_address(req),
            {"instance_id": instance_id, "endpoint_type": endpoint_type},
        )
        eip_id = allocated.get("AllocationId") or allocated.get("allocation_id")
        if not eip_id:
            raise WorkflowError("API Error", f"AllocateEipAddress returned no AllocationId: {allocated!r}")
        return eip_id, allocated

    def provision_info(self) -> dict[str, Any]:
        steps: list[str] = []
        vpcs_resp = self._run_api(lambda: self.vpc.describe_vpcs({}))
        steps.append("fetch_vpcs")

        specs_resp = self._run_api(lambda: self.milvus.describe_available_spec_v2({}))
        steps.append("fetch_specs")

        versions_resp = self._run_api(lambda: self.milvus.describe_available_version({}))
        steps.append("fetch_versions")

        subnets_by_vpc: dict[str, Any] = {}
        for vpc in get_list(vpcs_resp, "Vpcs", "vpcs"):
            vpc_id = vpc.get("VpcId") or vpc.get("vpc_id")
            if not vpc_id:
                continue
            subnet_resp = self._fetch_subnets_for_vpc(vpc_id)
            subnets_by_vpc[vpc_id] = subnet_resp
        steps.append("fetch_subnets")

        return self._success(
            "provision-info",
            {
                "region": self.region,
                "vpcs": vpcs_resp,
                "subnets_by_vpc": subnets_by_vpc,
                "specs": specs_resp,
                "versions": versions_resp,
            },
            steps,
        )

    def provision(self, args: argparse.Namespace) -> dict[str, Any]:
        steps: list[str] = []
        subnet_resp = self._fetch_subnets_for_vpc(args.vpc_id)
        steps.append("fetch_subnets")

        subnet = self._find_subnet(subnet_resp, args.subnet_id)
        if not subnet:
            raise WorkflowError(
                "Subnet Not Found",
                f"Subnet ID '{args.subnet_id}' was not found in VPC '{args.vpc_id}'.",
                {"subnets": subnet_resp},
                steps_completed=steps,
            )

        zone_id = subnet.get("ZoneId") or subnet.get("zone_id")
        if not zone_id:
            raise WorkflowError(
                "Invalid Subnet Response",
                f"Subnet '{args.subnet_id}' did not include a zone identifier.",
                {"subnet": subnet},
                steps_completed=steps,
            )
        steps.append("validate_subnet")

    def _resolve_spec_name(self, node_type: str, cpu: int, mem: int, cu_type: str | None, spec_name_override: str = "", steps: list[str] | None = None) -> str:
        if spec_name_override:
            return spec_name_override

        # Fetch V2 specs to resolve per-node-type ResourceSpecName
        specs_resp = self._run_api(lambda: self.milvus.describe_available_spec_v2({}))
        if steps is not None:
            steps.append("fetch_specs")

        spec_list = get_list(specs_resp, "SpecList")
        node_support = get_list(specs_resp, "NodeSupportSpecList")

        # Build a lookup: node_type -> set of allowed spec names
        node_allowed: dict[str, set[str]] = {}
        for ns in node_support:
            nt = ns.get("NodeType", "")
            node_allowed[nt] = set(ns.get("SpecName", []))

        cu_label = (cu_type or "performance").lower()
        allowed = node_allowed.get(node_type, set())

        # Try exact match first: look for a spec whose Cpu/Memory match and cu_label (if provided)
        for s in spec_list:
            sn = s.get("SpecName", "")
            if sn in allowed and s.get("Cpu") == cpu and s.get("Memory") == mem:
                if cu_label in sn:
                    return sn

        # Fallback: try any matching cpu/mem spec in allowed set
        for s in spec_list:
            sn = s.get("SpecName", "")
            if sn in allowed and s.get("Cpu") == cpu and s.get("Memory") == mem:
                return sn

        # Last resort: find the smallest allowed spec for this node type
        smallest = None
        smallest_cpu = float("inf")
        for s in spec_list:
            sn = s.get("SpecName", "")
            if sn in allowed and cu_label in sn:
                if s.get("Cpu", 999) < smallest_cpu:
                    smallest_cpu = s.get("Cpu", 999)
                    smallest = sn
        
        if smallest:
            return smallest

        raise WorkflowError(
            "No Matching Spec",
            f"Cannot find a spec for node type {node_type} with cpu={cpu}, mem={mem}, cu_type={cu_label}.",
            steps_completed=steps,
        )

    def provision(self, args: argparse.Namespace) -> dict[str, Any]:
        steps: list[str] = []
        subnet_resp = self._fetch_subnets_for_vpc(args.vpc_id)
        steps.append("fetch_subnets")

        subnet = self._find_subnet(subnet_resp, args.subnet_id)
        if not subnet:
            raise WorkflowError(
                "Subnet Not Found",
                f"Subnet ID '{args.subnet_id}' was not found in VPC '{args.vpc_id}'.",
                {"subnets": subnet_resp},
                steps_completed=steps,
            )

        zone_id = subnet.get("ZoneId") or subnet.get("zone_id")
        if not zone_id:
            raise WorkflowError(
                "Invalid Subnet Response",
                f"Subnet '{args.subnet_id}' did not include a zone identifier.",
                {"subnet": subnet},
                steps_completed=steps,
            )
        steps.append("validate_subnet")

        node_num = 2 if args.ha else 1
        cu_type = args.cu_type.upper() if args.cu_type else None

        def create_spec(node_type: str) -> dict[str, Any]:
            spec = {
                "NodeType": node_type,
                "NodeNum": float(node_num),
                "CpuNum": float(args.cpu),
                "MemSize": float(args.mem),
                "ResourceSpecName": self._resolve_spec_name(node_type, args.cpu, args.mem, cu_type, args.spec_name, steps),
            }
            if cu_type:
                spec["NodeCuType"] = cu_type
            return spec

        body = {
            "Region": self.region,
            "ProjectName": "default",
            "Zones": [zone_id],
            "InstanceConfiguration": {
                "InstanceName": args.name,
                "InstanceVersion": args.version,
                "AdminPassword": args.password,
                "HaEnabled": args.ha,
                "ComponentSpecList": [
                    create_spec("PROXY_NODE"),
                    create_spec("META_NODE"),
                    create_spec("DATA_NODE"),
                    create_spec("QUERY_NODE"),
                    create_spec("INDEX_NODE"),
                ],
            },
            "NetworkConfig": {
                "VpcInfo": {"VpcId": args.vpc_id},
                "SubnetInfo": {"SubnetId": args.subnet_id},
            },
            "ChargeConfig": {"ChargeType": "POST"},
        }
        create_resp = self._run_api(lambda: self.milvus.create_instance_one_step(body), {"request": body})
        steps.append("create_instance")

        instance_id = self._extract_instance_id(create_resp)
        if not instance_id:
            raise WorkflowError(
                "API Error",
                "CreateInstanceOneStep returned no instance identifier.",
                {"create_response": create_resp},
                steps_completed=steps,
            )

        ok, detail = self._wait_for_condition(
            fetch_fn=lambda: self._fetch_detail(instance_id),
            condition_fn=lambda d: normalize_detail(d)["status"] == "Running",
            poll_interval=args.poll_interval,
            timeout=args.timeout,
            consecutive_successes=2,
        )
        steps.append("poll_status")

        data = {
            "instance_id": instance_id,
            "create_response": create_resp,
            "final_detail": detail,
        }
        if ok:
            return self._success("provision", data, steps)
        return self._error(
            "provision",
            "Timeout",
            f"Instance '{instance_id}' did not reach Running within {args.timeout} seconds.",
            steps,
            data,
            status="timeout",
        )

    def deprovision(self, args: argparse.Namespace) -> dict[str, Any]:
        steps: list[str] = []
        if args.confirm != args.id:
            raise WorkflowError(
                "Confirmation required",
                f"--confirm must exactly match the instance id {args.id!r}.",
                steps_completed=steps,
            )

        detail = self._fetch_detail(args.id)
        steps.append("fetch_detail")

        release_resp = self._run_api(
            lambda: self.milvus.release_instance({"InstanceId": args.id}),
            {"instance_id": args.id, "detail": detail},
        )
        steps.append("release_instance")

        def _fetch_safe():
            try:
                return self._fetch_detail(args.id)
            except WorkflowError as e:
                if "NotFound" in str(e) or "not exist" in str(e).lower():
                    return {"is_deleted": True}
                raise e

        ok, detail_after = self._wait_for_condition(
            fetch_fn=_fetch_safe,
            condition_fn=lambda d: d.get("is_deleted") or normalize_detail(d)["status"] == "Deleted",
            poll_interval=args.poll_interval,
            timeout=args.timeout,
        )
        steps.append("poll_deletion")

        data = {
            "instance_id": args.id,
            "release_response": release_resp,
            "final_detail": detail_after,
        }
        if ok:
            return self._success("deprovision", data, steps)
        return self._error("deprovision", "Timeout", "Instance was not deleted in time.", steps, data)

    def status(self, args: argparse.Namespace) -> dict[str, Any]:
        steps: list[str] = []
        detail = self._fetch_detail(args.id)
        steps.append("fetch_detail")
        normalized = normalize_detail(detail)
        return self._success(
            "status",
            {
                "instance_id": normalized["id"],
                "instance_name": normalized["name"],
                "status": normalized["status"],
                "endpoint_list": normalized["endpoint_list"],
                "spec_config": normalized["spec_config"],
                "detail": detail,
            },
            steps,
        )

    def list_instances(self, args: argparse.Namespace) -> dict[str, Any]:
        steps: list[str] = []
        body: dict[str, Any] = {"PageNumber": args.page_number, "PageSize": args.page_size}
        if args.instance_id:
            body["InstanceId"] = args.instance_id
        if args.instance_name:
            body["InstanceName"] = args.instance_name
        resp = self._run_api(lambda: self.milvus.describe_instances(body), {"request": body})
        steps.append("describe_instances")
        return self._success("list", {"response": resp}, steps)

    def ms_list(self, args: argparse.Namespace) -> dict[str, Any]:
        steps: list[str] = []
        body: dict[str, Any] = {"PageNumber": args.page_number, "PageSize": args.page_size}
        if args.instance_id:
            body["InstanceId"] = args.instance_id
        if args.instance_name:
            body["InstanceName"] = args.instance_name
        if args.project_name:
            body["ProjectName"] = args.project_name
        resp = self._run_api(lambda: self.milvus.m_s_describe_instances(body), {"request": body})
        steps.append("ms_describe_instances")
        return self._success("ms-list", {"response": resp}, steps)

    def ms_detail(self, args: argparse.Namespace) -> dict[str, Any]:
        detail = self._fetch_ms_detail(args.id, args.project_name)
        return self._success("ms-detail", {"detail": normalize_detail(detail)}, ["fetch_detail"])

    def scale(self, args: argparse.Namespace) -> dict[str, Any]:
        steps: list[str] = []
        current_detail = self._fetch_detail(args.id)
        steps.append("fetch_detail")

        current_status = normalize_detail(current_detail)["status"]
        if current_status != "Running":
            raise WorkflowError(
                "Invalid Instance State",
                f"Instance '{args.id}' must be Running before scaling. Current status: {current_status!r}.",
                {"detail": current_detail},
                steps_completed=steps,
            )
        steps.append("validate_running")

        spec = {
            "NodeType": args.type,
            "NodeNum": float(args.count),
            "CpuNum": float(args.cpu),
            "MemSize": float(args.mem),
            "ResourceSpecName": self._resolve_spec_name(args.type, args.cpu, args.mem, args.cu_type, steps=steps),
        }
        if args.cu_type:
            spec["NodeCuType"] = args.cu_type.upper()

        body = {
            "InstanceId": args.id,
            "HaEnabled": args.ha,
            "OneStep": True,
            "ComponentSpecList": [spec],
        }
        scale_resp = self._run_api(lambda: self.milvus.scale_instance(body), {"request": body})
        steps.append("scale_instance")

        ok, detail = self._wait_for_condition(
            fetch_fn=lambda: self._fetch_detail(args.id),
            condition_fn=lambda d: normalize_detail(d)["status"] == "Running",
            poll_interval=args.poll_interval,
            timeout=args.timeout,
            consecutive_successes=2,
        )
        steps.append("poll_status")

        data = {
            "instance_id": args.id,
            "scale_response": scale_resp,
            "final_detail": detail,
        }
        if ok:
            return self._success("scale", data, steps)
        return self._error(
            "scale",
            "Timeout",
            f"Instance '{args.id}' did not return to Running within {args.timeout} seconds.",
            steps,
            data,
            status="timeout",
        )

    def _endpoint_ready(self, detail: dict[str, Any], endpoint_type: str, enable: bool) -> bool:
        endpoint_list = normalize_detail(detail)["endpoint_list"]
        if not isinstance(endpoint_list, list):
            return False
        matching = []
        for item in endpoint_list:
            if not isinstance(item, dict):
                continue
            item_type = item.get("Type") or item.get("type")
            if item_type == endpoint_type:
                matching.append(item)
        if enable:
            return any((item.get("Eip") or item.get("eip")) not in (None, "") for item in matching)
        if not matching:
            return True
        return all((item.get("Eip") or item.get("eip")) in (None, "") for item in matching)

    def enable_public(self, args: argparse.Namespace) -> dict[str, Any]:
        steps: list[str] = []
        validate_endpoint_type(args.endpoint_type, ENDPOINT_TYPES)

        detail_before = self._fetch_detail(args.id)
        steps.append("fetch_detail")

        eip_id, allocated = self._validate_enable_public_args(args.id, args.endpoint_type, args.enable, args)
        if allocated:
            steps.append("allocate_eip")

        body = {
            "InstanceId": args.id,
            "Enable": args.enable,
            "EndpointType": args.endpoint_type,
        }
        if eip_id:
            body["EipId"] = eip_id

        modify_resp = self._run_api(lambda: self.milvus.modify_public_domain(body), {"request": body})
        steps.append("modify_public_domain")

        allow_resp = None
        if args.enable:
            # Wait for status to be Running to stabilize after public domain change
            self._wait_for_condition(
                fetch_fn=lambda: self._fetch_detail(args.id),
                condition_fn=lambda d: normalize_detail(d)["status"] == "Running",
                poll_interval=args.poll_interval,
                timeout=args.timeout,
            )
            allow_groups = parse_allow_groups_json(args.allow_groups_json)
            allow_body = {
                "InstanceId": args.id,
                "EndpointType": args.endpoint_type,
                "AllowGroups": allow_groups,
            }
            allow_resp = self._run_api(lambda: self.milvus.modify_endpoint_allow_group(allow_body), {"request": allow_body})
            steps.append("modify_endpoint_allow_group")

        ok, detail_after = self._wait_for_condition(
            fetch_fn=lambda: self._fetch_detail(args.id),
            condition_fn=lambda d: self._endpoint_ready(d, args.endpoint_type, args.enable),
            poll_interval=args.poll_interval,
            timeout=args.timeout,
            consecutive_successes=2,
        )
        steps.append("poll_endpoint")

        data = {
            "instance_id": args.id,
            "endpoint_type": args.endpoint_type,
            "enable": args.enable,
            "modify_response": modify_resp,
            "allow_group_response": allow_resp,
            "allocated_eip": allocated,
            "detail_before": detail_before,
            "detail_after": detail_after,
        }
        if ok:
            return self._success("enable-public", data, steps)
        return self._error(
            "enable-public",
            "Timeout",
            f"Endpoint '{args.endpoint_type}' for instance '{args.id}' did not reach the expected state within {args.timeout} seconds.",
            steps,
            data,
            status="timeout",
        )

    def ms_enable_public(self, args: argparse.Namespace) -> dict[str, Any]:
        steps: list[str] = []
        validate_endpoint_type(args.endpoint_type, MS_ENDPOINT_TYPES)

        detail_before = self._fetch_ms_detail(args.id, args.project_name)
        steps.append("fetch_detail")

        eip_id, allocated = self._validate_enable_public_args(args.id, args.endpoint_type, args.enable, args)
        if allocated:
            steps.append("allocate_eip")

        body = {
            "InstanceId": args.id,
            "Enable": args.enable,
            "EndpointType": args.endpoint_type,
        }
        if eip_id:
            body["EipId"] = eip_id

        modify_resp = self._run_api(lambda: self.milvus.m_s_modify_public_domain(body), {"request": body})
        steps.append("modify_public_domain")

        allow_resp = None
        if args.enable:
            # Wait for status to be Running to stabilize after public domain change
            self._wait_for_condition(
                fetch_fn=lambda: self._fetch_ms_detail(args.id, args.project_name),
                condition_fn=lambda d: normalize_detail(d)["status"] == "Running",
                poll_interval=args.poll_interval,
                timeout=args.timeout,
            )
            allow_groups = parse_allow_groups_json(args.allow_groups_json)
            allow_body = {
                "InstanceId": args.id,
                "EndpointType": args.endpoint_type,
                "AllowGroups": allow_groups,
            }
            allow_resp = self._run_api(lambda: self.milvus.m_s_modify_endpoint_allow_group(allow_body), {"request": allow_body})
            steps.append("modify_endpoint_allow_group")

        ok, detail_after = self._wait_for_condition(
            fetch_fn=lambda: self._fetch_ms_detail(args.id, args.project_name),
            condition_fn=lambda d: self._endpoint_ready(d, args.endpoint_type, args.enable),
            poll_interval=args.poll_interval,
            timeout=args.timeout,
            consecutive_successes=2,
        )
        steps.append("poll_endpoint")

        data = {
            "instance_id": args.id,
            "endpoint_type": args.endpoint_type,
            "enable": args.enable,
            "modify_response": modify_resp,
            "allow_group_response": allow_resp,
            "allocated_eip": allocated,
            "detail_before": detail_before,
            "detail_after": detail_after,
        }
        if ok:
            return self._success("ms-enable-public", data, steps)
        return self._error(
            "ms-enable-public",
            "Timeout",
            f"Endpoint '{args.endpoint_type}' for instance '{args.id}' did not reach the expected state within {args.timeout} seconds.",
            steps,
            data,
            status="timeout",
        )

    def ms_provision_info(self) -> dict[str, Any]:
        steps: list[str] = []
        vpcs_resp = self._run_api(lambda: self.vpc.describe_vpcs({}))
        steps.append("fetch_vpcs")

        subnets_by_vpc: dict[str, Any] = {}
        for vpc in get_list(vpcs_resp, "Vpcs", "vpcs"):
            vpc_id = vpc.get("VpcId") or vpc.get("vpc_id")
            if not vpc_id:
                continue
            subnet_resp = self._fetch_subnets_for_vpc(vpc_id)
            subnets_by_vpc[vpc_id] = subnet_resp
        steps.append("fetch_subnets")

        versions_resp = self._run_api(lambda: self.milvus.describe_available_version({}))
        steps.append("fetch_versions")

        return self._success(
            "ms-provision-info",
            {
                "region": self.region,
                "vpcs": vpcs_resp,
                "subnets_by_vpc": subnets_by_vpc,
                "versions": versions_resp,
                "supported_versions": sorted(MS_ALLOWED_VERSIONS),
            },
            steps,
        )

    def ms_provision(self, args: argparse.Namespace) -> dict[str, Any]:
        steps: list[str] = []
        if args.version not in MS_ALLOWED_VERSIONS:
            raise WorkflowError(
                "Invalid Parameters",
                f"Invalid --version {args.version!r}. Allowed values: {', '.join(sorted(MS_ALLOWED_VERSIONS))}.",
                steps_completed=steps,
            )

        subnet_resp = self._fetch_subnets_for_vpc(args.vpc_id)
        steps.append("fetch_subnets")
        subnet = self._find_subnet(subnet_resp, args.subnet_id)
        if not subnet:
            raise WorkflowError(
                "Subnet Not Found",
                f"Subnet ID '{args.subnet_id}' was not found in VPC '{args.vpc_id}'.",
                {"subnets": subnet_resp},
                steps_completed=steps,
            )
        steps.append("validate_subnet")

        body = {
            "InstanceName": args.name,
            "InstanceVersion": args.version,
            "Password": args.password,
            "ProjectName": args.project_name,
            "DeleteProtectEnabled": args.delete_protect,
            "NetworkConfig": {
                "VpcInfo": {"VpcId": args.vpc_id},
                "SubnetInfo": {"SubnetId": args.subnet_id},
            },
        }
        create_resp = self._run_api(lambda: self.milvus.m_s_create_instance_one_step(body), {"request": body})
        steps.append("create_instance")

        instance_id = self._extract_instance_id(create_resp)
        if not instance_id:
            raise WorkflowError(
                "API Error",
                "MSCreateInstanceOneStep returned no instance identifier.",
                {"create_response": create_resp},
            )

        ok, detail = self._wait_for_condition(
            fetch_fn=lambda: self._fetch_ms_detail(instance_id, args.project_name),
            condition_fn=lambda d: normalize_detail(d)["status"] == "Running",
            poll_interval=args.poll_interval,
            timeout=args.timeout,
            consecutive_successes=2,
        )
        steps.append("poll_status")

        data = {
            "instance_id": instance_id,
            "project_name": args.project_name,
            "create_response": create_resp,
            "final_detail": detail,
        }
        if ok:
            return self._success("ms-provision", data, steps)
        return self._error(
            "ms-provision",
            "Timeout",
            f"Serverless instance '{instance_id}' did not reach Running within {args.timeout} seconds.",
            steps,
            data,
            status="timeout",
        )

    def ms_deprovision(self, args: argparse.Namespace) -> dict[str, Any]:
        steps: list[str] = []
        if args.confirm != args.id:
            raise WorkflowError(
                "Confirmation required",
                f"--confirm must exactly match the instance id {args.id!r}.",
                steps_completed=steps,
            )

        detail = self._fetch_ms_detail(args.id, args.project_name)
        steps.append("fetch_detail")

        body = {"InstanceId": args.id}
        release_resp = self._run_api(
            lambda: self.milvus.m_s_release_instance(body),
            {"instance_id": args.id, "detail": detail},
        )
        steps.append("release_instance")

        def _fetch_safe():
            try:
                return self._fetch_ms_detail(args.id, args.project_name)
            except WorkflowError as e:
                if "NotFound" in str(e) or "not exist" in str(e).lower():
                    return {"is_deleted": True}
                raise e

        ok, detail_after = self._wait_for_condition(
            fetch_fn=_fetch_safe,
            condition_fn=lambda d: d.get("is_deleted") or normalize_detail(d)["status"] == "Deleted",
            poll_interval=args.poll_interval,
            timeout=args.timeout,
        )
        steps.append("poll_deletion")

        data = {
            "instance_id": args.id,
            "project_name": args.project_name,
            "release_response": release_resp,
            "final_detail": detail_after,
        }
        if ok:
            return self._success("ms-deprovision", data, steps)
        return self._error("ms-deprovision", "Timeout", "Instance was not deleted in time.", steps, data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Volcano Engine Milvus goal-based control plane CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p = subparsers.add_parser("provision-info", help="Fetch VPCs, subnets, specs, and versions for regular Milvus provisioning")
    p.set_defaults(goal="provision-info")

    p = subparsers.add_parser("provision", help="Create a regular Milvus instance and wait until Running")
    p.add_argument("--name", required=True, help="Instance name")
    p.add_argument("--vpc-id", required=True, help="VPC ID")
    p.add_argument("--subnet-id", required=True, help="Subnet ID")
    p.add_argument("--cpu", type=int, required=True, help="CPU cores per node")
    p.add_argument("--mem", type=int, required=True, help="Memory size in GiB per node")
    p.add_argument("--password", required=True, help="Admin password")
    p.add_argument("--version", default="V2_5", help="Milvus version")
    p.add_argument("--spec-name", default="", help="ResourceSpecName from provision-info (e.g. milvus_4x_2c8g_service_performance)")
    p.add_argument("--cu-type", default="", help="Optional CU type")
    p.add_argument("--ha", type=str_to_bool, default=True, help="High availability")
    p.add_argument("--poll-interval", type=int, default=5, help="Polling interval in seconds")
    p.add_argument("--timeout", type=int, default=600, help="Polling timeout in seconds")
    p.set_defaults(goal="provision")

    p = subparsers.add_parser("deprovision", help="Delete a regular Milvus instance")
    p.add_argument("--id", required=True, help="Instance ID")
    p.add_argument("--confirm", required=True, help="Must exactly match the instance ID")
    p.add_argument("--poll-interval", type=int, default=5, help="Polling interval in seconds")
    p.add_argument("--timeout", type=int, default=600, help="Polling timeout in seconds")
    p.set_defaults(goal="deprovision")

    p = subparsers.add_parser("status", help="Fetch status and details for a regular Milvus instance")
    p.add_argument("--id", required=True, help="Instance ID")
    p.set_defaults(goal="status")

    p = subparsers.add_parser("list", help="List regular Milvus instances")
    p.add_argument("--page-number", type=int, default=1, help="Page number")
    p.add_argument("--page-size", type=int, default=10, help="Page size")
    p.add_argument("--instance-id", default="", help="Filter by instance id")
    p.add_argument("--instance-name", default="", help="Filter by instance name")
    p.set_defaults(goal="list")

    p = subparsers.add_parser("scale", help="Scale one component of a regular Milvus instance and wait until Running")
    p.add_argument("--id", required=True, help="Instance ID")
    p.add_argument("--type", required=True, help="Node type")
    p.add_argument("--cpu", type=int, required=True, help="CPU cores per node")
    p.add_argument("--mem", type=int, required=True, help="Memory size in GiB per node")
    p.add_argument("--count", type=int, required=True, help="Node count")
    p.add_argument("--cu-type", default="", help="Optional CU type")
    p.add_argument("--ha", type=str_to_bool, default=True, help="High availability")
    p.add_argument("--poll-interval", type=int, default=5, help="Polling interval in seconds")
    p.add_argument("--timeout", type=int, default=600, help="Polling timeout in seconds")
    p.set_defaults(goal="scale")

    p = subparsers.add_parser("enable-public", help="Enable or disable public access for a regular Milvus endpoint")
    p.add_argument("--id", required=True, help="Instance ID")
    p.add_argument("--enable", type=str_to_bool, required=True, help="true/false")
    p.add_argument("--endpoint-type", default="MILVUS_PUBLIC", help="Endpoint type")
    p.add_argument(
        "--allow-groups-json",
        default=default_allow_groups_json(),
        help="JSON array of allow-groups (default: open to 0.0.0.0/0)",
    )
    add_eip_alloc_args(p)
    p.add_argument("--poll-interval", type=int, default=5, help="Polling interval in seconds")
    p.add_argument("--timeout", type=int, default=600, help="Polling timeout in seconds")
    p.set_defaults(goal="enable-public")

    p = subparsers.add_parser("ms-provision-info", help="Fetch VPCs, subnets, and versions for serverless provisioning")
    p.set_defaults(goal="ms-provision-info")

    p = subparsers.add_parser("ms-list", help="List Milvus Serverless instances")
    p.add_argument("--page-number", type=int, default=1, help="Page number")
    p.add_argument("--page-size", type=int, default=10, help="Page size")
    p.add_argument("--instance-id", default="", help="Filter by instance id")
    p.add_argument("--instance-name", default="", help="Filter by instance name")
    p.add_argument("--project-name", default="", help="Filter by project name")
    p.set_defaults(goal="ms-list")

    p = subparsers.add_parser("ms-detail", help="Get Milvus Serverless instance details")
    p.add_argument("--id", required=True, help="Instance ID")
    p.add_argument("--project-name", default="default", help="Project name")
    p.set_defaults(goal="ms-detail")

    p = subparsers.add_parser("ms-provision", help="Create a serverless Milvus instance and wait until Running")
    p.add_argument("--name", required=True, help="Instance name")
    p.add_argument("--vpc-id", required=True, help="VPC ID")
    p.add_argument("--subnet-id", required=True, help="Subnet ID")
    p.add_argument("--password", required=True, help="Admin password")
    p.add_argument("--version", default="V2_5", help="Milvus version")
    p.add_argument("--project-name", default="default", help="Project name")
    p.add_argument("--delete-protect", type=str_to_bool, default=False, help="Delete protection")
    p.add_argument("--poll-interval", type=int, default=5, help="Polling interval in seconds")
    p.add_argument("--timeout", type=int, default=600, help="Polling timeout in seconds")
    p.set_defaults(goal="ms-provision")

    p = subparsers.add_parser("ms-enable-public", help="Enable or disable public access for a serverless Milvus endpoint")
    p.add_argument("--id", required=True, help="Instance ID")
    p.add_argument("--enable", type=str_to_bool, required=True, help="true/false")
    p.add_argument("--endpoint-type", default="MILVUS_SERVERLESS_PUBLIC", help="Endpoint type")
    p.add_argument("--project-name", default="default", help="Project name")
    p.add_argument(
        "--allow-groups-json",
        default=default_allow_groups_json(),
        help="JSON array of allow-groups (default: open to 0.0.0.0/0)",
    )
    add_eip_alloc_args(p)
    p.add_argument("--poll-interval", type=int, default=5, help="Polling interval in seconds")
    p.add_argument("--timeout", type=int, default=600, help="Polling timeout in seconds")
    p.set_defaults(goal="ms-enable-public")

    p = subparsers.add_parser("ms-deprovision", help="Delete a serverless Milvus instance")
    p.add_argument("--id", required=True, help="Instance ID")
    p.add_argument("--project-name", default="default", help="Project name")
    p.add_argument("--confirm", required=True, help="Must exactly match the instance ID")
    p.add_argument("--poll-interval", type=int, default=5, help="Polling interval in seconds")
    p.add_argument("--timeout", type=int, default=600, help="Polling timeout in seconds")
    p.set_defaults(goal="ms-deprovision")

    return parser


def dispatch(control_plane: ControlPlane, args: argparse.Namespace) -> dict[str, Any]:
    match args.goal:
        case "provision-info":
            return control_plane.provision_info()
        case "provision":
            return control_plane.provision(args)
        case "deprovision":
            return control_plane.deprovision(args)
        case "status":
            return control_plane.status(args)
        case "list":
            return control_plane.list_instances(args)
        case "scale":
            return control_plane.scale(args)
        case "enable-public":
            return control_plane.enable_public(args)
        case "ms-provision-info":
            return control_plane.ms_provision_info()
        case "ms-list":
            return control_plane.ms_list(args)
        case "ms-detail":
            return control_plane.ms_detail(args)
        case "ms-provision":
            return control_plane.ms_provision(args)
        case "ms-enable-public":
            return control_plane.ms_enable_public(args)
        case "ms-deprovision":
            return control_plane.ms_deprovision(args)
    raise WorkflowError("Invalid Command", f"Unsupported goal {args.goal!r}.")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    control_plane = ControlPlane()
    try:
        emit(dispatch(control_plane, args))
    except WorkflowError as exc:
        emit(
            {
                "status": "error",
                "goal": getattr(args, "goal", ""),
                "error": exc.error,
                "details": exc.details or str(exc),
                "data": exc.data,
                "steps_completed": exc.steps_completed,
            },
            exit_code=1,
        )


if __name__ == "__main__":
    main()
