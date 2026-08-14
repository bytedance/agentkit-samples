import importlib
import os
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

SAMPLE_DIR = Path(__file__).resolve().parents[1]


@contextmanager
def sample_path():
    sys.path.insert(0, str(SAMPLE_DIR))
    try:
        yield
    finally:
        sys.path.remove(str(SAMPLE_DIR))


@contextmanager
def patched_env(values=None, absent=()):
    original = os.environ.copy()
    try:
        for key in absent:
            os.environ.pop(key, None)
        for key, value in (values or {}).items():
            os.environ[key] = value
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


def import_sample(module_name: str):
    for name in ("agent", "config", "guardrails", module_name):
        sys.modules.pop(name, None)
    with sample_path():
        return importlib.import_module(module_name)


class AgentContractTests(unittest.TestCase):
    def test_skill_space_ids_are_trimmed(self):
        with patched_env({"SKILL_SPACE_ID": " ss-primary , , ss-secondary "}):
            config = import_sample("config")

            self.assertEqual(
                config.configured_skill_space_ids(),
                ["ss-primary", "ss-secondary"],
            )

    def test_skill_sandbox_status_keeps_live_tool_hidden_by_default(self):
        with patched_env(
            {
                "AGENTKIT_TOOL_ID": "tool-skill-sandbox",
                "SKILL_SPACE_ID": "ss-primary",
            },
            absent=("EXPOSE_SKILL_SANDBOX_TO_AGENT",),
        ):
            config = import_sample("config")

            status = config.skill_sandbox_status()
            self.assertIs(status["ok"], True)
            self.assertEqual(status["data"]["tool_id_source"], "AGENTKIT_TOOL_ID")
            self.assertEqual(status["data"]["skill_space_ids"], ["ss-primary"])
            self.assertIs(status["data"]["exposed_to_agent"], False)
            self.assertIn("execute_skills", status["next_actions"][0])

    def test_skill_sandbox_uses_compatibility_tool_id_alias(self):
        with patched_env(
            {"AGENTKIT_TOOL_ID_SKILLS": "tool-legacy-skills"},
            absent=("AGENTKIT_TOOL_ID",),
        ):
            config = import_sample("config")

            self.assertEqual(
                config.resolve_skill_sandbox_tool_id(),
                ("tool-legacy-skills", "AGENTKIT_TOOL_ID_SKILLS"),
            )

    def test_placeholder_values_do_not_count_as_configured(self):
        with patched_env(
            {
                "AGENTKIT_TOOL_ID": "<your-skills-sandbox-tool-id>",
                "SKILL_SPACE_ID": "{{your_skill_space_id}}",
            }
        ):
            config = import_sample("config")

            status = config.skill_sandbox_status()
            self.assertIs(status["ok"], False)
            self.assertIs(status["data"]["tool_id_configured"], False)
            self.assertEqual(status["data"]["skill_space_ids"], [])

    def test_llm_shield_disabled_by_default(self):
        with patched_env(absent=("ENABLE_LLM_SHIELD", "TOOL_LLM_SHIELD_APP_ID")):
            guardrails = import_sample("guardrails")

            self.assertIsNone(guardrails.build_llm_shield_before_model_callback())

    def test_llm_shield_enabled_requires_app_id(self):
        with patched_env(
            {"ENABLE_LLM_SHIELD": "true"}, absent=("TOOL_LLM_SHIELD_APP_ID",)
        ):
            guardrails = import_sample("guardrails")

            with self.assertRaisesRegex(ValueError, "TOOL_LLM_SHIELD_APP_ID"):
                guardrails.build_llm_shield_before_model_callback()

    def test_llm_shield_placeholder_app_id_is_not_configured(self):
        with patched_env(
            {
                "ENABLE_LLM_SHIELD": "true",
                "TOOL_LLM_SHIELD_APP_ID": "<your-llm-shield-app-id>",
            }
        ):
            guardrails = import_sample("guardrails")

            self.assertIs(guardrails.llm_shield_status()["ok"], False)
            with self.assertRaisesRegex(ValueError, "TOOL_LLM_SHIELD_APP_ID"):
                guardrails.build_llm_shield_before_model_callback()

    def test_llm_shield_returns_builtin_callback_when_enabled(self):
        callback = object()
        llm_shield_module = ModuleType("veadk.tools.builtin_tools.llm_shield")
        llm_shield_module.content_safety = SimpleNamespace(
            before_model_callback=callback
        )

        with (
            patch.dict(
                sys.modules,
                {"veadk.tools.builtin_tools.llm_shield": llm_shield_module},
            ),
            patched_env(
                {
                    "ENABLE_LLM_SHIELD": "true",
                    "TOOL_LLM_SHIELD_APP_ID": "shield-app",
                }
            ),
        ):
            guardrails = import_sample("guardrails")

            self.assertIs(
                guardrails.build_llm_shield_before_model_callback(),
                callback,
            )

    def test_tools_include_execute_skills_only_when_explicitly_exposed(self):
        execute_skills = object()
        execute_skills_module = ModuleType("veadk.tools.builtin_tools.execute_skills")
        execute_skills_module.execute_skills = execute_skills

        with patch.dict(
            sys.modules,
            {"veadk.tools.builtin_tools.execute_skills": execute_skills_module},
        ):
            with patched_env(
                {
                    "AGENTKIT_TOOL_ID": "tool-skill-sandbox",
                    "SKILL_SPACE_ID": "ss-primary",
                    "ENABLE_SKILL_SANDBOX": "true",
                    "EXPOSE_SKILL_SANDBOX_TO_AGENT": "false",
                }
            ):
                agent = import_sample("agent")
                self.assertNotIn(execute_skills, agent.build_tools())

            with patched_env(
                {
                    "AGENTKIT_TOOL_ID": "tool-skill-sandbox",
                    "SKILL_SPACE_ID": "ss-primary",
                    "ENABLE_SKILL_SANDBOX": "true",
                    "EXPOSE_SKILL_SANDBOX_TO_AGENT": "true",
                }
            ):
                agent = import_sample("agent")
                self.assertIn(execute_skills, agent.build_tools())

    def test_agentkit_yaml_documents_runtime_contract_without_writeback_fields(self):
        yaml_text = (SAMPLE_DIR / "agentkit.yaml").read_text()

        for key in (
            "ENABLE_SKILL_SANDBOX",
            "EXPOSE_SKILL_SANDBOX_TO_AGENT",
            "AGENTKIT_TOOL_ID",
            "SKILL_SPACE_ID",
            "ENABLE_LLM_SHIELD",
            "TOOL_LLM_SHIELD_APP_ID",
        ):
            self.assertIn(key, yaml_text)

        for generated_key in (
            "runtime_apikey:",
            "runtime_endpoint:",
            "runtime_id:",
            "cr_image_full_url:",
            "pipeline_id:",
        ):
            self.assertNotIn(generated_key, yaml_text)


if __name__ == "__main__":
    unittest.main()
