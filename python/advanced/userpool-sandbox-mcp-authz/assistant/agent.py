"""Experiment agent that delegates MCP work to AgentKit Skills Sandbox."""

from __future__ import annotations

import os
import threading
from typing import Any

from google.adk.tools import ToolContext
from veadk import Agent
from veadk.tools.builtin_tools.execute_skills import execute_skills


INBOUND_AUTH_CREDENTIAL_KEY = "inbound_auth"
LOCAL_INBOUND_AUTH_TOKEN_STATE_KEY = "_local_inbound_auth_token"
MCP_TIP_HEADER = "X-Ve-TIP-Token"
SKILL_SANDBOX_MCP_PROMPT_ENV = "SKILL_SANDBOX_MCP_PROMPT"
DEFAULT_SKILL_SANDBOX_MCP_PROMPT = """
You are running inside AgentKit Skills Sandbox for a User Pool identity experiment.

Use the MCP tools configured in this Skills Sandbox to satisfy the user request.
The calling Runtime has already forwarded the signed-in user's credential as the
inbound_auth request header. The Skills Sandbox runtime may use that credential
to prepare downstream MCP request authentication.

Do not reveal access tokens, TIP tokens, request headers, API keys, endpoint
secrets, or internal credential values. Return only the user-facing result from
the MCP tool call or a concise non-sensitive failure.

User request:
{user_request}
""".strip()

INSTRUCTION = """
You are a User Pool + Skills Sandbox MCP experiment assistant.

The user has already signed in through VeIdentity User Pool. When the user asks
to inspect, read, call, or operate an MCP resource, delegate the request to
Skills Sandbox. The Skills Sandbox already owns the MCP tool configuration.
Do not reveal access tokens, TIP tokens, request headers, or internal credential
details.

Runtime responsibilities:
1. The local Web UI captures the signed-in user's inbound Authorization bearer
   and stores it as ADK credential key inbound_auth before Skills Sandbox calls.
2. This Runtime agent delegates remote MCP work to Skills Sandbox with
   call_mcp_tool_via_skills_sandbox.
3. The Runtime agent does not read raw tokens, exchange tokens, or connect to
   MCP directly. Skills Sandbox owns MCP endpoint configuration and tool
   execution.
4. Report only user-facing outcomes, requested tool/resource names, and
   non-sensitive failure details.
""".strip()


def _env_present(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def _sandbox_prompt(user_request: str) -> str:
    template = (
        os.getenv(SKILL_SANDBOX_MCP_PROMPT_ENV, "").strip()
        or DEFAULT_SKILL_SANDBOX_MCP_PROMPT
    )
    if "{user_request}" in template:
        return template.format(user_request=user_request)
    return f"{template}\n\nUser request:\n{user_request}"


def _await_sync(awaitable):
    try:
        import asyncio

        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    result: dict[str, Any] = {}

    def run_in_thread() -> None:
        try:
            result["value"] = asyncio.run(awaitable)
        except BaseException as exc:  # noqa: BLE001
            result["error"] = exc

    thread = threading.Thread(target=run_in_thread)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")


def _state_value(tool_context: ToolContext, key: str) -> str | None:
    state = getattr(tool_context, "state", None)
    if not isinstance(state, dict):
        return None
    value = state.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _store_local_inbound_auth(tool_context: ToolContext) -> bool:
    """Store the local Web UI user token into ADK's credential service."""

    access_token = _state_value(tool_context, LOCAL_INBOUND_AUTH_TOKEN_STATE_KEY)
    if not access_token:
        return False

    invocation_context = getattr(tool_context, "_invocation_context", None)
    credential_service = getattr(invocation_context, "credential_service", None)
    set_credential = getattr(credential_service, "set_credential", None)
    app_name = getattr(invocation_context, "app_name", None)
    user_id = getattr(invocation_context, "user_id", None)
    if not callable(set_credential) or not app_name or not user_id:
        return False

    from veadk.utils.auth import build_auth_config

    auth_config = build_auth_config(
        token=access_token,
        auth_method="header",
        credential_key=INBOUND_AUTH_CREDENTIAL_KEY,
        header_scheme="bearer",
    )
    credential = getattr(auth_config, "exchanged_auth_credential", None)
    if credential is None:
        return False

    _await_sync(
        set_credential(
            app_name=app_name,
            user_id=user_id,
            credential_key=INBOUND_AUTH_CREDENTIAL_KEY,
            credential=credential,
        )
    )
    return True


def call_mcp_tool_via_skills_sandbox(
    user_request: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Delegate the user's MCP request to Skills Sandbox."""

    request = user_request.strip()
    if not request:
        return {
            "ok": False,
            "stage": "input_validation",
            "error": {
                "type": "ValueError",
                "message": "user_request must not be empty",
            },
        }

    workflow_prompt = _sandbox_prompt(request)
    local_inbound_auth_stored = _store_local_inbound_auth(tool_context)
    try:
        result = execute_skills(
            workflow_prompt=workflow_prompt,
            tool_context=tool_context,
            timeout=1800,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "stage": "execute_skills_mcp_experiment",
            "credential_key": INBOUND_AUTH_CREDENTIAL_KEY,
            "mcp_tip_header": MCP_TIP_HEADER,
            "skill_sandbox": {
                "uses_execute_skills": True,
                "runtime_mcp_env_required": False,
                "expected_mcp_owner": "Skills Sandbox",
            },
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }

    return {
        "ok": True,
        "stage": "execute_skills_mcp_experiment",
        "credential_key": INBOUND_AUTH_CREDENTIAL_KEY,
        "mcp_tip_header": MCP_TIP_HEADER,
        "inbound_auth_source": "local_webui_state_delta",
        "local_inbound_auth_stored": local_inbound_auth_stored,
        "prompt_source": (
            "env" if _env_present(SKILL_SANDBOX_MCP_PROMPT_ENV) else "default"
        ),
        "skill_sandbox": {
            "uses_execute_skills": True,
            "runtime_mcp_env_required": False,
            "expected_mcp_owner": "Skills Sandbox",
        },
        "result": result,
    }


root_agent = Agent(
    name="userpool_sandbox_mcp_authz",
    description=(
        "Experiment assistant for calling MCP tools through AgentKit Skills "
        "Sandbox with a VeIdentity User Pool login."
    ),
    instruction=INSTRUCTION,
    tools=[call_mcp_tool_via_skills_sandbox],
)
