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


def print_config_example():
    print(
        json.dumps(
            {
                "volcengine_access_key": "",
                "volcengine_secret_key": "",
                "volcengine_region": "cn-beijing",
                "volcengine_agentkit_host": "agentkit-stg.cn-beijing.volcengineapi.com",
                "volcengine_agentkit_api_version": "2025-10-30",
                "volcengine_agentkit_service": "agentkit_stg",
                "x_forward_env": "liulei",
                "artifact_url": "agentkit-platform-2107625663-cn-beijing.cr.volces.com/hia/echo-api:2026-07-27",
                "role_name": "Agentkit_runtime_vke_test",
                "DiscoveryUrl": "https://example.com/.well-known/openid-configuration",
                "namespace": "hiagent",
                "vke_cluster_id": "YOUR_VKE_CLUSTER_ID",
                "min_instance": 1,
                "max_instance": 2,
                "WorkspaceId": "",
                "body": {
                    "name": "optional-full-body-example",
                    "artifact_type": "image",
                    "artifact_url": "optional-full-body-wins-over-fields",
                    "role_name": "optional-full-body-wins-over-fields",
                    "provider": "VKE",
                    "min_instance": 1,
                    "max_instance": 2,
                    "authorizer_configuration": {
                        "CustomJwtAuthorizer": {
                            "DiscoveryUrl": "optional-full-body-wins-over-fields",
                        },
                    },
                    "provider_config": {
                        "vke_configuration": {
                            "vke_cluster_id": "optional-full-body-wins-over-fields",
                            "namespace": "optional-full-body-wins-over-fields",
                        },
                    },
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )


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
    if missing:
        raise ValueError(
            "Missing required runtime config field(s) in "
            + config_path
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


def runtime_name():
    return "single-chat-gateway-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")


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

    workspace_id = config_text(config, "WorkspaceId")
    if workspace_id:
        vke_configuration["WorkspaceId"] = workspace_id

    return {
        "name": runtime_name(),
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
        return ensure_body_dict(read_json_file(body_file), body_file), "body_file"

    if "body" in config and config["body"] is not None:
        return ensure_body_dict(config["body"], config_path + ":body"), "config.body"

    validate_runtime_config(config, config_path)
    return build_create_body(config), "config_fields"


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
    )
    parser.add_argument(
        "--print-config-example",
        action="store_true",
        help="print a config example and exit",
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
        if args.print_config_example:
            print_config_example()
            return

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
