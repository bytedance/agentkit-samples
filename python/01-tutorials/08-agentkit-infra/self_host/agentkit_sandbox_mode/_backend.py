"""复用资源教程的签名、配置和输出，部署 AgentKit SelfHosted 后端。"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

SHARED = Path(__file__).resolve().parents[2] / "resource_to_chat_http"
sys.path.insert(0, str(SHARED))

from _clients import DataPlaneClient, TopClient  # noqa: E402
from _common import emit, load_state, parser, run as run, wait_until  # noqa: E402
from _config import (  # noqa: E402
    _mapping,
    _positive_integer,
    _read_yaml,
    _string,
    _validate_data_url,
    validated_config,
)
from _iam import ensure_runtime_role  # noqa: E402

REGISTRY = "enterprise-public-cn-beijing.cr.volces.com/vefaas-public"
DISPATCHER_IMAGE = (
    f"{REGISTRY}/agentkit-selfhostsandbox:"
    "runtime-anthropic-sdk-20261103-a28aa9d7-59ee0972"
)
SANDBOX_IMAGE = f"{REGISTRY}/agentkit-selfhostsandbox:tool-1.0.0"


def backend_path() -> Path:
    """返回独立的部署状态路径，避免覆盖资源教程的状态。"""
    configured = os.getenv("HARNESS_INFRA_BACKEND_STATE", "").strip()
    return (
        Path(configured).expanduser().resolve()
        if configured
        else Path(__file__).with_name(".sandbox_agentkit_backend.json")
    )


def write_backend(state: dict[str, Any]) -> None:
    """以私有权限原子保存标识与幂等 token；状态不包含凭据明文。"""
    path = backend_path()
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def settings() -> dict[str, Any]:
    """解析可选后端配置；缺省值与 config.yaml.example 保持一致。"""
    root = _read_yaml()
    raw = _mapping(root.get("self_host", {}), "self_host")
    raw = _mapping(raw.get("agentkit_sandbox", {}), "self_host.agentkit_sandbox")
    result: dict[str, Any] = {}
    defaults = {
        "dispatcher_image": DISPATCHER_IMAGE,
        "sandbox_image": SANDBOX_IMAGE,
        "sandbox_command": "/opt/gem/run.sh",
        "role_name": "AgentKitDefaultRuntimeAccess",
        "project_name": "default",
        "name_prefix": "selfhost",
        "base_url": "",
        "environment_id": "",
        "environment_key": "",
        "existing_tool_id": "",
    }
    for name, default in defaults.items():
        result[name] = _string(
            raw.get(name, default),
            f"self_host.agentkit_sandbox.{name}",
            allow_empty=not default,
        )
    for name, default in {
        "dispatcher_cpu_milli": 1000,
        "dispatcher_memory_mb": 2048,
        "sandbox_cpu_milli": 2000,
        "sandbox_memory_mb": 4096,
        "sandbox_port": 8080,
        "ttl_seconds": 3600,
        "idle_timeout_seconds": 180,
    }.items():
        result[name] = _positive_integer(
            raw.get(name, default), f"self_host.agentkit_sandbox.{name}"
        )
    if result["sandbox_port"] > 65535:
        raise RuntimeError("sandbox_port must be <= 65535")
    if not result["name_prefix"].replace("-", "").isalnum():
        raise RuntimeError("name_prefix must contain only letters, numbers and '-'")
    return result


def connection(
    config: Any, options: dict[str, Any], *, dry_run: bool
) -> dict[str, str]:
    """优先使用完整的三项连接配置，否则复用 01 的共享配置与状态。"""
    explicit = {
        "base_url": os.getenv("ANTHROPIC_BASE_URL", "").strip() or options["base_url"],
        "environment_id": os.getenv("ANTHROPIC_ENVIRONMENT_ID", "").strip()
        or options["environment_id"],
        "environment_key": os.getenv("ANTHROPIC_ENVIRONMENT_KEY", "").strip()
        or options["environment_key"],
    }
    if any(explicit.values()):
        if not all(explicit.values()):
            raise RuntimeError(
                "set all three ANTHROPIC_BASE_URL / ANTHROPIC_ENVIRONMENT_ID / "
                "ANTHROPIC_ENVIRONMENT_KEY values"
            )
        explicit["base_url"] = _validate_data_url(
            "ANTHROPIC_BASE_URL", explicit["base_url"]
        )
        return explicit
    if config.environment.type != "SelfHosted":
        raise RuntimeError("run resource_to_chat_http/01 with SelfHosted (n) first")
    if dry_run:
        return {
            "base_url": config.session.endpoint_base_url or "<ANTHROPIC_BASE_URL>",
            "environment_id": "<ANTHROPIC_ENVIRONMENT_ID>",
            "environment_key": "<ANTHROPIC_ENVIRONMENT_KEY>",
        }
    state = load_state(TopClient(config.control))
    environment_id = state.get("resources", {}).get("environment", {}).get("id", "")
    if not environment_id or not config.environment.env_api_key_value:
        raise RuntimeError(
            "SelfHosted environment/key missing; run 01_create_resources.py"
        )
    if not config.session.endpoint_base_url:
        raise RuntimeError("session.endpoint_base_url is missing")
    return {
        "base_url": config.session.endpoint_base_url,
        "environment_id": environment_id,
        "environment_key": config.environment.env_api_key_value,
    }


def validate_connection(client: TopClient, conn: dict[str, str]) -> None:
    """确认目标为 Active SelfHosted，并验证环境范围的 Session 访问。"""
    env = client.call("GetEnvironment", {"EnvironmentId": conn["environment_id"]})
    if (
        env.get("Status") != "Active"
        or env.get("Config", {}).get("Type") != "SelfHosted"
    ):
        raise RuntimeError("target Environment must be Active SelfHosted")
    workspace = client.config.workspace_id
    if workspace and env.get("WorkspaceId") != workspace:
        raise RuntimeError("SelfHosted Environment belongs to another Workspace")
    data = DataPlaneClient(conn["base_url"], conn["environment_key"])
    remote = data.call(
        "GET",
        "/v1/sessions",
        params={"environment_id": conn["environment_id"], "limit": 1},
    )
    sessions = remote.get("data")
    if not isinstance(sessions, list):
        raise RuntimeError("List Sessions response is missing data[]")
    if any(item.get("environment_id") != conn["environment_id"] for item in sessions):
        raise RuntimeError("Environment key/endpoint does not match EnvironmentId")


def tool_request(options: dict[str, Any], token: str, name: str) -> dict[str, Any]:
    """构造 AppO CreateTool 请求；执行参数由 Dispatcher 注入实例。"""
    return {
        "Name": name,
        "ToolType": "Private",
        "ImageUrl": options["sandbox_image"],
        "Command": options["sandbox_command"],
        "Port": options["sandbox_port"],
        "CpuMilli": options["sandbox_cpu_milli"],
        "MemoryMb": options["sandbox_memory_mb"],
        "ProjectName": options["project_name"],
        "NetworkConfiguration": {"EnablePublicNetwork": True},
        "AuthorizerConfiguration": {
            "KeyAuth": {"ApiKeyName": "x-api-key", "ApiKeyLocation": "header"}
        },
        "ClientToken": token,
    }


def runtime_request(
    options: dict[str, Any],
    conn: dict[str, str],
    region: str,
    tool_id: str,
    token: str,
    name: str,
) -> dict[str, Any]:
    """构造 AppO CreateRuntime 请求，将三项连接信息映射到镜像配置。"""
    envs = {
        "MANAGED_AGENT_API_MODE": "oma",
        "MANAGED_AGENT_AUTH_HEADER": "x-api-key",
        "ANTHROPIC_BASE_URL": conn["base_url"],
        "MA_ENVIRONMENT_ID": conn["environment_id"],
        "MA_API_KEY": conn["environment_key"],
        "SANDBOX_PROVIDER": "agentkit",
        "AGENTKIT_TOOL_ID": tool_id,
        "VOLCENGINE_REGION": region,
        "AGENTKIT_TTL_SECONDS": str(options["ttl_seconds"]),
        "AGENTKIT_SESSION_IDLE_TIMEOUT_SECONDS": str(options["idle_timeout_seconds"]),
    }
    return {
        "Name": name,
        "ArtifactType": "image",
        "ArtifactUrl": options["dispatcher_image"],
        "RoleName": options["role_name"],
        "ProjectName": options["project_name"],
        "Envs": [{"Key": key, "Value": value} for key, value in envs.items()],
        "NetworkConfiguration": {"EnablePublicNetwork": True},
        "AuthorizerConfiguration": {
            "KeyAuth": {"ApiKeyName": "x-api-key", "ApiKeyLocation": "header"}
        },
        "CpuMilli": options["dispatcher_cpu_milli"],
        "MemoryMb": options["dispatcher_memory_mb"],
        "MinInstance": 1,
        "MaxInstance": 1,
        "MaxConcurrency": 100,
        "ClientToken": token,
    }


def public_request(body: dict[str, Any]) -> dict[str, Any]:
    """隐藏列表形式 Envs 内的密钥，保留非敏感映射供核对。"""
    result = dict(body)
    if "Envs" in result:
        result["Envs"] = [
            {**item, "Value": "<redacted>"}
            if item["Key"] == "MA_API_KEY"
            else dict(item)
            for item in result["Envs"]
        ]
    return result


def deployment_state(client: TopClient, options: dict[str, Any]) -> dict[str, Any]:
    """在首个写请求前保存 token；按账号、入口、地域及项目隔离恢复。"""
    scope = {
        "endpoint": client.scope,
        "account_hash": hashlib.sha256(client.config.access_key.encode()).hexdigest(),
        "project": options["project_name"],
    }
    path = backend_path()
    if path.exists():
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("schema_version") != 1 or state.get("scope") != scope:
            raise RuntimeError(
                "backend state scope changed; use HARNESS_INFRA_BACKEND_STATE"
            )
        return state
    suffix = uuid.uuid4().hex[:12]
    state = {
        "schema_version": 1,
        "scope": scope,
        "names": {
            name: f"{options['name_prefix'][:30]}-{suffix}-{name}"
            for name in ("tool", "runtime")
        },
        "tokens": {name: uuid.uuid4().hex for name in ("tool", "runtime")},
        "resources": {},
    }
    write_backend(state)
    return state


def ensure_resource(
    client: TopClient,
    state: dict[str, Any],
    kind: str,
    body: dict[str, Any],
    *,
    json_output: bool,
) -> str:
    """保存创建返回 ID 后等待 Ready；重跑只查询，配置变化拒绝静默复用。"""
    resource = "Tool" if kind == "tool" else "Runtime"
    id_field = f"{resource}Id"
    fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    saved = state["resources"].setdefault(kind, {})
    if saved.get("fingerprint") and saved["fingerprint"] != fingerprint:
        raise RuntimeError(f"{resource} configuration changed; use a new backend state")
    saved["fingerprint"] = fingerprint
    write_backend(state)
    if not saved.get("id"):
        emit(
            "request",
            f"创建 {resource}",
            json_output=json_output,
            action=f"Create{resource}",
            body=public_request(body),
        )
        result = client.call(f"Create{resource}", body)
        resource_id = result.get(id_field)
        if not isinstance(resource_id, str) or not resource_id:
            raise RuntimeError(f"Create{resource} response is missing {id_field}")
        saved.update(id=resource_id, owned=True, status=result.get("Status"))
        write_backend(state)
    result = wait_until(
        lambda: client.call(f"Get{resource}", {id_field: saved["id"]}),
        lambda value: value.get("Status") == "Ready",
        lambda value: str(value["Status"])
        if value.get("Status")
        in {
            "Failed",
            "Error",
            "CreateFailed",
            "UpdateFailed",
            "Deleting",
        }
        else None,
        description=f"{resource} Ready",
        json_output=json_output,
        report_result=False,
    )
    saved["status"] = result["Status"]
    write_backend(state)
    emit(
        "resource",
        f"{resource} Ready",
        json_output=json_output,
        id=saved["id"],
        status=saved["status"],
    )
    return saved["id"]


def reuse_tool(
    client: TopClient,
    state: dict[str, Any],
    options: dict[str, Any],
    *,
    json_output: bool,
) -> str:
    """显式复用匹配的 Ready 模板，不修改模板，也不将其登记为自有资源。"""
    tool_id = options["existing_tool_id"]
    saved = state["resources"].get("tool", {})
    if saved.get("id") and saved["id"] != tool_id:
        raise RuntimeError(
            "existing_tool_id differs from saved ToolId; use a new state"
        )
    tool = client.call("GetTool", {"ToolId": tool_id})
    expected = {
        "ToolType": "Private",
        "Status": "Ready",
        "ImageUrl": options["sandbox_image"],
        "Command": options["sandbox_command"],
        "Port": options["sandbox_port"],
        "ProjectName": options["project_name"],
    }
    if any(tool.get(key) != value for key, value in expected.items()):
        raise RuntimeError(
            "existing Tool must be Ready and match image/command/port/project"
        )
    state["resources"]["tool"] = {"id": tool_id, "status": "Ready", "owned": False}
    write_backend(state)
    emit(
        "resource",
        "复用兼容 Tool 模板",
        json_output=json_output,
        id=tool_id,
        status="Ready",
        owned=False,
    )
    return tool_id


def main(*, dispatcher: bool) -> None:
    """执行部署入口；dry-run 不创建客户端、不访问网络、不写状态。"""
    args = parser(
        "创建 AgentKit Dispatcher 和工具 Sandbox"
        if dispatcher
        else "创建 AgentKit 工具 Sandbox 模板"
    ).parse_args()
    config = validated_config(
        require_model_key_name=False, require_credentials=not args.dry_run
    )
    options = settings()
    conn = connection(config, options, dry_run=args.dry_run) if dispatcher else None
    if args.dry_run:
        actions = [
            {
                "action": "CreateTool",
                "body": tool_request(options, "<tool-client-token>", "<tool-name>"),
            }
        ]
        if options["existing_tool_id"]:
            actions = [
                {"action": "GetTool", "body": {"ToolId": options["existing_tool_id"]}}
            ]
        if dispatcher:
            actions.append(
                {
                    "action": "CreateRuntime",
                    "body": public_request(
                        runtime_request(
                            options,
                            conn,
                            config.control.region,
                            "<ToolId>",
                            "<runtime-client-token>",
                            "<runtime-name>",
                        )
                    ),
                }
            )
        emit(
            "dry_run",
            "SelfHosted 后端部署计划",
            json_output=args.json_output,
            actions=actions,
        )
        return
    client = TopClient(config.control)
    if dispatcher:
        validate_connection(client, conn)
    state = deployment_state(client, options)
    if options["existing_tool_id"]:
        tool_id = reuse_tool(client, state, options, json_output=args.json_output)
    else:
        if state["resources"].get("tool", {}).get("owned") is False:
            raise RuntimeError(
                "retain existing_tool_id when resuming a reused template"
            )
        tool_id = ensure_resource(
            client,
            state,
            "tool",
            tool_request(options, state["tokens"]["tool"], state["names"]["tool"]),
            json_output=args.json_output,
        )
    if dispatcher:
        ensure_runtime_role(config.control, options["role_name"])
        runtime_id = ensure_resource(
            client,
            state,
            "runtime",
            runtime_request(
                options,
                conn,
                config.control.region,
                tool_id,
                state["tokens"]["runtime"],
                state["names"]["runtime"],
            ),
            json_output=args.json_output,
        )
        emit(
            "completed",
            "SelfHosted 后端已就绪，请运行 resource_to_chat_http/02",
            json_output=args.json_output,
            tool_id=tool_id,
            runtime_id=runtime_id,
            environment_id=conn["environment_id"],
        )
