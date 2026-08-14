import os
from typing import Any

from config import TRUE_VALUES, configured_value


def llm_shield_enabled() -> bool:
    return os.getenv("ENABLE_LLM_SHIELD", "false").strip().lower() in TRUE_VALUES


def llm_shield_status() -> dict[str, Any]:
    enabled = llm_shield_enabled()
    has_app_id = bool(configured_value("TOOL_LLM_SHIELD_APP_ID"))
    return {
        "ok": (not enabled) or has_app_id,
        "stage": "llm_shield_config",
        "data": {
            "enabled": enabled,
            "app_id_configured": has_app_id,
        },
        "warnings": []
        if (not enabled or has_app_id)
        else ["TOOL_LLM_SHIELD_APP_ID is required when ENABLE_LLM_SHIELD=true."],
        "next_actions": []
        if (not enabled or has_app_id)
        else ["Set TOOL_LLM_SHIELD_APP_ID or disable ENABLE_LLM_SHIELD."],
    }


def build_llm_shield_before_model_callback():
    if not llm_shield_enabled():
        return None
    if not configured_value("TOOL_LLM_SHIELD_APP_ID"):
        raise ValueError(
            "TOOL_LLM_SHIELD_APP_ID must be set when ENABLE_LLM_SHIELD=true"
        )

    from veadk.tools.builtin_tools.llm_shield import content_safety

    return content_safety.before_model_callback


def check_llm_shield() -> dict[str, Any]:
    return llm_shield_status()
