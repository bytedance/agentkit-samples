"""Workspace 选择、范围隔离及真实传输边界的离线回归。"""

import sys
import json
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _clients import ControlConfig, TopClient, workspace_body, WORKSPACE_ACTIONS


class WorkspaceTests(unittest.TestCase):
    def test_selector_conflicts_fail_before_transport(self):
        client = TopClient(
            ControlConfig(
                "ak", "sk", "cn-beijing", "agentkit", "example.com", workspace_id="ws-1"
            )
        )
        with mock.patch("_clients.requests.post") as post:
            for body in [
                {"WorkspaceId": "ws-2"},
                {"WorkspaceId": None},
                {"WorkspaceId": "ws-1", "workspace_id": ""},
            ]:
                with self.assertRaises((ValueError, TypeError)):
                    client.call("GetHarness", body)
            post.assert_not_called()

    def test_only_supported_actions_are_scoped_and_body_is_not_mutated(self):
        self.assertEqual(len(WORKSPACE_ACTIONS), 18)
        for action in WORKSPACE_ACTIONS:
            self.assertEqual(
                workspace_body(action, {}, "ws-1"), {"WorkspaceId": "ws-1"}
            )
        for action in [
            "CreateEndpoint",
            "CreateAPIKey",
            "CreateSessionStore",
            "UpdateHarness",
            "DeleteRuntimeTemplate",
        ]:
            self.assertEqual(workspace_body(action, {}, "ws-1"), {})
        body = {"workspace_id": " ws-1 "}
        self.assertEqual(
            workspace_body("GetHarness", body, "ws-1"), {"WorkspaceId": "ws-1"}
        )
        self.assertEqual(body, {"workspace_id": " ws-1 "})

    def test_scope_and_signed_payload_include_workspace(self):
        cfg = ControlConfig(
            "ak", "sk", "cn-beijing", "agentkit", "example.com", workspace_id="ws-1"
        )
        client = TopClient(cfg)
        self.assertTrue(client.scope.endswith("/workspace/ws-1"))
        response = mock.Mock(status_code=200)
        response.json.return_value = {"Result": {"Items": [], "NextToken": None}}
        with mock.patch("_clients.requests.post", return_value=response) as post:
            client.call("ListHarnesses", {"NextToken": "page-2"})
        self.assertEqual(
            json.loads(post.call_args.kwargs["data"]),
            {"NextToken": "page-2", "WorkspaceId": "ws-1"},
        )
