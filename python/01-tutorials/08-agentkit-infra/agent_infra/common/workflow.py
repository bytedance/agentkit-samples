"""从控制面资源创建到数据面对话及回收的确定性工作流。"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import replace
from typing import Any, Callable

from .clients import DataPlaneClient, HarnessInfraError, TopClient
from .state import (
    emit,
    report_resource,
    resource_info,
    save_state,
    update_resource,
    wait_progress,
    wait_until,
)
from .config import (
    ExampleConfig,
    persist_environment_api_key,
    persist_session,
    persist_workspace,
)
from .display import display_selfhost_connection
from .iam import ensure_runtime_role

NOT_FOUND_CODES = {
    "InvalidApiKey.NotFound",
    "InvalidEnvironment.NotFound",
    "InvalidHarness.NotFound",
    "ResourceNotFound",
}
REQUIRED_SANDBOX_TOOLS = ("write", "edit", "read", "grep", "glob", "bash")
TOOL_USE_EVENT_TYPES = {
    "agent.tool_use",
    "agent.custom_tool_use",
    "agent.mcp_tool_use",
}
TOOL_RESULT_EVENT_TYPES = {
    "user.tool_result",
    "agent.tool_result",
    "user.custom_tool_result",
    "agent.mcp_tool_result",
}


def _not_found(exc: HarnessInfraError) -> bool:
    return exc.status_code == 404 or exc.code in NOT_FOUND_CODES


def extract_tool_names(event: Any) -> set[str]:
    """从不同 AgentLoop 的工具事件结构中提取真实工具名称。"""

    names: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if (
                    key in {"name", "tool_name", "function_name"}
                    and isinstance(item, str)
                    and item
                ):
                    names.add(item.lower())
                elif isinstance(item, (dict, list)):
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    if isinstance(event, dict) and "tool" in str(event.get("type") or "").lower():
        visit(event)
    return names


def missing_tool_names(observed: set[str]) -> list[str]:
    """按原生工具名及 AgentLoop 前缀兼容规则返回缺失工具。"""

    return [
        required
        for required in REQUIRED_SANDBOX_TOOLS
        if not any(
            name == required or name.endswith((f"_{required}", f".{required}"))
            for name in observed
        )
    ]


def _tool_reference(event: dict[str, Any]) -> str:
    """返回工具结果引用的调用 ID，兼容原生、自定义和 MCP 工具字段。"""

    for key in ("tool_use_id", "custom_tool_use_id", "mcp_tool_use_id"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _tool_use_id(event: dict[str, Any]) -> str:
    """返回工具调用的关联 ID；无显式引用时使用事件 ID。"""

    return _tool_reference(event) or str(event.get("id") or "")


def _tool_result_failed(event: dict[str, Any]) -> bool:
    """递归识别工具结果中的失败标记。"""

    def contains_error(value: Any) -> bool:
        if isinstance(value, dict):
            if value.get("is_error") is True:
                return True
            return any(contains_error(item) for item in value.values())
        if isinstance(value, list):
            return any(contains_error(item) for item in value)
        return False

    return contains_error(event)


def _tool_result_summary(event: dict[str, Any], limit: int = 500) -> str:
    """生成结果摘要；完整事件通过独立的 raw_result 字段保留。"""

    content = event.get("content")
    if isinstance(content, str):
        text = content
    else:
        try:
            text = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            text = str(content)
    text = text.strip() or "<empty>"
    return text if len(text) <= limit else f"{text[:limit]}…"


def collect_tool_executions(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将一轮事件关联为工具调用结果，自动合并服务端镜像结果事件。"""

    uses: list[tuple[str, dict[str, Any]]] = []
    results: dict[str, list[dict[str, Any]]] = {}
    for event in sorted(events, key=lambda item: int(item.get("sequence") or 0)):
        event_type = str(event.get("type") or "")
        if event_type in TOOL_USE_EVENT_TYPES:
            use_id = _tool_use_id(event)
            if use_id:
                uses.append((use_id, event))
        elif event_type in TOOL_RESULT_EVENT_TYPES:
            reference = _tool_reference(event)
            if reference:
                results.setdefault(reference, []).append(event)

    executions: list[dict[str, Any]] = []
    for use_id, use in uses:
        matches = results.get(use_id, [])
        if not matches:
            continue
        # AgentKit 可能同时持久化 user-side 和 agent-side 镜像结果，优先展示规范化结果。
        result = next(
            (item for item in matches if item.get("type") == "agent.tool_result"),
            matches[0],
        )
        names = sorted(extract_tool_names(use))
        executions.append(
            {
                "tool_use_id": use_id,
                "tool_name": names[0] if names else "unknown",
                "sequence": int(result.get("sequence") or 0),
                "failed": _tool_result_failed(result),
                "result": _tool_result_summary(result),
                "raw_result": result,
            }
        )
    return executions


def emit_tool_executions(
    events: list[dict[str, Any]],
    emitted: set[str],
    *,
    json_output: bool,
) -> set[str]:
    """实时输出尚未展示的工具执行结果，并返回成功工具名集合。"""

    successful: set[str] = set()
    for execution in collect_tool_executions(events):
        tool_use_id = str(execution["tool_use_id"])
        tool_name = str(execution["tool_name"])
        if not execution["failed"]:
            successful.add(tool_name.lower())
        if tool_use_id in emitted:
            continue
        emitted.add(tool_use_id)
        emit(
            "tool_result",
            f"工具步骤 {len(emitted)}：{tool_name}",
            json_output=json_output,
            step=len(emitted),
            heading=False,
            tool_name=tool_name,
            tool_use_id=tool_use_id,
            sequence=execution["sequence"],
            status="failed" if execution["failed"] else "completed",
            result=execution["result"],
            raw_result=execution["raw_result"],
        )
    return successful


