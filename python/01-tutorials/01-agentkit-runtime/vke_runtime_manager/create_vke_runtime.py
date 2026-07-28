#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agentkit_client import call_api, load_config


STATE_SCHEMA_VERSION = 1
READY_STATUS = "Ready"
FAILED_STATUSES = {"Failed", "CreateFailed", "Error"}


def config_text(config, key):
    value = config.get(key)
    if isinstance(value, str):
        return value.strip()
    return value


def validate_runtime_config(config, config_path):
    required = [
        "artifact_url",
        "role_name",
        "DiscoveryUrl",
        "namespace",
        "vke_cluster_id",
    ]
    missing = [key for key in required if not config_text(config, key)]
    if not runtime_name_prefix(config):
        missing.append("name (or runtime_name / runtimename)")
    if missing:
        raise ValueError(
            "Missing required runtime config field(s) in "
            + config_path
            + ": "
            + ", ".join(sorted(missing))
        )


def body_text(body, path):
    value = body
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    if isinstance(value, str):
        return value.strip()
    return value


def validate_create_body(body, source):
    required_paths = [
        ("name",),
        ("artifact_url",),
        ("role_name",),
        ("authorizer_configuration", "CustomJwtAuthorizer", "DiscoveryUrl"),
        ("provider_config", "vke_configuration", "vke_cluster_id"),
        ("provider_config", "vke_configuration", "namespace"),
    ]
    missing = [".".join(path) for path in required_paths if not body_text(body, path)]
    if missing:
        raise ValueError(
            "Missing required CreateRuntime body field(s) in "
            + source
            + ": "
            + ", ".join(sorted(missing))
        )


def int_config(config, key, default_value):
    value = config.get(key)
    if value in ("", None):
        return default_value
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer") from exc


def runtime_name_prefix(config):
    return (
        config_text(config, "name")
        or config_text(config, "runtime_name")
        or config_text(config, "runtimename")
    )


def timestamped_runtime_name(name_prefix):
    prefix = str(name_prefix).strip().rstrip("-")
    return prefix + "-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")


def apply_runtime_name_timestamp(body):
    body = dict(body)
    body["name"] = timestamped_runtime_name(body.get("name"))
    return body


def default_state_path(config_path):
    return config_path + ".vke-runtime-state.json"


def read_json_file(path):
    with open(path, "r") as f:
        return json.load(f)


def read_state(state_path):
    if not os.path.exists(state_path):
        return {}
    return read_json_file(state_path)


