"""从控制面资源创建到数据面对话及回收的确定性工作流。"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from _clients import DataPlaneClient, HarnessInfraError, TopClient
from _common import (
    emit,
    report_resource,
    resource_info,
    save_state,
    update_resource,
    wait_progress,
    wait_until,
)
from _config import ExampleConfig, persist_environment_api_key, persist_session
from _curl import configure_session_curl_scripts
from _iam import ensure_runtime_role

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
    json_output: bool,
) -> dict[str, Any]:
    """复用唯一 Ready Endpoint；无 Endpoint 时同步创建。"""

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
        with wait_progress("创建 Endpoint", json_output=json_output):
            endpoint = client.call("CreateEndpoint", {})
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
    with wait_progress("创建 SessionStore", json_output=json_output):
        created = client.call("CreateSessionStore", request)
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


def create_resources(
    client: TopClient,
    state: dict[str, Any],
    config: ExampleConfig,
    *,
    endpoint_id: str = "",
    json_output: bool = False,
) -> dict[str, Any]:
    """创建控制面资源、数据面凭据和 Session，并等待异步资源就绪。"""

    emit("step", "准备 Endpoint", json_output=json_output, step=1)
    _prepare_endpoint(
        client,
        state,
        endpoint_id=endpoint_id,
        json_output=json_output,
    )
    names = state["names"]
    tokens = state["tokens"]
    environment_config = {
        "Type": config.environment.type,
        "Resources": config.environment.resources,
    }

    emit(
        "request",
        "创建 Cloud Environment",
        json_output=json_output,
        step=2,
    )
    with wait_progress("创建 Cloud Environment", json_output=json_output):
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
    update_resource(
        state,
        "environment",
        {
            "id": environment_id,
            "name": environment.get("Name") or names["environment"],
            "parameters": environment_config,
            "status": environment.get("Status"),
            "owned": True,
        },
    )
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
        result="Cloud Sandbox 已就绪",
    )

    emit(
        "request",
        "创建 Harness",
        json_output=json_output,
        step=3,
    )
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

    emit(
        "request",
        "创建 SessionStore",
        json_output=json_output,
        step=4,
    )
    session_store = _create_session_store(
        client,
        state,
        config,
        json_output=json_output,
    )

    emit(
        "request",
        "创建 RuntimeTemplate",
        json_output=json_output,
        step=5,
    )
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
        "Name": names["runtime_template"],
        "Description": "Harness Infra resource-to-chat HTTP tutorial",
        "RoleName": role_name,
        "Resources": config.runtime_template.resources,
        "Meta": {"purpose": "resource-to-chat-tutorial"},
        "ClientToken": tokens["runtime_create"],
        "SessionStoreId": session_store["SessionStoreId"],
    }
    if config.runtime_template.image_url is not None:
        runtime_request["ImageUrl"] = config.runtime_template.image_url
    if config.runtime_template.envs:
        runtime_request["Envs"] = config.runtime_template.envs
    if config.runtime_template.runtime:
        runtime_request["Runtime"] = config.runtime_template.runtime
    with wait_progress("创建 RuntimeTemplate", json_output=json_output):
        runtime = client.call("CreateRuntimeTemplate", runtime_request)
    runtime_id = runtime.get("RuntimeTemplateId")
    if not isinstance(runtime_id, str) or not runtime_id:
        raise RuntimeError(
            "CreateRuntimeTemplate response is missing RuntimeTemplateId"
        )
    update_resource(
        state,
        "runtime_template",
        {
            "id": runtime_id,
            "name": runtime.get("Name") or names["runtime_template"],
            "parameters": {
                **config.runtime_template.resources,
                "ImageUrl": config.runtime_template.image_url,
                "Envs": config.runtime_template.envs,
                "Runtime": config.runtime_template.runtime,
                "SessionStoreId": session_store["SessionStoreId"],
            },
            "status": runtime.get("Status"),
            "owned": True,
        },
    )
    runtime = wait_until(
        lambda: client.call("GetRuntimeTemplate", {"RuntimeTemplateId": runtime_id}),
        lambda value: value.get("Status") == "Ready",
        lambda value: (
            str(value.get("Status")) if value.get("Status") == "Failed" else None
        ),
        description="RuntimeTemplate Ready",
        json_output=json_output,
        report_result=False,
    )
    update_resource(
        state,
        "runtime_template",
        {"id": runtime_id, "status": "Ready", "owned": True},
    )
    report_resource(state, "runtime_template", json_output=json_output)

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
    persist_environment_api_key(api_key_id, environment_key)
    report_resource(state, "api_key", json_output=json_output)

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
                "agent": {"type": "agent", "id": harness_id},
                "environment_id": environment_id,
                "runtime_template_id": runtime_id,
                "runtime_type": "agentkit_runtime",
                "title": config.session.title,
                "initial_events": [],
            },
            headers={
                "x-ark-key-name": config.model_api_key_name,
                "Idempotency-Key": tokens["session_create"],
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
            "status": session.get("status"),
            "owned": True,
        },
    )
    persist_session(session_id, session_name, endpoint["base_url"])
    invoke_path, sse_path = configure_session_curl_scripts()
    report_resource(
        state,
        "session",
        json_output=json_output,
        result=f"已回填 curl 脚本配置：{invoke_path}、{sse_path}",
    )

    state["status"] = "resources_ready"
    save_state(state)
    emit(
        "completed",
        "资源和 Session 全部就绪",
        json_output=json_output,
        resources=[
            resource_info(state, key, compact=True)
            for key in (
                "endpoint",
                "environment",
                "harness",
                "session_store",
                "runtime_template",
                "api_key",
                "session",
            )
        ],
        status=state["status"],
        next_step="python 02_invoke_session_http.py",
    )
    return state


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
        while time.monotonic() < deadline:
            try:
                data.call("GET", f"/v1/sessions/{session_id}")
            except HarnessInfraError as exc:
                if _not_found(exc):
                    break
                raise
            time.sleep(3)
        else:
            raise TimeoutError("timed out waiting for Session deletion")


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
                "Session is not deleted and config.yaml has no Environment API Key"
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
            result="使用 config.yaml 中的 Environment API Key 删除",
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

    emit("step", "删除 RuntimeTemplate", json_output=json_output, step=2)
    runtime = resources.get("runtime_template") or {}
    if runtime.get("id") and runtime.get("status") != "deleted":
        _delete_top_and_wait_not_found(
            client,
            delete_action="DeleteRuntimeTemplate",
            delete_body={
                "RuntimeTemplateId": runtime["id"],
                "Reason": "Resource-to-chat tutorial cleanup",
                "ClientToken": tokens["runtime_delete"],
            },
            get_action="GetRuntimeTemplate",
            get_body={"RuntimeTemplateId": runtime["id"]},
            description="RuntimeTemplate",
            json_output=json_output,
        )
        update_resource(
            state,
            "runtime_template",
            {**runtime, "status": "deleted"},
        )
        report_resource(
            state, "runtime_template", json_output=json_output, result="已删除"
        )
    else:
        report_resource(
            state,
            "runtime_template",
            json_output=json_output,
            result="不存在或已删除，跳过",
        )

    emit("step", "删除 SessionStore", json_output=json_output, step=3)
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
            lambda: client.call(
                "GetEnvironmentResource", {"ResourceId": resource["id"]}
            ),
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

    emit("step", "删除 Environment", json_output=json_output, step=4)
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

    emit("step", "归档 Harness", json_output=json_output, step=5)
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
                "runtime_template",
                "api_key",
                "session",
            )
        ],
        status=state["status"],
    )