def _list_all(
    client: TopClient,
    action: str,
    body: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """完整遍历控制面 Items/NextToken 分页。"""

    request = {**(body or {}), "MaxResults": 100}
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    while True:
        result = client.call(action, request)
        page = result.get("Items")
        token = result.get("NextToken")
        if not isinstance(page, list) or not all(
            isinstance(item, dict) for item in page
        ):
            raise RuntimeError(f"{action} response is missing Items[]")
        if token is not None and not isinstance(token, str):
            raise RuntimeError(f"{action} returned an invalid NextToken")
        items.extend(page)
        if not token:
            return items
        if token in seen:
            raise RuntimeError(f"{action} returned a repeated NextToken")
        seen.add(token)
        request["NextToken"] = token


def _prepare_endpoint(
    client: TopClient,
    state: dict[str, Any],
    *,
    endpoint_id: str,
    apig_gateway_id: str,
    json_output: bool,
) -> dict[str, Any]:
    """复用唯一 Ready Endpoint；无 Endpoint 时通过 CreateRoute 同步创建。"""

    recorded = state["resources"].get("endpoint", {})
    if recorded.get("id"):
        report_resource(state, "endpoint", json_output=json_output)
        return {"EndpointId": recorded["id"], "BaseUrl": recorded["base_url"]}
    with wait_progress("查询 Endpoint", json_output=json_output):
        endpoints = _list_all(client, "ListEndpoints")
    if endpoint_id:
        selected = [
            endpoint
            for endpoint in endpoints
            if endpoint.get("EndpointId") == endpoint_id
        ]
        if len(selected) != 1:
            raise RuntimeError(f"EndpointId is not visible: {endpoint_id}")
        endpoint = selected[0]
        reused = True
    elif not endpoints:
        gateway = apig_gateway_id.strip()
        if not gateway:
            raise RuntimeError(
                "No Endpoint is visible: CreateRoute requires a non-empty "
                "environment.apig_gateway_id (contract field; the actual gateway "
                "comes from server configuration)"
            )
        with wait_progress("创建 Endpoint", json_output=json_output):
            endpoint = client.call("CreateRoute", {"ApigGatewayId": gateway})
        reused = False
    elif len(endpoints) == 1:
        endpoint = endpoints[0]
        reused = True
    else:
        raise RuntimeError("multiple Endpoints are visible; rerun with --endpoint-id")
    if endpoint.get("Status") != "ready":
        raise RuntimeError(f"Endpoint is not ready: {endpoint.get('Status') or '-'}")
    value = {
        "id": endpoint.get("EndpointId"),
        "name": endpoint.get("Name"),
        "base_url": endpoint.get("BaseUrl"),
        "status": endpoint.get("Status"),
        "owned": not reused,
    }
    if not isinstance(value["id"], str) or not isinstance(value["base_url"], str):
        raise TypeError("Endpoint response is missing EndpointId/BaseUrl")
    update_resource(state, "endpoint", value)
    report_resource(state, "endpoint", json_output=json_output)
    return endpoint


def _wait_environment_resource(
    client: TopClient,
    state: dict[str, Any],
    environment_id: str,
    *,
    json_output: bool,
) -> dict[str, Any]:
    """等待 Cloud Environment 自动资源出现并收敛到 Ready。"""

    deadline = time.monotonic() + 15 * 60
    resource: dict[str, Any] | None = None
    with wait_progress("Cloud Sandbox 准备", json_output=json_output) as update:
        while time.monotonic() < deadline:
            items = _list_all(
                client,
                "ListEnvironmentResources",
                {"EnvironmentId": environment_id},
            )
            active = [item for item in items if item.get("Status") != "Deleted"]
            if len(active) > 1:
                raise RuntimeError(
                    "Cloud Environment returned multiple active resources"
                )
            if active:
                resource = active[0]
                break
            update(None)
            time.sleep(5)
    if resource is None or not isinstance(resource.get("ResourceId"), str):
        raise TimeoutError("Cloud Environment resource did not appear")
    resource_id = resource["ResourceId"]
    update_resource(
        state,
        "environment_resource",
        {"id": resource_id, "status": resource.get("Status"), "owned": True},
    )
    ready = wait_until(
        lambda: client.call("GetEnvironmentResource", {"ResourceId": resource_id}),
        lambda value: (
            value.get("Status") == "Ready"
            and value.get("DesiredGeneration") == value.get("ObservedGeneration")
        ),
        lambda value: (
            str(value.get("ErrorCode") or value.get("Status"))
            if value.get("Status") in {"Failed", "DeleteFailed"}
            or value.get("ErrorCode")
            else None
        ),
        description="Cloud Sandbox Ready",
        json_output=json_output,
        report_result=False,
    )
    update_resource(
        state,
        "environment_resource",
        {
            "id": resource_id,
            "name": ready.get("Name") or resource.get("Name"),
            "status": ready.get("Status"),
            "revision": ready.get("Revision"),
            "desired_generation": ready.get("DesiredGeneration"),
            "observed_generation": ready.get("ObservedGeneration"),
            "tool_id": ready.get("ToolId"),
            "owned": True,
        },
    )
    return ready


def _create_session_store(
    client: TopClient,
    state: dict[str, Any],
    config: ExampleConfig,
    *,
    json_output: bool,
) -> dict[str, Any]:
    """创建托管 Serverless PG SessionStore，并等待服务完成异步准备。"""

    request: dict[str, Any] = {
        "ProjectName": config.session_store.project_name,
        "Name": state["names"]["session_store"],
        "Description": "Harness Infra resource-to-chat HTTP tutorial",
        "ProviderType": "SERVERLESS_PG",
    }
    if config.session_store.vpc_id:
        request["VpcConfig"] = {
            "VpcId": config.session_store.vpc_id,
            "SubnetIds": config.session_store.subnet_ids,
        }
    session_store_id = state["resources"].get("session_store", {}).get("id")
    if not session_store_id:
        with wait_progress("创建 SessionStore", json_output=json_output):
            created = client.call("CreateSessionStore", request)
        _record_session_store(state, config, created)
        session_store_id = created["SessionStoreId"]
    ready = wait_until(
        lambda: client.call(
            "GetSessionStore",
            {"SessionStoreId": session_store_id},
        ),
        lambda value: (
            value.get("Status") == "Ready"
            and value.get("ProviderType") == "SERVERLESS_PG"
        ),
        lambda value: (
            str(value.get("Status"))
            if value.get("Status") in {"Failed", "Deleting", "Deleted"}
            else None
        ),
        description="SessionStore Ready",
        json_output=json_output,
        report_result=False,
    )
    if ready.get("SessionStoreId") != session_store_id:
        raise RuntimeError("GetSessionStore returned a mismatched SessionStoreId")
    update_resource(
        state,
        "session_store",
        {"id": session_store_id, "status": "Ready", "owned": True},
    )
    report_resource(state, "session_store", json_output=json_output)
    return ready


def _record_session_store(
    state: dict[str, Any], config: ExampleConfig, created: dict[str, Any]
) -> None:
    """先保存 ID，供异步等待中断后的重跑及清理使用。"""
    session_store_id = created.get("SessionStoreId")
    if not isinstance(session_store_id, str) or not session_store_id:
        raise RuntimeError("CreateSessionStore response is missing SessionStoreId")
    if created.get("ProviderType") != "SERVERLESS_PG":
        raise RuntimeError("CreateSessionStore did not return SERVERLESS_PG")
    update_resource(
        state,
        "session_store",
        {
            "id": session_store_id,
            "name": created.get("Name") or state["names"]["session_store"],
            "parameters": {
                "ProjectName": config.session_store.project_name,
                "ProviderType": "SERVERLESS_PG",
                "VpcId": config.session_store.vpc_id,
            },
            "status": created.get("Status"),
            "owned": True,
        },
    )


def create_environment(
    client: TopClient,
    state: dict[str, Any],
    config: ExampleConfig,
    *,
    json_output: bool = False,
    write_workspace: bool = True,
) -> ExampleConfig:
    """创建或继续等待 Environment；记录 Workspace 和云 Sandbox 信息。"""
    names = state["names"]
    tokens = state["tokens"]
    environment_config = {
        "Type": config.environment.type,
    }
    if config.environment.type == "Cloud":
        environment_config["Resources"] = config.environment.resources
    if config.environment.env_vars:
        environment_config["EnvVars"] = config.environment.env_vars
    environment_label = f"创建 {config.environment.type} Environment"

    emit(
        "request",
        environment_label,
        json_output=json_output,
        step=2,
    )
    with wait_progress(environment_label, json_output=json_output):
        recorded_id = state["resources"].get("environment", {}).get("id")
        if recorded_id:
            environment = client.call("GetEnvironment", {"EnvironmentId": recorded_id})
        else:
            environment = client.call(
                "CreateEnvironment",
                {
                    "Name": names["environment"],
                    "Description": "Harness Infra resource-to-chat HTTP tutorial",
                    "Config": environment_config,
                    "Metadata": config.environment.metadata,
                    "ClientToken": tokens["environment_create"],
                },
            )
    environment_id = environment.get("EnvironmentId")
    if not isinstance(environment_id, str) or not environment_id:
        raise RuntimeError("CreateEnvironment response is missing EnvironmentId")
    workspace_id = environment.get("WorkspaceId") or config.control.workspace_id
    if workspace_id:
        if config.control.workspace_id and config.control.workspace_id != workspace_id:
            raise RuntimeError("Environment belongs to another Workspace")
        client.config = replace(client.config, workspace_id=workspace_id)
        config = replace(config, control=client.config)
        state["control_scope"] = client.scope
        state["workspace_id"] = workspace_id
    update_resource(
        state,
        "environment",
        {
            "id": environment_id,
            "name": environment.get("Name") or names["environment"],
            "parameters": {
                **environment_config,
                **(
                    {
                        "EnvVars": {
                            name: "<redacted>" for name in config.environment.env_vars
                        }
                    }
                    if config.environment.env_vars
                    else {}
                ),
            },
            "status": environment.get("Status"),
            "owned": True,
        },
    )
    if workspace_id and write_workspace:
        persist_workspace(workspace_id)
    environment = wait_until(
        lambda: client.call("GetEnvironment", {"EnvironmentId": environment_id}),
        lambda value: value.get("Status") == "Active",
        lambda value: (
            str(value.get("Status")) if value.get("Status") == "Archived" else None
        ),
        description="Environment Active",
        json_output=json_output,
        report_result=False,
    )
    update_resource(
        state,
        "environment",
        {"id": environment_id, "status": "Active", "owned": True},
    )
    if config.environment.type == "Cloud":
        _wait_environment_resource(
            client,
            state,
            environment_id,
            json_output=json_output,
        )
    report_resource(
        state,
        "environment",
        json_output=json_output,
        result=(
            "Cloud Sandbox 已就绪"
            if config.environment.type == "Cloud"
            else "SelfHosted Env 已登记；工具执行需接入自托管后端"
        ),
    )
    return config


def create_resources(
    client: TopClient,
    state: dict[str, Any],
    config: ExampleConfig,
    *,
    endpoint_id: str = "",
    apig_gateway_id: str = "",
    json_output: bool = False,
    defer_session: bool = False,
) -> dict[str, Any]:
    """一次准备队列模式的控制面，并按需创建 APIG 会话。"""
    emit("step", "准备 Endpoint", json_output=json_output, step=1)
    _prepare_endpoint(
        client,
        state,
        endpoint_id=endpoint_id,
        apig_gateway_id=apig_gateway_id or config.environment.apig_gateway_id,
        json_output=json_output,
    )
    config = create_environment(client, state, config, json_output=json_output)
    environment_id = state["resources"]["environment"]["id"]
    create_harness(client, state, config, json_output=json_output)
    emit("request", "创建 SessionStore", json_output=json_output, step=4)
    session_store = _create_session_store(
        client, state, config, json_output=json_output
    )
    emit("request", "创建 Runtime", json_output=json_output, step=5)
    create_runtime_template(
        client, state, config, session_store["SessionStoreId"], json_output=json_output
    )
    return _finish_queue_resources(
        client,
        state,
        config,
        environment_id,
        defer_session=defer_session,
        json_output=json_output,
    )


def create_harness(
    client: TopClient,
    state: dict[str, Any],
    config: ExampleConfig,
    *,
    json_output: bool = False,
) -> None:
    """创建队列模式使用的 Harness；重跑时复用已记录的 ID。"""
    names = state["names"]
    tokens = state["tokens"]
    if not state["resources"].get("harness", {}).get("id"):
        emit("request", "创建 Harness", json_output=json_output, step=3)
        with wait_progress("创建 Harness", json_output=json_output):
            harness = client.call(
                "CreateHarness",
                {
                    "Name": names["harness"],
                    "Description": "Harness Infra resource-to-chat HTTP tutorial",
                    "Model": {
                        "Id": config.harness.model_id,
                        "BaseUrl": config.harness.model_base_url,
                    },
                    "AgentLoop": config.harness.agent_loop,
                    "System": config.harness.system_prompt,
                    "Tools": config.harness.tools,
                    "McpServers": config.harness.mcp_servers,
                    "Skills": config.harness.skills,
                    "Metadata": {"purpose": "resource-to-chat-tutorial"},
                    "ClientToken": tokens["harness_create"],
                },
            )
        harness_id = harness.get("HarnessId")
        if not isinstance(harness_id, str) or harness.get("Status") != "Active":
            raise RuntimeError("CreateHarness did not return an active Harness")
        update_resource(
            state,
            "harness",
            {
                "id": harness_id,
                "name": harness.get("Name") or names["harness"],
                "version": harness.get("HarnessVersion"),
                "status": harness.get("Status"),
                "owned": True,
            },
        )
    report_resource(state, "harness", json_output=json_output)


def create_runtime_template(
    client: TopClient,
    state: dict[str, Any],
    config: ExampleConfig,
    session_store_id: str,
    *,
    tool_id: str = "",
    json_output: bool = False,
) -> None:
    """准备执行角色，提交 Runtime 模板或继续等待已记录的 Runtime。"""
    runtime_id = state["resources"].get("runtime", {}).get("id")
    if not runtime_id:
        runtime_id = _submit_runtime_template(
            client,
            state,
            config,
            session_store_id,
            tool_id=tool_id,
            json_output=json_output,
        )
    wait_until(
        lambda: client.call("GetRuntime", {"RuntimeId": runtime_id}),
        lambda value: value.get("Status") == "Ready",
        lambda value: (
            str(value.get("Status"))
            if value.get("Status") in {"Error", "Aborted", "Deleting", "Deleted"}
            else None
        ),
        description="Runtime Ready",
        json_output=json_output,
        report_result=False,
    )
    update_resource(
        state,
        "runtime",
        {"id": runtime_id, "status": "Ready", "owned": True},
    )
    report_resource(state, "runtime", json_output=json_output)


def _submit_runtime_template(
    client: TopClient,
    state: dict[str, Any],
    config: ExampleConfig,
    session_store_id: str,
    *,
    tool_id: str,
    json_output: bool,
) -> str:
    """发起 CreateRuntimeTemplate 并在首次取得 ID 时持久化。"""
    with wait_progress("准备 Runtime IAM Role", json_output=json_output):
        role_name, reused = ensure_runtime_role(
            config.control, config.runtime_role_name
        )
    emit(
        "resource",
        "Runtime IAM Role",
        json_output=json_output,
        heading=False,
        resource="Runtime IAM Role",
        name=role_name,
        status="reused" if reused else "created",
    )
    runtime_request = {
        "Name": state["names"]["runtime"],
        "Description": "Harness Infra resource-to-chat HTTP tutorial",
        "RoleName": role_name,
        "Resources": config.runtime_template.resources,
        "Meta": {"purpose": "resource-to-chat-tutorial"},
        "ClientToken": state["tokens"]["runtime_create"],
        "SessionStoreId": session_store_id,
    }
    if config.runtime_template.image_url is not None:
        runtime_request["ImageUrl"] = config.runtime_template.image_url
    if config.runtime_template.envs:
        runtime_request["Envs"] = config.runtime_template.envs
    if tool_id:
        runtime_request["Envs"] = {
            **config.runtime_template.envs,
            "MODEL_NAME": config.harness.model_id,
            "MODEL_API_BASE": config.harness.model_base_url,
            "SYSTEM_PROMPT": config.harness.system_prompt,
            "RUNTIME": "adk",
            "HARNESS_SANDBOX_TOOL_ID": tool_id,
        }
    if config.runtime_template.runtime:
        runtime_request["Runtime"] = config.runtime_template.runtime
    with wait_progress("创建 Runtime", json_output=json_output):
        runtime = client.call("CreateRuntimeTemplate", runtime_request)
    runtime_id = runtime.get("RuntimeId")
    if not isinstance(runtime_id, str) or not runtime_id:
        raise RuntimeError("CreateRuntimeTemplate response is missing RuntimeId")
    update_resource(
        state,
        "runtime",
        {
            "id": runtime_id,
            "name": runtime.get("Name") or state["names"]["runtime"],
            "parameters": {
                **config.runtime_template.resources,
                "ImageUrl": config.runtime_template.image_url,
                "Envs": dict.fromkeys(runtime_request.get("Envs", {}), "<redacted>"),
                "Runtime": config.runtime_template.runtime,
                "SessionStoreId": session_store_id,
            },
            "status": runtime.get("Status"),
            "owned": True,
        },
    )
    return runtime_id


def create_environment_api_key(
    client: TopClient,
    state: dict[str, Any],
    config: ExampleConfig,
    environment_id: str,
    *,
    json_output: bool = False,
    save_key: Callable[[str, str], None] | None = None,
) -> str:
    """为当前 Endpoint 和 Environment 签发 Key，仅在本地配置保存明文。"""
    recorded = state["resources"].get("api_key", {})
    if recorded.get("id"):
        if (
            config.environment.env_api_key_id == recorded["id"]
            and config.environment.env_api_key_value
            and recorded.get("status") == "active"
        ):
            report_resource(state, "api_key", json_output=json_output)
            return config.environment.env_api_key_value
        raise RuntimeError("Environment API Key 明文不可用，请先清理本轮资源")
    names = state["names"]
    tokens = state["tokens"]
    emit(
        "request",
        "创建 Environment API Key",
        json_output=json_output,
        step=6,
    )
    endpoint = state["resources"]["endpoint"]
    with wait_progress("创建 Environment API Key", json_output=json_output):
        key_result = client.call(
            "CreateAPIKey",
            {
                "Name": names["api_key"],
                "Description": "Environment key for resource-to-chat tutorial",
                "EnvironmentId": environment_id,
                "EndpointId": endpoint["id"],
                "ClientToken": tokens["api_key_create"],
            },
        )
    api_key_id = key_result.get("ApiKeyId")
    environment_key = key_result.get("Key")
    if not isinstance(api_key_id, str) or not api_key_id:
        raise RuntimeError("CreateAPIKey response is missing ApiKeyId")
    update_resource(
        state,
        "api_key",
        {
            "id": api_key_id,
            "name": key_result.get("Name") or names["api_key"],
            "status": "active",
            "owned": True,
        },
    )
    if not isinstance(environment_key, str) or not environment_key:
        raise RuntimeError(
            "CreateAPIKey did not return Key; run 03_cleanup_resources.py before retrying"
        )
    if save_key is None:
        persist_environment_api_key(
            api_key_id, environment_key, environment_type=config.environment.type
        )
    else:
        save_key(api_key_id, environment_key)
    report_resource(state, "api_key", json_output=json_output)
    return environment_key


def _finish_queue_resources(
    client: TopClient,
    state: dict[str, Any],
    config: ExampleConfig,
    environment_id: str,
    *,
    defer_session: bool,
    json_output: bool,
) -> dict[str, Any]:
    """兼容旧教程的一键资源和会话流程。"""
    environment_key = create_environment_api_key(
        client, state, config, environment_id, json_output=json_output
    )
    endpoint = state["resources"]["endpoint"]
    if defer_session:
        persist_session("", "", endpoint["base_url"])
        state["status"] = "control_plane_ready"
        save_state(state)
        return state

    create_queue_session(state, config, environment_key, json_output=json_output)
    report_resource(
        state,
        "session",
        json_output=json_output,
        result="Session 已就绪",
    )
    emit(
        "completed",
        (
            "资源和 Session 全部就绪"
            if config.environment.type == "Cloud"
            else "资源和 Session 创建完成，工具执行需接入自托管后端"
        ),
        json_output=json_output,
        resources=[
            resource_info(state, key, compact=True)
            for key in (
                "endpoint",
                "environment",
                "harness",
                "session_store",
                "runtime",
                "api_key",
                "session",
            )
        ],
        status=state["status"],
        next_step="python run.py run-sse",
    )
    if config.environment.type == "SelfHosted":
        connection = {
            "ANTHROPIC_BASE_URL": endpoint["base_url"],
            "ANTHROPIC_ENVIRONMENT_ID": environment_id,
            "ANTHROPIC_ENVIRONMENT_KEY": environment_key,
        }
        if json_output:
            print(
                json.dumps({"phase": "selfhost_connection", **connection}), flush=True
            )
        else:
            display_selfhost_connection(connection)
    return state


def create_queue_session(
    state: dict[str, Any],
    config: ExampleConfig,
    environment_key: str,
    *,
    json_output: bool = False,
    write_session: bool = True,
) -> str:
    """在 APIG 创建空会话；调用者可以先启动 Dispatcher 再提交首轮消息。"""
    resources = state["resources"]
    endpoint = resources["endpoint"]
    emit(
        "request",
        "创建 Session",
        json_output=json_output,
        step=7,
    )
    data = DataPlaneClient(endpoint["base_url"], environment_key)
    with wait_progress("创建 Session", json_output=json_output):
        session = data.call(
            "POST",
            "/v1/sessions",
            body={
                "agent": {"type": "agent", "id": resources["harness"]["id"]},
                "environment_id": resources["environment"]["id"],
                "workspace_id": state.get("workspace_id")
                or config.control.workspace_id,
                "runtime_id": resources["runtime"]["id"],
                "runtime_type": "agentkit_runtime",
                "title": config.session.title,
                "initial_events": [],
            },
            headers={
                "x-ark-key-name": config.model_api_key_name,
                "Idempotency-Key": state["tokens"]["session_create"],
            },
        )
    session_id = str(session.get("id") or "")
    if not session_id:
        raise RuntimeError("Create Session response is missing id")
    if session.get("ark_api_key_name") != config.model_api_key_name:
        raise RuntimeError("Session did not preserve ark_api_key_name")
    session_name = str(session.get("name") or "")
    update_resource(
        state,
        "session",
        {
            "id": session_id,
            "name": session_name,
            "title": session.get("title") or config.session.title,
            "parameters": {
                "runtime_type": "agentkit_runtime",
                "ark_api_key_name": config.model_api_key_name,
            },
            "status": session.get("status") or "active",
            "owned": True,
        },
    )
    if write_session:
        persist_session(session_id, session_name, endpoint["base_url"])
    state["status"] = "resources_ready"
    save_state(state)
    return session_id


def _extract_text(event: dict[str, Any]) -> str:
    content = event.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "".join(
        str(block.get("text") or "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def _delete_session(
    data: DataPlaneClient,
    session_id: str,
    *,
    json_output: bool,
) -> None:
    """归档并异步删除 Session，直到 Get 返回 404。"""

    with wait_progress("Session 删除完成", json_output=json_output):
        try:
            data.call("POST", f"/v1/sessions/{session_id}/archive")
        except HarnessInfraError as exc:
            if not _not_found(exc):
                raise
        try:
            data.call("DELETE", f"/v1/sessions/{session_id}")
        except HarnessInfraError as exc:
            if not _not_found(exc):
                raise
        deadline = time.monotonic() + 10 * 60
        last_status = "unknown"
        while time.monotonic() < deadline:
            try:
                observed = data.call("GET", f"/v1/sessions/{session_id}")
            except HarnessInfraError as exc:
                if _not_found(exc):
                    break
                raise
            last_status = observed.get("status") or "unknown"
            time.sleep(3)
        else:
            raise TimeoutError(
                f"等待 Session {session_id} 删除超时，最后状态：{last_status}。"
                "请保留本轮状态和 Environment API Key，以便重试清理。"
            )


def invoke_session(
    *,
    endpoint_base_url: str,
    environment_api_key: str,
    session_id: str,
    prompt: str,
    verify_sandbox_tools: bool = False,
    expected_substring: str = "",
    json_output: bool = False,
) -> str:
    """使用 YAML 中已创建的 Session 完成并校验一个智能体轮次。"""

    if not endpoint_base_url or not environment_api_key or not session_id:
        raise RuntimeError(
            "Session data is unavailable; run 01_create_resources.py first"
        )
    invocation_id = uuid.uuid4().hex
    event_id = f"event-send-{invocation_id}"
    data = DataPlaneClient(endpoint_base_url, environment_api_key)
    answer = ""
    turn_events: list[dict[str, Any]] = []
    emitted_tool_uses: set[str] = set()
    emit(
        "step",
        "HTTP 发起对话",
        json_output=json_output,
        step=1,
        id=session_id,
        prompt=prompt,
    )
    started_at = time.monotonic()
    with wait_progress("发送用户问题", json_output=json_output):
        sent = data.call(
            "POST",
            f"/v1/sessions/{session_id}/events",
            body={
                "events": [
                    {
                        "id": event_id,
                        "type": "user.message",
                        "content": [{"type": "text", "text": prompt}],
                    }
                ]
            },
        )
    events = sent.get("data")
    if not isinstance(events, list):
        raise TypeError("Send Events response is missing data[]")
    cursor = max(
        (
            int(event.get("sequence") or 0)
            for event in events
            if isinstance(event, dict)
        ),
        default=0,
    )
    if json_output:
        emit(
            "resource",
            "Session",
            json_output=True,
            id=session_id,
            parameters={"event_id": event_id, "event_type": "user.message"},
            prompt=prompt,
            result="问题已发送",
        )
    emit("step", "等待智能体回复", json_output=json_output, step=2)
    deadline = time.monotonic() + 5 * 60
    saw_answer = False
    turn_completed = False
    with wait_progress("HTTP 智能体回复", json_output=json_output):
        while time.monotonic() < deadline:
            page = data.call(
                "GET",
                f"/v1/sessions/{session_id}/events",
                params={
                    "after_sequence": cursor,
                    "limit": 100,
                    "order": "asc",
                },
            )
            new_events = page.get("data")
            if not isinstance(new_events, list):
                raise TypeError("List Events response is missing data[]")
            for event in new_events:
                if not isinstance(event, dict):
                    continue
                sequence = int(event.get("sequence") or 0)
                if sequence <= cursor:
                    continue
                cursor = sequence
                event_type = event.get("type")
                turn_events.append(event)
                tool_names = extract_tool_names(event)
                if json_output:
                    emit(
                        "event",
                        "收到持久化事件",
                        json_output=json_output,
                        sequence=sequence,
                        event_type=event_type,
                        tool_names=sorted(tool_names),
                    )
                if event_type in {"agent.error", "session.error"}:
                    raise RuntimeError(f"conversation failed: {event_type}")
                if event_type == "agent.message":
                    text = _extract_text(event)
                    if text:
                        answer = text
                        saw_answer = True
                if event_type == "session.status_idle":
                    stop = event.get("stop_reason")
                    stop = stop if isinstance(stop, dict) else {}
                    if saw_answer and stop.get("type") == "end_turn":
                        turn_completed = True
                        break
                    if stop.get("type") == "requires_action":
                        raise RuntimeError(
                            "conversation requires an unsupported client action"
                        )
            emit_tool_executions(
                turn_events,
                emitted_tool_uses,
                json_output=json_output,
            )
            if turn_completed:
                break
            time.sleep(2)
        else:
            raise TimeoutError("timed out waiting for agent.message and end_turn")
    successful_tools = emit_tool_executions(
        turn_events,
        emitted_tool_uses,
        json_output=json_output,
    )
    if verify_sandbox_tools:
        missing = missing_tool_names(successful_tools)
        if missing:
            raise RuntimeError(
                "sandbox tool-result validation failed; missing successful tools: "
                + ", ".join(missing)
            )
    if expected_substring and expected_substring not in answer:
        raise RuntimeError(
            "real conversation completed, but the final answer did not contain "
            f"{expected_substring!r}"
        )
    emit(
        "verified",
        "HTTP 对话校验通过",
        json_output=json_output,
        step=3,
        id=session_id,
        parameters={"stop_reason": "end_turn"},
        status="completed",
        prompt=prompt,
        answer=answer,
        tool_names=sorted(successful_tools),
        verification={
            "required_tools": list(REQUIRED_SANDBOX_TOOLS)
            if verify_sandbox_tools
            else [],
            "expected_substring": expected_substring,
            "stop_reason": "end_turn",
            "elapsed_seconds": round(time.monotonic() - started_at, 1),
        },
    )
    return answer


def _delete_top_and_wait_not_found(
    client: TopClient,
    *,
    delete_action: str,
    delete_body: dict[str, Any],
    get_action: str,
    get_body: dict[str, Any],
    description: str,
    json_output: bool,
) -> None:
    """删除控制面对象并用 Get 404 确认终态。"""

    with wait_progress(f"{description} 删除完成", json_output=json_output):
        try:
            client.call(delete_action, delete_body)
        except HarnessInfraError as exc:
            if not _not_found(exc):
                raise
        deadline = time.monotonic() + 15 * 60
        while time.monotonic() < deadline:
            try:
                client.call(get_action, get_body)
            except HarnessInfraError as exc:
                if _not_found(exc):
                    break
                raise
            time.sleep(5)
        else:
            raise TimeoutError(f"timed out waiting for {description} deletion")


def cleanup_resources(
    client: TopClient,
    state: dict[str, Any],
    *,
    environment_api_key: str = "",
    json_output: bool = False,
) -> None:
    """按引用关系回收模板、自动资源和环境，并归档 Harness。"""

    resources = state.get("resources")
    if not isinstance(resources, dict):
        raise TypeError("state resources are invalid")
    tokens = state["tokens"]

    emit("step", "检查 Session 并清理残留 API Key", json_output=json_output, step=1)
    session = resources.get("session") or {}
    api_key = resources.get("api_key") or {}
    report_resource(
        state, "session", json_output=json_output, result="检查 Session 状态"
    )
    if session.get("status") not in {None, "deleted"}:
        endpoint = resources.get("endpoint") or {}
        if not environment_api_key:
            raise RuntimeError(
                "Session is not deleted and its Environment API Key is unavailable"
            )
        if not session.get("id") or not endpoint.get("base_url"):
            raise RuntimeError(
                "Session cleanup requires its id and Endpoint base_url in state"
            )
        data = DataPlaneClient(endpoint["base_url"], environment_api_key)
        _delete_session(data, session["id"], json_output=json_output)
        update_resource(
            state,
            "session",
            {**session, "status": "deleted", "owned": True},
        )
        report_resource(
            state,
            "session",
            json_output=json_output,
            result="已通过 APIG 删除并确认会话不可再查询",
        )
    if api_key.get("status") not in {None, "deleted"}:
        try:
            with wait_progress("删除 Environment API Key", json_output=json_output):
                client.call(
                    "DeleteAPIKey",
                    {
                        "ApiKeyId": api_key["id"],
                        "ClientToken": tokens["api_key_delete"],
                    },
                )
        except HarnessInfraError as exc:
            if not _not_found(exc):
                raise

        update_resource(state, "api_key", {"status": "deleted"})
        report_resource(state, "api_key", json_output=json_output, result="已清理")
    else:
        report_resource(
            state, "api_key", json_output=json_output, result="无需清理，跳过"
        )

    emit("step", "归档 Deployment", json_output=json_output, step=2)
    deployment = resources.get("deployment") or {}
    if deployment.get("id") and deployment.get("status") != "archived":
        try:
            with wait_progress("归档 Deployment", json_output=json_output):
                client.call(
                    "ArchiveDeployment",
                    {"DeploymentId": deployment["id"]},
                )
        except HarnessInfraError as exc:
            if not _not_found(exc):
                raise
        update_resource(
            state,
            "deployment",
            {**deployment, "status": "archived"},
        )
        report_resource(state, "deployment", json_output=json_output, result="已归档")
    else:
        report_resource(
            state, "deployment", json_output=json_output, result="不存在或已归档，跳过"
        )

    emit("step", "删除 Runtime", json_output=json_output, step=3)

    runtime = resources.get("runtime") or {}
    if runtime.get("id") and runtime.get("status") != "deleted":
        _delete_top_and_wait_not_found(
            client,
            delete_action="DeleteRuntime",
            delete_body={
                "RuntimeId": runtime["id"],
                "ClientToken": tokens["runtime_delete"],
            },
            get_action="GetRuntime",
            get_body={"RuntimeId": runtime["id"]},
            description="Runtime",
            json_output=json_output,
        )
        update_resource(
            state,
            "runtime",
            {**runtime, "status": "deleted"},
        )
        report_resource(state, "runtime", json_output=json_output, result="已删除")
    else:
        report_resource(
            state,
            "runtime",
            json_output=json_output,
            result="不存在或已删除，跳过",
        )

    emit("step", "删除 SessionStore", json_output=json_output, step=4)
    session_store = resources.get("session_store") or {}
    if session_store.get("id") and session_store.get("status") != "deleted":
        _delete_top_and_wait_not_found(
            client,
            delete_action="DeleteSessionStore",
            delete_body={"SessionStoreId": session_store["id"]},
            get_action="GetSessionStore",
            get_body={"SessionStoreId": session_store["id"]},
            description="SessionStore",
            json_output=json_output,
        )
        update_resource(
            state,
            "session_store",
            {**session_store, "status": "deleted"},
        )
        report_resource(
            state, "session_store", json_output=json_output, result="已删除"
        )
    else:
        report_resource(
            state,
            "session_store",
            json_output=json_output,
            result="不存在或已删除，跳过",
        )

    resource = resources.get("environment_resource") or {}
    if resource.get("id") and resource.get("status") != "Deleted":

        def read_cloud_resource() -> dict[str, Any]:
            """资源已不存在也视为回收完成，以便恢复中断的清理。"""
            try:
                return client.call(
                    "GetEnvironmentResource", {"ResourceId": resource["id"]}
                )
            except HarnessInfraError as exc:
                if not _not_found(exc):
                    raise
                return {"Status": "Deleted"}

        try:
            with wait_progress("清理 Cloud Sandbox", json_output=json_output):
                client.call(
                    "DeleteEnvironmentResource",
                    {
                        "ResourceId": resource["id"],
                        "ClientToken": tokens["resource_delete"],
                    },
                )
        except HarnessInfraError as exc:
            if not _not_found(exc):
                raise
        deleted = wait_until(
            read_cloud_resource,
            lambda value: value.get("Status") == "Deleted",
            lambda value: (
                str(value.get("ErrorCode") or value.get("Status"))
                if value.get("Status") in {"Failed", "DeleteFailed"}
                or value.get("ErrorCode")
                else None
            ),
            description="Cloud Sandbox Deleted",
            json_output=json_output,
            report_result=False,
        )
        update_resource(
            state,
            "environment_resource",
            {
                **resource,
                "status": deleted.get("Status"),
                "revision": deleted.get("Revision"),
            },
        )

    emit("step", "删除 Environment", json_output=json_output, step=5)
    environment = resources.get("environment") or {}
    if environment.get("id") and environment.get("status") != "deleted":
        _delete_top_and_wait_not_found(
            client,
            delete_action="DeleteEnvironment",
            delete_body={
                "EnvironmentId": environment["id"],
                "ClientToken": tokens["environment_delete"],
            },
            get_action="GetEnvironment",
            get_body={"EnvironmentId": environment["id"]},
            description="Environment",
            json_output=json_output,
        )
        update_resource(
            state,
            "environment",
            {**environment, "status": "deleted"},
        )
        report_resource(state, "environment", json_output=json_output, result="已删除")
    else:
        report_resource(
            state, "environment", json_output=json_output, result="不存在或已删除，跳过"
        )

    emit("step", "归档 Harness", json_output=json_output, step=6)
    harness = resources.get("harness") or {}
    if harness.get("id") and harness.get("status") not in {"Archived", "not_found"}:
        try:
            with wait_progress("归档 Harness", json_output=json_output):
                archived = client.call(
                    "ArchiveHarness",
                    {
                        "HarnessId": harness["id"],
                        "ClientToken": tokens["harness_archive"],
                    },
                )
        except HarnessInfraError as exc:
            if not _not_found(exc):
                raise
            update_resource(state, "harness", {"status": "not_found"})
        else:
            update_resource(
                state,
                "harness",
                {
                    **harness,
                    "status": archived.get("Status"),
                },
            )
        report_resource(
            state, "harness", json_output=json_output, result="归档操作完成"
        )
    else:
        report_resource(
            state, "harness", json_output=json_output, result="不存在或已归档，跳过"
        )

    state["status"] = "cleaned"
    state["cleaned"] = True
    state["cleaned_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_state(state)
    emit(
        "completed",
        "本轮资源清理完成（保留 Endpoint）",
        json_output=json_output,
        step=6,
        resources=[
            {
                **resource_info(state, key, compact=True),
                **({"result": "保留"} if key == "endpoint" else {}),
            }
            for key in (
                "endpoint",
                "environment",
                "harness",
                "session_store",
                "runtime",
                "api_key",
                "session",
            )
        ],
        status=state["status"],
    )
