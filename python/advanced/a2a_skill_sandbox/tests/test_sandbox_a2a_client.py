from __future__ import annotations

import importlib.util
import io
import json
import sys
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock


SAMPLE_DIR = Path(__file__).resolve().parents[1]
CLIENT_SCRIPT = SAMPLE_DIR / "sandbox_a2a_client.py"


class AgentKitSandboxFakes:
    def __init__(self) -> None:
        self.ensure_sandbox_session = Mock(
            return_value={
                "endpoint": "https://sandbox.example",
                "session_id": "sandbox-session",
            }
        )
        self.send_message_nonblocking = Mock(
            return_value=types.SimpleNamespace(task_id="task-1")
        )
        self.poll_task_until_terminal = Mock(
            return_value={"task_ref": "sample-task", "status": "completed"}
        )
        self.task_output = Mock(
            return_value={
                "ok": True,
                "source": "a2a-skill-sandbox-sample",
                "content": "done",
            }
        )
        self.error_payload = Mock(
            side_effect=lambda exc: {
                "ok": False,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }
        )
        self.build_invoke_session_envs = Mock(
            return_value={
                "MODEL_AGENT_NAME": "doubao-test",
                "MODEL_AGENT_PROVIDER": "openai",
                "MODEL_AGENT_API_BASE": "https://ark.example/api/v3",
                "MODEL_AGENT_API_KEY": "test-key",
            }
        )

    def install(self) -> None:
        modules = {
            "agentkit": types.ModuleType("agentkit"),
            "agentkit.toolkit": types.ModuleType("agentkit.toolkit"),
            "agentkit.toolkit.cli": types.ModuleType("agentkit.toolkit.cli"),
            "agentkit.toolkit.cli.sandbox": types.ModuleType(
                "agentkit.toolkit.cli.sandbox"
            ),
        }

        a2a_client = types.ModuleType("agentkit.toolkit.cli.sandbox.a2a_client")
        a2a_client.DEFAULT_A2A_HISTORY_LENGTH = 3
        a2a_client.DEFAULT_A2A_PATH = "/a2a"
        a2a_client.DEFAULT_A2A_POLL_INTERVAL_SECONDS = 0.01
        a2a_client.DEFAULT_A2A_TIMEOUT_SECONDS = 120
        a2a_client.poll_task_until_terminal = self.poll_task_until_terminal
        a2a_client.send_message_nonblocking = self.send_message_nonblocking

        cli_invoke = types.ModuleType("agentkit.toolkit.cli.sandbox.cli_invoke")
        cli_invoke._error_payload = self.error_payload
        cli_invoke._task_output = self.task_output

        config_store = types.ModuleType("agentkit.toolkit.cli.sandbox.config_store")
        config_store.configured_sandbox_config = Mock(return_value={})
        config_store.config_default_str = Mock(return_value=None)

        env_config = types.ModuleType("agentkit.toolkit.cli.sandbox.env_config")
        env_config.build_invoke_session_envs = self.build_invoke_session_envs

        session_create = types.ModuleType("agentkit.toolkit.cli.sandbox.session_create")
        session_create.ensure_sandbox_session = self.ensure_sandbox_session

        tool_resolve = types.ModuleType("agentkit.toolkit.cli.sandbox.tool_resolve")
        tool_resolve.SandboxToolType = types.SimpleNamespace(
            SKILL_ENV=types.SimpleNamespace(value="SkillEnv")
        )

        modules.update(
            {
                a2a_client.__name__: a2a_client,
                cli_invoke.__name__: cli_invoke,
                config_store.__name__: config_store,
                env_config.__name__: env_config,
                session_create.__name__: session_create,
                tool_resolve.__name__: tool_resolve,
            }
        )
        sys.modules.update(modules)


def load_client_module():
    module_name = "a2a_skill_sandbox_client_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, CLIENT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {CLIENT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class SandboxA2AClientTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fakes = AgentKitSandboxFakes()
        self.fakes.install()
        self.client = load_client_module()

    def test_skill_profile_invokes_a2a_without_session_envs(self) -> None:
        output = self.client.invoke_sandbox_a2a(
            sandbox_profile="skill",
            tool_id="tool-123",
            session_id="session-123",
            prompt="  list skills  ",
        )

        self.assertTrue(output["ok"])
        self.fakes.ensure_sandbox_session.assert_called_once_with(
            session_id="session-123",
            tool_id="tool-123",
            tool_type="SkillEnv",
            envs=None,
            resolve_tool=False,
            include_tos_mount_points=False,
        )
        self.fakes.send_message_nonblocking.assert_called_once_with(
            endpoint="https://sandbox.example",
            prompt="list skills",
            a2a_path="/a2a",
            request_metadata={
                "session_id": "sandbox-session",
                "user_id": "agentkit-a2a-skill-sandbox",
            },
            history_length=3,
            timeout=60,
        )
        self.fakes.poll_task_until_terminal.assert_called_once_with(
            endpoint="https://sandbox.example",
            task_id="task-1",
            a2a_path="/a2a",
            history_length=3,
            timeout=120,
            interval=0.01,
        )

    def test_skill_env_profile_injects_model_agent_envs(self) -> None:
        self.client.invoke_sandbox_a2a(
            sandbox_profile="skill-env",
            tool_id="tool-123",
            session_id="session-123",
            prompt="hello",
            model_name="doubao-test",
            model_provider="openai",
            model_base_url="https://ark.example/api/v3",
            model_api_key="test-key",
        )

        call_kwargs = self.fakes.ensure_sandbox_session.call_args.kwargs
        self.assertEqual(
            {
                "MODEL_AGENT_NAME": "doubao-test",
                "MODEL_AGENT_PROVIDER": "openai",
                "MODEL_AGENT_API_BASE": "https://ark.example/api/v3",
                "MODEL_AGENT_API_KEY": "test-key",
            },
            call_kwargs["envs"],
        )
        self.fakes.build_invoke_session_envs.assert_called_once_with(
            model_name="doubao-test",
            model_provider="openai",
            model_base_url="https://ark.example/api/v3",
            model_api_key="test-key",
        )

    def test_model_args_are_rejected_for_skill_profile(self) -> None:
        with self.assertRaisesRegex(ValueError, "--model-name"):
            self.client.invoke_sandbox_a2a(
                sandbox_profile="skill",
                tool_id="tool-123",
                session_id="session-123",
                prompt="hello",
                model_name="doubao-test",
            )

    def test_main_returns_json_error_for_empty_prompt(self) -> None:
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = self.client.main(
                [
                    "--tool-id",
                    "tool-123",
                    "--session-id",
                    "session-123",
                    "--prompt",
                    "   ",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(1, exit_code)
        self.assertFalse(payload["ok"])
        self.assertEqual("ValueError", payload["error"]["type"])
        self.fakes.ensure_sandbox_session.assert_not_called()

    def test_main_prints_success_payload(self) -> None:
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = self.client.main(
                [
                    "--tool-id",
                    "tool-123",
                    "--session-id",
                    "session-123",
                    "--prompt",
                    "hello",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, exit_code)
        self.assertTrue(payload["ok"])
        self.assertEqual("a2a-skill-sandbox-sample", payload["source"])


if __name__ == "__main__":
    unittest.main()
