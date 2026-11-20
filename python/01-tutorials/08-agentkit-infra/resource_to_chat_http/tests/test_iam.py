"""验证 Dispatcher 所需的沙箱 Session 权限补齐。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import _iam
from _clients import ControlConfig, HarnessInfraError


def conflict(operation: str) -> HarnessInfraError:
    return HarnessInfraError(operation, "Conflict", "already exists", status_code=409)


class SandboxPolicyTests(unittest.TestCase):
    def test_creates_and_attaches_custom_policy(self) -> None:
        control = ControlConfig("", "", "cn-beijing", "agentkit", "open.volcengineapi.com")
        with patch.object(_iam, "IamClient") as factory:
            client = factory.return_value
            client.call.side_effect = [{}, {}]
            _iam.ensure_sandbox_role_policy(control, "role-1")
        self.assertEqual(
            [call.args[0] for call in client.call.call_args_list],
            ["CreatePolicy", "AttachRolePolicy"],
        )
        attach = client.call.call_args_list[1].args[1]
        self.assertEqual(attach["PolicyName"], _iam.SANDBOX_POLICY_NAME)
        self.assertEqual(attach["PolicyType"], "Custom")
        self.assertIn("agentkit:SetSessionTtl", _iam.SANDBOX_POLICY_DOCUMENT)
        self.assertIn("agentkit:DeleteSession", _iam.SANDBOX_POLICY_DOCUMENT)

    def test_existing_policy_and_attachment_are_idempotent(self) -> None:
        control = ControlConfig("", "", "cn-beijing", "agentkit", "open.volcengineapi.com")
        with patch.object(_iam, "IamClient") as factory:
            client = factory.return_value
            client.call.side_effect = [
                conflict("IAM CreatePolicy"),
                conflict("IAM AttachRolePolicy"),
            ]
            _iam.ensure_sandbox_role_policy(control, "role-1")
        self.assertEqual(client.call.call_count, 2)

    def test_non_conflict_errors_are_raised(self) -> None:
        control = ControlConfig("", "", "cn-beijing", "agentkit", "open.volcengineapi.com")
        error = HarnessInfraError("IAM CreatePolicy", "AccessDenied", "denied", status_code=403)
        with patch.object(_iam, "IamClient") as factory:
            client = factory.return_value
            client.call.side_effect = [error]
            with self.assertRaises(HarnessInfraError):
                _iam.ensure_sandbox_role_policy(control, "role-1")


if __name__ == "__main__":
    unittest.main()
