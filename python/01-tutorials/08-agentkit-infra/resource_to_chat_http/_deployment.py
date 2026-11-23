"""Deployment / DeploymentRun 控制面请求、轮询及事件验收。"""

from __future__ import annotations

from typing import Any

from _clients import TopClient
from _common import wait_until


def deployment_spec(
    *,
    name: str,
    harness_id: str,
    harness_version: int | None,
    environment_id: str,
    runtime_id: str,
    ark_api_key_name: str,
    prompt: str,
    cron: str | None,
    timezone: str = "Asia/Shanghai",
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    """构造 CreateDeployment 请求；每次触发都由服务端创建新 Session。"""

    if not name.strip():
        raise ValueError("deployment name is required")
    if not prompt.strip():
        raise ValueError("deployment prompt is required")
    body: dict[str, Any] = {
        "Name": name,
        "HarnessId": harness_id,
        "EnvironmentId": environment_id,
        "RuntimeId": runtime_id,
        "ArkApiKeyName": ark_api_key_name,
        "InitialEvents": [
            {
                "type": "user.message",
                "content": [{"type": "text", "text": prompt}],
            }
        ],
        "Metadata": metadata or {},
    }
    if harness_version is not None:
        body["HarnessVersion"] = harness_version
    if cron:
        body["Schedule"] = {
            "Type": "cron",
            "Expression": cron,
            "Timezone": timezone,
        }
    return body


def ensure_self_hosted_environment(client: TopClient, environment_id: str) -> None:
    """CLI/samples 只支持 SelfHosted Environment；Cloud 模式直接拒绝。"""

    if not environment_id.strip():
        raise ValueError("environment id is required")
    value = client.call("GetEnvironment", {"EnvironmentId": environment_id})
    config = value.get("Config") or value.get("config") or {}
    if not isinstance(config, dict):
        config = {}
    kind = (
        str(config.get("Type") or config.get("type") or "")
        .strip()
        .lower()
        .replace("_", "")
    )
    if kind != "selfhosted":
        raise ValueError(
            f"Deployment Cloud mode is not supported: Environment {environment_id} must be SelfHosted"
        )
    if value.get("ArchivedAt") or value.get("archived_at"):
        raise ValueError(f"Environment {environment_id} is archived")


def create_deployment(client: TopClient, body: dict[str, Any]) -> dict[str, Any]:
    """CreateDeployment；返回 Deployment 对象。"""

    return client.call("CreateDeployment", body)


def trigger_deployment(client: TopClient, deployment_id: str) -> dict[str, Any]:
    """RunDeployment；每次手动触发都会创建新的 Session 和 Run。"""

    return client.call("RunDeployment", {"DeploymentId": deployment_id})


def wait_for_run(
    client: TopClient,
    run_id: str,
    *,
    json_output: bool = False,
) -> dict[str, Any]:
    """等待 Run 写入 SessionId 或 Error。

    Run 创建成功不等于执行成功；必须检查 Error。
    """

    def failed(value: dict[str, Any]) -> str | None:
        error = value.get("Error")
        if isinstance(error, dict):
            kind = str(error.get("Type") or error.get("type") or "error")
            message = str(error.get("Message") or error.get("message") or "")
            return f"{kind}: {message}"
        return None

    return wait_until(
        lambda: client.call("GetDeploymentRun", {"DeploymentRunId": run_id}),
        lambda value: bool(value.get("SessionId") or value.get("Error")),
        failed,
        description=f"DeploymentRun {run_id}",
        json_output=json_output,
    )


def list_runs(
    client: TopClient,
    deployment_id: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """列出某个 Deployment 的 Run，按服务端创建时间倒序。"""

    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    result = client.call(
        "ListDeploymentRuns",
        {"DeploymentId": deployment_id, "MaxResults": limit},
    )
    items = result.get("Items")
    if not isinstance(items, list):
        raise RuntimeError("ListDeploymentRuns returned no Items")
    return [item for item in items if isinstance(item, dict)]


def archive_deployment(client: TopClient, deployment_id: str) -> dict[str, Any]:
    """ArchiveDeployment；归档不可恢复，归档后不能再触发。"""

    return client.call("ArchiveDeployment", {"DeploymentId": deployment_id})


def _event_text(event: dict[str, Any]) -> str:
    """提取 AgentKit 文本内容块，兼容字符串和文本块数组。"""

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


def _tool_name(event: dict[str, Any]) -> str:
    """读取原生工具调用名称；未知结构保留空值而非猜测。"""

    for key in ("name", "tool_name", "function_name"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value.lower()
    return ""


def _tool_reference(event: dict[str, Any]) -> str:
    """读取工具调用或结果关联 ID，兼容自定义与 MCP 事件。"""

    for key in ("tool_use_id", "custom_tool_use_id", "mcp_tool_use_id", "id"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _tool_result_failed(event: dict[str, Any]) -> bool:
    """递归检查工具结果是否包含明确失败标记。"""

    def contains_error(value: Any) -> bool:
        if isinstance(value, dict):
            if value.get("is_error") is True:
                return True
            return any(contains_error(item) for item in value.values())
        if isinstance(value, list):
            return any(contains_error(item) for item in value)
        return False

    return contains_error(event)


def verify_run_session_events(
    events: list[dict[str, Any]],
    *,
    expected_substring: str = "",
    required_tools: tuple[str, ...] = (),
) -> dict[str, Any]:
    """验证已派发 Deployment Session 的完成事件，不发送任何新消息。

    验收要求是最终 agent.message 先出现，随后收到
    session.status_idle/end_turn；每个工具调用至少有一个非失败结果。
    """

    ordered = sorted(events, key=lambda item: int(item.get("sequence") or 0))
    tool_uses: dict[str, str] = {}
    tool_results: dict[str, list[dict[str, Any]]] = {}
    answer = ""
    answer_sequence = 0
    end_turn_sequence = 0

    for event in ordered:
        event_type = str(event.get("type") or "")
        sequence = int(event.get("sequence") or 0)
        if event_type in {"agent.error", "session.error"}:
            raise RuntimeError(f"Deployment Session failed: {event_type}")
        if event_type in {
            "agent.tool_use",
            "agent.custom_tool_use",
            "agent.mcp_tool_use",
        }:
            reference = _tool_reference(event)
            if reference:
                tool_uses[reference] = _tool_name(event)
        elif event_type in {
            "user.tool_result",
            "agent.tool_result",
            "user.custom_tool_result",
            "agent.mcp_tool_result",
        }:
            reference = _tool_reference(event)
            if reference:
                tool_results.setdefault(reference, []).append(event)
        elif event_type == "agent.message":
            text = _event_text(event)
            if text:
                answer = text
                answer_sequence = sequence
        elif event_type == "session.status_idle":
            stop_reason = event.get("stop_reason")
            if (
                isinstance(stop_reason, dict)
                and stop_reason.get("type") == "end_turn"
                and answer_sequence
                and sequence > answer_sequence
            ):
                end_turn_sequence = sequence

    if not answer:
        raise RuntimeError("Deployment Session produced no agent.message")
    if not end_turn_sequence:
        raise RuntimeError(
            "Deployment Session did not reach end_turn after agent.message"
        )
    if expected_substring and expected_substring not in answer:
        raise RuntimeError(
            f"Deployment Session final answer did not contain {expected_substring!r}"
        )

    successful_tools: set[str] = set()
    for reference, name in tool_uses.items():
        results = tool_results.get(reference, [])
        if not results:
            raise RuntimeError(f"Deployment Session tool {reference} has no result")
        if all(_tool_result_failed(result) for result in results):
            raise RuntimeError(f"Deployment Session tool {reference} failed")
        if name:
            successful_tools.add(name)

    missing = sorted(set(required_tools) - successful_tools)
    if missing:
        raise RuntimeError(
            "Deployment Session is missing successful tools: " + ", ".join(missing)
        )

    return {
        "answer": answer,
        "answer_sequence": answer_sequence,
        "end_turn_sequence": end_turn_sequence,
        "stop_reason": "end_turn",
        "tool_names": sorted(successful_tools),
        "event_count": len(ordered),
    }
