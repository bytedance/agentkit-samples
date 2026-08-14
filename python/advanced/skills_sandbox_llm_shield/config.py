from __future__ import annotations

import os
from typing import Any

TRUE_VALUES = {"1", "true", "yes", "on"}


def configured_value(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or value.startswith(("<", "{{")):
        return ""
    return value


def env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in TRUE_VALUES


def configured_skill_space_ids() -> list[str]:
    return [
        item.strip()
        for item in os.getenv("SKILL_SPACE_ID", "").split(",")
        if item.strip() and not item.strip().startswith(("<", "{{"))
    ]


def resolve_skill_sandbox_tool_id() -> tuple[str | None, str | None]:
    for env_name in ("AGENTKIT_TOOL_ID", "AGENTKIT_TOOL_ID_SKILLS"):
        value = configured_value(env_name)
        if value:
            return value, env_name
    return None, None


def skill_sandbox_status() -> dict[str, Any]:
    tool_id, source = resolve_skill_sandbox_tool_id()
    skill_space_ids = configured_skill_space_ids()
    enabled = env_flag("ENABLE_SKILL_SANDBOX", False)
    exposed = env_flag("EXPOSE_SKILL_SANDBOX_TO_AGENT", False)
    ready = bool(tool_id and skill_space_ids)

    warnings: list[str] = []
    next_actions: list[str] = []
    if not tool_id:
        warnings.append("AGENTKIT_TOOL_ID is not configured.")
        next_actions.append("Bind a Skills Sandbox Tool to the AgentKit Runtime.")
    if not skill_space_ids:
        warnings.append("SKILL_SPACE_ID is not configured.")
        next_actions.append(
            "Set SKILL_SPACE_ID to the Skills space that contains published Skills."
        )
    if ready and not exposed:
        next_actions.append(
            "Set ENABLE_SKILL_SANDBOX=true and EXPOSE_SKILL_SANDBOX_TO_AGENT=true "
            "to expose execute_skills to the Agent."
        )

    return {
        "ok": ready,
        "stage": "skill_sandbox_config",
        "data": {
            "enabled": enabled,
            "exposed_to_agent": enabled and exposed,
            "tool_id_configured": bool(tool_id),
            "tool_id_source": source,
            "skill_space_ids": skill_space_ids,
        },
        "warnings": warnings,
        "next_actions": next_actions,
    }


def should_expose_skill_sandbox() -> bool:
    status = skill_sandbox_status()
    return bool(
        status["ok"]
        and status["data"]["enabled"]
        and status["data"]["exposed_to_agent"]
    )
