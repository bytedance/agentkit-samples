# Copyright (c) 2026 ByteDance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT
import argparse
import json
import os
import sys

from volcenginesdkcore.rest import ApiException
import volcenginesdkcore
import volcenginesdkmilvus
from volcenginesdkmilvus.api.milvus_api import MILVUSApi
import volcenginesdkvpc
from volcenginesdkvpc.api.vpc_api import VPCApi


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


def api_call(fn):
    """Execute an API call with standard error handling."""
    try:
        response = fn()
        try:
            result = response.to_dict()
        except AttributeError:
            result = str(response)
        print_result(result)
    except ApiException as e:
        msg = str(e)
        instr = ""
        # Provide actionable instructions for the agent based on common substrings
        if "TaskIsRunning" in msg:
            instr = "An operation is already in progress for this instance. Please wait a few minutes and try again, or check status with 'detail'."
        elif any(k in msg for k in ["BadRequestParameterEmpty", "InvalidParameter", "NotFound", "Unauthorized"]):
            instr = "Verify that all IDs (VPC, Subnet, Instance) are correct and that you have appropriate permissions. Run 'specs' and 'vpc/subnet' to verify valid options."

        details = f"{msg}\n\nInstruction: {instr}" if instr else msg
        print_error("API Error", details)
    except Exception as e:
        print_error("Unexpected Error", f"{str(e)}\n\nInstruction: Internal script error. Please check your network and credentials.")


def get_clients():
    """Initialize and return (milvus_api, vpc_api, region) from env vars."""
    ak = os.environ.get("VOLCENGINE_AK")
    sk = os.environ.get("VOLCENGINE_SK")
    region = os.environ.get("VOLCENGINE_REGION", "cn-beijing")

    if not ak or not sk:
        print_error("Missing Credentials", "VOLCENGINE_AK or VOLCENGINE_SK environment variables are not set. Please ask the user to provide their Volcano Engine Access Key and Secret Key.")

    configuration = volcenginesdkcore.Configuration()
    configuration.ak = ak
    configuration.sk = sk
    configuration.region = region
    configuration.client_side_validation = False

    client = volcenginesdkcore.ApiClient(configuration)
    milvus_api = MILVUSApi(client)
    vpc_api = VPCApi(client)
    return milvus_api, vpc_api, region


# --- Command handlers ---

def cmd_list(args, milvus_api, vpc_api, region):
    body = volcenginesdkmilvus.models.DescribeInstancesRequest()
    body.page_number = args.page_number
    body.page_size = args.page_size
    api_call(lambda: milvus_api.describe_instances(body))


def cmd_create(args, milvus_api, vpc_api, region):
    # Look up zone from subnet
    subnet_resp = vpc_api.describe_subnets(
        volcenginesdkvpc.models.DescribeSubnetsRequest(subnet_ids=[args.subnet_id])
    )
    if not subnet_resp.subnets:
        print_error("Subnet Not Found", f"Subnet ID '{args.subnet_id}' does not exist or is not in the current region. Instruction: Run 'vpc' and 'subnet --vpc-id <ID>' to list valid network resources.")
        return
    zone_id = subnet_resp.subnets[0].zone_id

    has_ha = args.ha
    node_num = 2 if has_ha else 1
    cu_type = args.cu_type.upper() if args.cu_type else None

    def create_spec(node_type):
        spec_kwargs = {
            "node_type": node_type,
            "node_num": float(node_num),
            "cpu_num": float(args.cpu),
            "mem_size": float(args.mem)
        }
        if cu_type:
            spec_kwargs["node_cu_type"] = cu_type
        return volcenginesdkmilvus.models.ComponentSpecListForCreateInstanceOneStepInput(**spec_kwargs)

    body = volcenginesdkmilvus.models.CreateInstanceOneStepRequest(
        region=region,
        project_name="default",
        zones=[zone_id],
        instance_configuration=volcenginesdkmilvus.models.InstanceConfigurationForCreateInstanceOneStepInput(
            instance_name=args.name,
            instance_version=args.version,
            admin_password=args.password,
            ha_enabled=has_ha,
            component_spec_list=[
                create_spec("PROXY_NODE"), create_spec("META_NODE"), create_spec("DATA_NODE"),
                create_spec("QUERY_NODE"), create_spec("INDEX_NODE")
            ]
        ),
        network_config=volcenginesdkmilvus.models.NetworkConfigForCreateInstanceOneStepInput(
            vpc_info=volcenginesdkmilvus.models.VpcInfoForCreateInstanceOneStepInput(vpc_id=args.vpc_id),
            subnet_info=volcenginesdkmilvus.models.SubnetInfoForCreateInstanceOneStepInput(subnet_id=args.subnet_id)
        ),
        charge_config=volcenginesdkmilvus.models.ChargeConfigForCreateInstanceOneStepInput(charge_type="POST")
    )
    api_call(lambda: milvus_api.create_instance_one_step(body))