def write_state(state_path, state):
    directory = os.path.dirname(os.path.abspath(state_path))
    os.makedirs(directory, exist_ok=True)
    temp_path = state_path + ".tmp"
    with open(temp_path, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    os.replace(temp_path, state_path)


def acquire_create_lock(lock_path):
    directory = os.path.dirname(os.path.abspath(lock_path))
    os.makedirs(directory, exist_ok=True)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError(
            "Create lock exists: "
            + lock_path
            + ". Another create may be running. "
            + "If this is stale, inspect the lock and state file before deleting it."
        )

    payload = {
        "pid": os.getpid(),
        "created_at": datetime.datetime.now().isoformat(),
    }
    with os.fdopen(fd, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def release_create_lock(lock_path):
    try:
        os.remove(lock_path)
    except FileNotFoundError:
        pass


def api_error(result):
    metadata = result.get("ResponseMetadata") or {}
    error = metadata.get("Error")
    if not error:
        return None
    code = error.get("Code")
    message = error.get("Message")
    return f"{code} - {message}"


def extract_runtime_id(result):
    result_body = result.get("Result") or {}
    return (
        result_body.get("RuntimeId")
        or result.get("RuntimeId")
        or result.get("runtime_id")
    )


def extract_runtime_status(result):
    result_body = result.get("Result") or {}
    return result_body.get("Status") or ""


def extract_endpoint(result):
    result_body = result.get("Result") or {}
    endpoint = result_body.get("Endpoint")
    if endpoint:
        return endpoint

    for item in result_body.get("NetworkConfigurations") or []:
        endpoint = item.get("Endpoint")
        if endpoint:
            return endpoint
    return ""


def build_create_body(config):
    min_instance = int_config(config, "min_instance", 1)
    max_instance = int_config(config, "max_instance", 2)

    vke_configuration = {
        "vke_cluster_id": config_text(config, "vke_cluster_id"),
        "namespace": config_text(config, "namespace"),
    }

    vke_configuration["WorkspaceId"] = config_text(config, "WorkspaceId") or "default"

    return {
        "name": runtime_name_prefix(config),
        "artifact_type": "image",
        "artifact_url": config_text(config, "artifact_url"),
        "role_name": config_text(config, "role_name"),
        "provider": "VKE",
        "min_instance": min_instance,
        "max_instance": max_instance,
        "authorizer_configuration": {
            "CustomJwtAuthorizer": {
                "DiscoveryUrl": config_text(config, "DiscoveryUrl"),
            },
        },
        "provider_config": {
            "vke_configuration": vke_configuration,
        },
    }


def ensure_body_dict(body, source):
    if not isinstance(body, dict):
        raise ValueError(f"{source} must be a JSON object")
    return body


def resolve_create_body(config, config_path, body_file):
    if body_file:
        body = ensure_body_dict(read_json_file(body_file), body_file)
        validate_create_body(body, body_file)
        return apply_runtime_name_timestamp(body), "body_file"

    if "body" in config and config["body"] is not None:
        source = config_path + ":body"
        body = ensure_body_dict(config["body"], source)
        validate_create_body(body, source)
        return apply_runtime_name_timestamp(body), "config.body"

    validate_runtime_config(config, config_path)
    body = build_create_body(config)
    validate_create_body(body, config_path)
    return apply_runtime_name_timestamp(body), "config_fields"


def create_runtime(config_path, body, body_source, state_path, verbose):
    state = {
        "schema_version": STATE_SCHEMA_VERSION,
        "name": body.get("name", ""),
        "runtime_id": "",
        "endpoint": "",
        "status": "Creating",
        "body_source": body_source,
        "state_path": state_path,
        "created_at": datetime.datetime.now().isoformat(),
        "updated_at": datetime.datetime.now().isoformat(),
    }
    write_state(state_path, state)

    result = call_api(
        "CreateRuntime",
        body,
        method="POST",
        verbose=verbose,
        config_path=config_path,
    )
    error = api_error(result)
    if error:
        state["status"] = "CreateFailed"
        state["updated_at"] = datetime.datetime.now().isoformat()
        state["last_error"] = error
        write_state(state_path, state)
        raise RuntimeError("CreateRuntime failed: " + error)

    runtime_id = extract_runtime_id(result)
    if not runtime_id:
        state["status"] = "CreateFailed"
        state["updated_at"] = datetime.datetime.now().isoformat()
        state["last_response"] = result
        write_state(state_path, state)
        raise RuntimeError("CreateRuntime response does not contain Result.RuntimeId")

    state["runtime_id"] = runtime_id
    state["status"] = "Created"
    state["updated_at"] = datetime.datetime.now().isoformat()
    state["last_create_response_metadata"] = result.get("ResponseMetadata") or {}
    write_state(state_path, state)
    return runtime_id, state


def get_runtime(config_path, runtime_id, verbose):
    result = call_api(
        "GetRuntime",
        {"RuntimeId": runtime_id},
        method="POST",
        verbose=verbose,
        config_path=config_path,
    )
    error = api_error(result)
    if error:
        raise RuntimeError("GetRuntime failed: " + error)
    return result


def update_state_from_get_runtime(state_path, state, result):
    state["runtime_id"] = extract_runtime_id(result) or state.get("runtime_id", "")
    state["status"] = extract_runtime_status(result)
    state["endpoint"] = extract_endpoint(result)
    state["updated_at"] = datetime.datetime.now().isoformat()
    state["last_get_response_metadata"] = result.get("ResponseMetadata") or {}
    write_state(state_path, state)
    return state


def print_runtime_summary(runtime_id, status, endpoint, state_path):
    print(f"RuntimeId: {runtime_id}")
    print(f"Status: {status or '-'}")
    print(f"Endpoint: {endpoint or '-'}")
    print(f"State: {state_path}")


def wait_for_ready(
    config_path,
    runtime_id,
    state_path,
    state,
    timeout_seconds,
    interval_seconds,
    verbose,
):
    deadline = time.time() + timeout_seconds
    last_state = state

    while True:
        result = get_runtime(config_path, runtime_id, verbose)
        last_state = update_state_from_get_runtime(state_path, last_state, result)

        status = last_state.get("status")
        endpoint = last_state.get("endpoint")
        print_runtime_summary(runtime_id, status, endpoint, state_path)

        if status == READY_STATUS:
            return last_state

        if status in FAILED_STATUSES:
            raise RuntimeError(f"runtime entered failed status: {status}")

        if time.time() >= deadline:
            print(
                "Runtime is not Ready before timeout. "
                "Please run the get command later to check status manually."
            )
            return last_state

        print(f"Runtime is not Ready yet; retry in {interval_seconds}s.")
        time.sleep(interval_seconds)


def runtime_id_from_args_or_state(args, state):
    if getattr(args, "runtime_id", None):
        return args.runtime_id
    runtime_id = state.get("runtime_id")
    if runtime_id:
        return runtime_id
    raise ValueError(
        "missing RuntimeId; pass --runtime-id or run create first with the same --state"
    )


def run_create(args):
    config = load_config(args.config)
    state_path = args.state or default_state_path(args.config)
    state = read_state(state_path)
    runtime_id = state.get("runtime_id")

    if runtime_id:
        print(f"Found existing RuntimeId in state, skip create: {runtime_id}")
    else:
        body, body_source = resolve_create_body(config, args.config, args.body_file)
        lock_path = state_path + ".lock"
        acquire_create_lock(lock_path)
        try:
            runtime_id, state = create_runtime(
                args.config,
                body,
                body_source,
                state_path,
                not args.quiet,
            )
            print(f"CreateRuntime succeeded, RuntimeId: {runtime_id}")
        finally:
            release_create_lock(lock_path)

    wait_for_ready(
        args.config,
        runtime_id,
        state_path,
        state or read_state(state_path),
        args.timeout,
        args.interval,
        not args.quiet,
    )


def run_get(args):
    state_path = args.state or default_state_path(args.config)
    state = read_state(state_path)
    runtime_id = runtime_id_from_args_or_state(args, state)

    result = get_runtime(args.config, runtime_id, not args.quiet)
    state = update_state_from_get_runtime(state_path, state, result)
    print_runtime_summary(
        runtime_id,
        state.get("status"),
        state.get("endpoint"),
        state_path,
    )


def build_parser():
    parser = argparse.ArgumentParser(
        description="Create or inspect a VKE AgentKit runtime.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 create_vke_runtime.py create --config config.json\n"
            "  python3 create_vke_runtime.py get --config config.json\n"
            "  python3 create_vke_runtime.py get --config config.json --runtime-id r-xxxx\n"
            "  python3 create_vke_runtime.py create --config config.json --body-file body.json\n"
            "\n"
            "Config fields:\n"
            "  volcengine_access_key          火山引擎 AK。\n"
            "  volcengine_secret_key          火山引擎 SK。\n"
            "  volcengine_region              AgentKit 服务地域，例如 cn-beijing。\n"
            "  volcengine_agentkit_host       AgentKit 服务域名，例如 agentkit.cn-beijing.volcengineapi.com。\n"
            "  volcengine_agentkit_api_version  AgentKit OpenAPI 版本。\n"
            "  volcengine_agentkit_service    AgentKit 服务名称，线上环境为 agentkit。\n"
            "  x_forward_env                  测试环境标识，线上环境不传。\n"
            "  name                           Agent Runtime 名称前缀。\n"
            "  artifact_url                   镜像地址。\n"
            "  role_name                      火山引擎 IAM Role 名称。\n"
            "  DiscoveryUrl                   OAuth/OIDC IdP discovery URL。\n"
            "  namespace                      VKE 集群 namespace。\n"
            "  vke_cluster_id                 VKE 集群 ID。\n"
            "  WorkspaceId                    CP 服务工作区，未配置时默认为 default。\n"
            "  min_instance                   AgentKit Runtime 最小实例数。\n"
            "  max_instance                   AgentKit Runtime 最大实例数。\n"
            "\n"
            "Runtime name:\n"
            "  name is a prefix. The final CreateRuntime body uses\n"
            "  <name>-YYYYmmddHHMMSS for config, config.body, and --body-file.\n"
            "\n"
            "See README.md for full config.json and body.json examples."
        ),
    )

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", required=True, help="config.json path")
    common.add_argument("--state", help="runtime state json path")
    common.add_argument(
        "--quiet", action="store_true", help="hide detailed API request/response logs"
    )

    subparsers = parser.add_subparsers(dest="command")

    create_parser = subparsers.add_parser(
        "create",
        parents=[common],
        help="create once, then poll status until Ready",
    )
    create_parser.add_argument(
        "--body-file",
        help="full CreateRuntime JSON body path; when set, config body fields are ignored",
    )
    create_parser.add_argument(
        "--timeout", type=int, default=300, help="seconds to wait for Ready"
    )
    create_parser.add_argument(
        "--interval", type=int, default=10, help="seconds between GetRuntime checks"
    )

    get_parser = subparsers.add_parser(
        "get",
        parents=[common],
        help="get runtime status by --runtime-id or saved state",
    )
    get_parser.add_argument(
        "--runtime-id", help="RuntimeId; defaults to the value in state"
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "create":
            run_create(args)
        elif args.command == "get":
            run_get(args)
        else:
            parser.print_help()
            sys.exit(2)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
