"""验证部署恢复、配置隔离与连接凭据保护。"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import _backend as backend


class BackendTests(unittest.TestCase):
    """覆盖会触发重复创建或错误环境绑定的部署边界。"""

    def setUp(self) -> None:
        """为每个用例创建独立状态与无网络客户端。"""
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / ".sandbox_backend.json"
        self.environment = patch.dict(
            os.environ, {"HARNESS_INFRA_BACKEND_STATE": str(self.path)}
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.client = Mock()
        self.client.scope = "https://control/cn-beijing/agentkit/workspace/ws-1"
        self.client.config = SimpleNamespace(
            access_key="account-1", workspace_id="ws-1"
        )
        with patch.object(backend, "_read_yaml", return_value={}):
            self.options = backend.settings()
        self.conn = {
            "base_url": "https://example.com",
            "environment_id": "env-1",
            "environment_key": "private-example-value",
        }

    def test_runtime_mapping_and_redaction(self) -> None:
        """确认 Environment Key 注入 MA_API_KEY，脱敏计划不泄露其值。"""
        body = backend.runtime_request(
            self.options, self.conn, "cn-beijing", "tool-1", "token", "runtime"
        )
        env = {item["Key"]: item["Value"] for item in body["Envs"]}
        self.assertEqual(env["MA_API_KEY"], self.conn["environment_key"])
        self.assertEqual(env["MA_ENVIRONMENT_ID"], "env-1")
        self.assertEqual(env["AGENTKIT_TOOL_ID"], "tool-1")
        self.assertNotIn(
            self.conn["environment_key"], json.dumps(backend.public_request(body))
        )
        self.assertEqual(body["MinInstance"], 1)
        self.assertEqual(body["MaxInstance"], 1)

    def test_wait_failure_resumes_without_duplicate_create(self) -> None:
        """创建成功但等待超时时，持久化 ID，重跑不再次创建。"""
        state = backend.deployment_state(self.client, self.options)
        body = backend.tool_request(self.options, state["tokens"]["tool"], "tool")
        self.client.call.return_value = {"ToolId": "tool-1"}
        with patch.object(backend, "wait_until", side_effect=TimeoutError("timeout")):
            with self.assertRaises(TimeoutError):
                backend.ensure_resource(
                    self.client, state, "tool", body, json_output=True
                )
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved["resources"]["tool"]["id"], "tool-1")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.client.call.reset_mock()
        with patch.object(backend, "wait_until", return_value={"Status": "Ready"}):
            backend.ensure_resource(self.client, saved, "tool", body, json_output=True)
        self.client.call.assert_not_called()

    def test_same_token_after_ambiguous_create(self) -> None:
        """网络失败后复用首次已保存的 token，保证请求幂等。"""
        state = backend.deployment_state(self.client, self.options)
        body = backend.tool_request(self.options, state["tokens"]["tool"], "tool")
        self.client.call.side_effect = RuntimeError("network")
        with self.assertRaises(RuntimeError):
            backend.ensure_resource(self.client, state, "tool", body, json_output=True)
        recovered = backend.deployment_state(self.client, self.options)
        self.assertEqual(recovered["tokens"], state["tokens"])
        self.assertTrue(recovered["resources"]["tool"]["fingerprint"])

    def test_changed_account_or_project_rejected(self) -> None:
        """拒绝另一账号或项目复用同一部署状态。"""
        backend.deployment_state(self.client, self.options)
        self.client.config.access_key = "account-2"
        with self.assertRaisesRegex(RuntimeError, "scope changed"):
            backend.deployment_state(self.client, self.options)
        self.client.config.access_key = "account-1"
        with self.assertRaisesRegex(RuntimeError, "scope changed"):
            backend.deployment_state(
                self.client, {**self.options, "project_name": "other"}
            )

    def test_changed_environment_key_rejected(self) -> None:
        """环境或密钥变化时禁止静默复用旧 Dispatcher。"""
        state = backend.deployment_state(self.client, self.options)
        body = backend.runtime_request(
            self.options, self.conn, "cn-beijing", "tool-1", "token", "runtime"
        )
        state["resources"]["runtime"] = {
            "id": "runtime-1",
            "fingerprint": backend.hashlib.sha256(
                json.dumps(body, sort_keys=True).encode()
            ).hexdigest(),
        }
        changed = backend.runtime_request(
            self.options,
            {**self.conn, "environment_key": "rotated"},
            "cn-beijing",
            "tool-1",
            "token",
            "runtime",
        )
        with self.assertRaisesRegex(RuntimeError, "configuration changed"):
            backend.ensure_resource(
                self.client, state, "runtime", changed, json_output=True
            )
        self.client.call.assert_not_called()

    def test_partial_connection_rejected(self) -> None:
        """三项显式参数必须一起配置，避免与旧状态拼接。"""
        with patch.dict(
            os.environ, {"ANTHROPIC_BASE_URL": "https://example.com"}, clear=True
        ):
            with self.assertRaisesRegex(RuntimeError, "all three"):
                backend.connection(Mock(), self.options, dry_run=False)

    def test_cloud_environment_rejected(self) -> None:
        """即使有有效 Key，也不把 Cloud 环境接到此 Dispatcher。"""
        self.client.call.return_value = {
            "Status": "Active",
            "Config": {"Type": "Cloud"},
        }
        with self.assertRaisesRegex(RuntimeError, "Active SelfHosted"):
            backend.validate_connection(self.client, self.conn)

    def test_wrong_key_binding_rejected(self) -> None:
        """在创建后端前确认环境 Key 的数据面资源归属。"""
        self.client.call.return_value = {
            "Status": "Active",
            "Config": {"Type": "SelfHosted"},
            "WorkspaceId": "ws-1",
        }
        with patch.object(backend, "DataPlaneClient") as data:
            data.return_value.call.return_value = {
                "data": [{"environment_id": "another-env"}]
            }
            with self.assertRaisesRegex(RuntimeError, "does not match"):
                backend.validate_connection(self.client, self.conn)

    def test_dry_run_has_no_network_or_state_writes(self) -> None:
        """完整 dry-run 不构造网络客户端、不触碰部署状态。"""
        with (
            patch("sys.argv", ["02_create_dispatcher.py", "--dry-run", "--json"]),
            patch.object(
                backend,
                "validated_config",
                return_value=SimpleNamespace(
                    control=SimpleNamespace(region="cn-beijing"),
                    environment=SimpleNamespace(type="SelfHosted"),
                    session=SimpleNamespace(endpoint_base_url=""),
                ),
            ),
            patch.object(backend, "settings", return_value=self.options),
            patch.dict(os.environ, {}, clear=True),
            patch.object(backend, "TopClient") as client,
            patch.object(backend, "write_backend") as write,
        ):
            backend.main(dispatcher=True)
        client.assert_not_called()
        write.assert_not_called()
        self.assertFalse(self.path.exists())

    def test_reused_template_is_not_owned(self) -> None:
        """兼容模板仅查询并标记非自有，防止部署误删现有模板。"""
        state = backend.deployment_state(self.client, self.options)
        options = {**self.options, "existing_tool_id": "tool-existing"}
        self.client.call.return_value = {
            "ToolType": "Private",
            "Status": "Ready",
            "ImageUrl": options["sandbox_image"],
            "Command": options["sandbox_command"],
            "Port": options["sandbox_port"],
            "ProjectName": options["project_name"],
        }
        tool_id = backend.reuse_tool(self.client, state, options, json_output=True)
        self.assertEqual(tool_id, "tool-existing")
        self.client.call.assert_called_once_with("GetTool", {"ToolId": tool_id})
        self.assertFalse(state["resources"]["tool"]["owned"])

    def test_incompatible_reused_template_does_not_change_state(self) -> None:
        """错误镜像、端口或项目不可替代已验证的工具模板。"""
        state = backend.deployment_state(self.client, self.options)
        options = {**self.options, "existing_tool_id": "tool-existing"}
        self.client.call.return_value = {
            "ToolType": "Private",
            "Status": "Ready",
            "ImageUrl": "wrong-image",
            "Command": options["sandbox_command"],
            "Port": options["sandbox_port"],
            "ProjectName": options["project_name"],
        }
        with self.assertRaisesRegex(RuntimeError, "match image"):
            backend.reuse_tool(self.client, state, options, json_output=True)
        self.assertNotIn("tool", json.loads(self.path.read_text())["resources"])


if __name__ == "__main__":
    unittest.main()
