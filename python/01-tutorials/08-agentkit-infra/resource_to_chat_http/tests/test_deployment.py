"""Deployment 请求与 Run 状态的离线测试；不访问云资源。"""

from __future__ import annotations

import unittest
from typing import Any

from _deployment import (
    archive_deployment,
    deployment_spec,
    ensure_self_hosted_environment,
    list_runs,
    trigger_deployment,
    verify_run_session_events,
    wait_for_run,
)


class FakeClient:
    """只实现 Deployment 相关 Action 的假控制面。"""

    def __init__(self, responses: dict[str, dict[str, Any]] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, action: str, body: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((action, body))
        value = self.responses.get(action)
        if value is None:
            raise AssertionError(f"unexpected action {action}")
        return value


class DeploymentSpecTests(unittest.TestCase):
    def test_builds_cron_deployment_with_pinned_harness_and_text_event(self) -> None:
        body = deployment_spec(
            name="nightly-triage",
            harness_id="agent_123",
            harness_version=3,
            environment_id="env_123",
            runtime_id="r-123",
            ark_api_key_name="api-key-123",
            prompt="run bash",
            cron="* * * * *",
            timezone="Asia/Shanghai",
            metadata={"owner": "tutorial"},
        )
        self.assertEqual(body["Name"], "nightly-triage")
        self.assertEqual(body["HarnessId"], "agent_123")
        self.assertEqual(body["HarnessVersion"], 3)
        self.assertEqual(body["EnvironmentId"], "env_123")
        self.assertEqual(body["RuntimeId"], "r-123")
        self.assertEqual(body["ArkApiKeyName"], "api-key-123")
        self.assertEqual(body["Metadata"], {"owner": "tutorial"})
        self.assertEqual(
            body["InitialEvents"],
            [
                {
                    "type": "user.message",
                    "content": [{"type": "text", "text": "run bash"}],
                }
            ],
        )
        self.assertEqual(
            body["Schedule"],
            {
                "Type": "cron",
                "Expression": "* * * * *",
                "Timezone": "Asia/Shanghai",
            },
        )

    def test_no_schedule_keeps_manual_only_deployment(self) -> None:
        body = deployment_spec(
            name="manual-only",
            harness_id="agent_123",
            harness_version=None,
            environment_id="env_123",
            runtime_id="r-123",
            ark_api_key_name="api-key-123",
            prompt="hello",
            cron=None,
        )
        self.assertNotIn("Schedule", body)
        self.assertNotIn("HarnessVersion", body)

    def test_rejects_empty_name_or_prompt_before_network(self) -> None:
        with self.assertRaises(ValueError):
            deployment_spec(
                name=" ",
                harness_id="agent_123",
                harness_version=1,
                environment_id="env_123",
                runtime_id="r-123",
                ark_api_key_name="api-key-123",
                prompt="hello",
                cron=None,
            )
        with self.assertRaises(ValueError):
            deployment_spec(
                name="name",
                harness_id="agent_123",
                harness_version=1,
                environment_id="env_123",
                runtime_id="r-123",
                ark_api_key_name="api-key-123",
                prompt=" ",
                cron=None,
            )


class EnvironmentModeTests(unittest.TestCase):
    def test_accepts_pascal_and_snake_case_self_hosted(self) -> None:
        for config in ({"Type": "SelfHosted"}, {"type": "self_hosted"}):
            client = FakeClient(
                {"GetEnvironment": {"EnvironmentId": "env-1", "Config": config}}
            )
            ensure_self_hosted_environment(client, "env-1")
            self.assertEqual(
                client.calls, [("GetEnvironment", {"EnvironmentId": "env-1"})]
            )

    def test_rejects_cloud_and_archived_environments(self) -> None:
        client = FakeClient(
            {"GetEnvironment": {"EnvironmentId": "env-1", "Config": {"Type": "Cloud"}}}
        )
        with self.assertRaisesRegex(ValueError, "Cloud mode is not supported"):
            ensure_self_hosted_environment(client, "env-1")
        client = FakeClient(
            {
                "GetEnvironment": {
                    "EnvironmentId": "env-1",
                    "Config": {"Type": "SelfHosted"},
                    "ArchivedAt": "2026-11-19T00:00:00Z",
                }
            }
        )
        with self.assertRaisesRegex(ValueError, "archived"):
            ensure_self_hosted_environment(client, "env-1")


class DeploymentRunTests(unittest.TestCase):
    def test_trigger_and_wait_return_session(self) -> None:
        client = FakeClient(
            {
                "RunDeployment": {"DeploymentRunId": "deprun-1", "SessionId": "sesn-1"},
                "GetDeploymentRun": {
                    "DeploymentRunId": "deprun-1",
                    "SessionId": "sesn-1",
                },
            }
        )
        triggered = trigger_deployment(client, "dep-1")
        self.assertEqual(triggered["DeploymentRunId"], "deprun-1")
        result = wait_for_run(client, "deprun-1")
        self.assertEqual(result["SessionId"], "sesn-1")
        self.assertEqual(
            [call[0] for call in client.calls], ["RunDeployment", "GetDeploymentRun"]
        )

    def test_wait_raises_on_async_dispatch_error(self) -> None:
        client = FakeClient(
            {
                "GetDeploymentRun": {
                    "DeploymentRunId": "deprun-1",
                    "SessionId": "sesn-1",
                    "Error": {"Type": "dispatch_error", "Message": "run_sse failed"},
                }
            }
        )
        with self.assertRaisesRegex(RuntimeError, "dispatch_error"):
            wait_for_run(client, "deprun-1")

    def test_list_runs_and_archive_use_pascal_case_actions(self) -> None:
        client = FakeClient(
            {
                "ListDeploymentRuns": {"Items": [{"DeploymentRunId": "deprun-1"}]},
                "ArchiveDeployment": {
                    "DeploymentId": "dep-1",
                    "ArchivedAt": "2026-11-19T00:00:00Z",
                },
            }
        )
        items = list_runs(client, "dep-1", limit=20)
        self.assertEqual(items, [{"DeploymentRunId": "deprun-1"}])
        archived = archive_deployment(client, "dep-1")
        self.assertEqual(archived["ArchivedAt"], "2026-11-19T00:00:00Z")
        self.assertEqual(client.calls[0][0], "ListDeploymentRuns")
        self.assertEqual(client.calls[0][1]["DeploymentId"], "dep-1")
        self.assertEqual(
            client.calls[1], ("ArchiveDeployment", {"DeploymentId": "dep-1"})
        )

    def test_list_runs_validates_limit_before_network(self) -> None:
        client = FakeClient()
        with self.assertRaises(ValueError):
            list_runs(client, "dep-1", limit=0)
        self.assertEqual(client.calls, [])


class DeploymentSessionVerificationTests(unittest.TestCase):
    """验证只读 Session 事件验收，而非再次触发 Runtime 执行。"""

    @staticmethod
    def _successful_events() -> list[dict[str, Any]]:
        return [
            {
                "id": "message-1",
                "type": "user.message",
                "sequence": 1,
                "content": [{"type": "text", "text": "run bash"}],
            },
            {
                "id": "tool-use-1",
                "type": "agent.tool_use",
                "sequence": 2,
                "tool_use_id": "call-1",
                "name": "bash",
            },
            {
                "id": "tool-result-1",
                "type": "user.tool_result",
                "sequence": 3,
                "tool_use_id": "call-1",
                "content": [{"type": "text", "text": "DEPLOYMENT_OK"}],
                "is_error": False,
            },
            {
                "id": "answer-1",
                "type": "agent.message",
                "sequence": 4,
                "content": [{"type": "text", "text": "DEPLOYMENT_OK"}],
            },
            {
                "id": "idle-1",
                "type": "session.status_idle",
                "sequence": 5,
                "stop_reason": {"type": "end_turn"},
            },
        ]

    def test_accepts_complete_session_with_successful_required_tool(self) -> None:
        result = verify_run_session_events(
            self._successful_events(),
            expected_substring="DEPLOYMENT_OK",
            required_tools=("bash",),
        )
        self.assertEqual(result["answer"], "DEPLOYMENT_OK")
        self.assertEqual(result["tool_names"], ["bash"])
        self.assertEqual(result["end_turn_sequence"], 5)

    def test_rejects_tool_failure_or_missing_end_turn(self) -> None:
        failed = self._successful_events()
        failed[2]["is_error"] = True
        with self.assertRaisesRegex(RuntimeError, "tool call-1 failed"):
            verify_run_session_events(failed)

        incomplete = self._successful_events()[:-1]
        with self.assertRaisesRegex(RuntimeError, "did not reach end_turn"):
            verify_run_session_events(incomplete)

    def test_rejects_missing_expected_answer_or_required_tool(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "final answer did not contain"):
            verify_run_session_events(
                self._successful_events(), expected_substring="NOT_PRESENT"
            )
        with self.assertRaisesRegex(RuntimeError, "missing successful tools: read"):
            verify_run_session_events(
                self._successful_events(), required_tools=("bash", "read")
            )


if __name__ == "__main__":
    unittest.main()