def cmd_scale(args, milvus_api, vpc_api, region):
    # Validation
    if args.cpu is None or args.mem is None:
        print_error("Missing Parameters", "Both --cpu and --mem must be provided. Run 'specs' to see valid CPU/Memory combinations.")
        return

    cu_type = args.cu_type.upper() if args.cu_type else None

    spec_kwargs = {
        "node_type": args.type,
        "node_num": args.count,
        "cpu_num": args.cpu,
        "mem_size": args.mem
    }
    if cu_type:
        spec_kwargs["node_cu_type"] = cu_type

    body = volcenginesdkmilvus.models.ScaleInstanceRequest(
        instance_id=args.id,
        ha_enabled=args.ha,
        one_step=True,
        component_spec_list=[
            volcenginesdkmilvus.models.ComponentSpecListForScaleInstanceInput(**spec_kwargs)
        ]
    )
    api_call(lambda: milvus_api.scale_instance(body))


def cmd_delete(args, milvus_api, vpc_api, region):
    if not args.confirm:
        print_error(
            "Confirmation required",
            "Refusing to delete instance without explicit confirmation.\n"
            f"Target instance id: {args.id!r}\n"
            "Instruction: Run 'detail' first and show the instance details to the user, then ask them to confirm.\n"
            f"1) control.py detail --id {args.id}\n"
            f"2) control.py delete --id {args.id} --confirm {args.id}",
        )
    if args.confirm != args.id:
        print_error(
            "Confirmation mismatch",
            f"--confirm must exactly match the instance id. Expected {args.id!r}, got {args.confirm!r}.",
        )
    body = volcenginesdkmilvus.models.ReleaseInstanceRequest(instance_id=args.id)
    api_call(lambda: milvus_api.release_instance(body))


def cmd_detail(args, milvus_api, vpc_api, region):
    body = volcenginesdkmilvus.models.DescribeInstanceDetailRequest(instance_id=args.id)
    api_call(lambda: milvus_api.describe_instance_detail(body))


def cmd_vpc(args, milvus_api, vpc_api, region):
    body = volcenginesdkvpc.models.DescribeVpcsRequest()
    api_call(lambda: vpc_api.describe_vpcs(body))


def cmd_subnet(args, milvus_api, vpc_api, region):
    body = volcenginesdkvpc.models.DescribeSubnetsRequest(vpc_id=args.vpc_id)
    api_call(lambda: vpc_api.describe_subnets(body))


def cmd_versions(args, milvus_api, vpc_api, region):
    body = volcenginesdkmilvus.models.DescribeAvailableVersionRequest()
    api_call(lambda: milvus_api.describe_available_version(body))


def cmd_specs(args, milvus_api, vpc_api, region):
    body = volcenginesdkmilvus.models.DescribeAvailableSpecRequest()
    api_call(lambda: milvus_api.describe_available_spec(body))


# --- Argument parser ---

def str_to_bool(v):
    """Convert string to bool for --ha flag."""
    if v.lower() in ("true", "1", "yes"):
        return True
    elif v.lower() in ("false", "0", "no"):
        return False
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
    p.add_argument("--version", default="V2_5", help="Milvus version (default: V2_5). Use 'versions' to list available values.")
    p.add_argument("--password", required=True, help="Admin password")
    p.add_argument("--ha", type=str_to_bool, default=True, help="High availability (default: true)")
    p.set_defaults(func=cmd_create)

    # scale
    p = subparsers.add_parser("scale", help="Scale an instance component")
    p.add_argument("--id", required=True, help="Instance ID")
    p.add_argument("--type", required=True, help="Node type (QUERY_NODE, DATA_NODE, etc.)")
    p.add_argument("--cpu", type=int, required=True, help="CPU cores per node")
    p.add_argument("--mem", type=int, required=True, help="Memory size in GiB per node")
    p.add_argument("--cu-type", type=str, help="CU type (e.g., PERFORMANCE, CAPACITY)")
    p.add_argument("--count", type=int, required=True, help="Node count")
    p.add_argument("--ha", type=str_to_bool, default=True, help="High availability (default: true)")
    p.set_defaults(func=cmd_scale)

    # delete
    p = subparsers.add_parser("delete", help="Delete a Milvus instance")
    p.add_argument("--id", required=True, help="Instance ID")
    p.add_argument(
        "--confirm",
        default="",
        help="Required: must exactly match the instance id to proceed (safety confirmation)",
    )
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

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    milvus_api, vpc_api, region = get_clients()
    args.func(args, milvus_api, vpc_api, region)


if __name__ == '__main__':
    main()
