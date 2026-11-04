"""Latest EnvironmentResource OpenAPI protocol tests with a local HTTP server."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = {
    "create": "01_create_environment_resource.py",
    "get": "02_get_environment_resource.py",
    "list": "03_list_environment_resources.py",
    "update": "04_update_environment_resource.py",
    "delete": "05_delete_environment_resource.py",
}


def resource(
    status="Ready",
    revision=1,
    desired_generation=1,
    observed_generation=None,
    error_code=None,
):
    """Return the current published PascalCase resource object."""
    if observed_generation is None:
        observed_generation = (
            desired_generation if status in {"Ready", "Deleted"} else 0
        )
    value = {
        "ResourceId": "er_demo",
        "EnvironmentId": "env_demo",
        "Name": "demo",
        "Region": "cn-beijing",
        "Status": status,
        "Revision": revision,
        "DesiredGeneration": desired_generation,
        "ObservedGeneration": observed_generation,
        "ToolId": "tool_demo",
        "RuntimeId": "runtime_demo",
        "CreatedAt": "2026-10-14T01:00:00Z",
        "UpdatedAt": "2026-10-14T01:01:00Z",
        "Config": {
            "Type": "Cloud",
            "ImageUrl": "registry.example.com/sandbox:v1",
            "EnvVars": {
                "APP_MODE": "private-value",
                "MixedCaseName": "private-value",
            },
            "Resources": {"CpuMilli": 2000, "MemoryMb": 4096},
            "Networking": {"CustomPolicy": "preserved"},
        },
    }
    if error_code:
        value["ErrorCode"] = error_code
    return value


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "resource.json"
        self.requests = []
        self.responses = []
        self.iam_responses = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                self.respond(owner.responses)

            def do_GET(self):
                self.respond(owner.iam_responses)

            def respond(self, responses):
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                owner.requests.append(
                    {
                        "method": self.command,
                        "url": self.path,
                        "headers": dict(self.headers),
                        "raw": raw,
                        "body": json.loads(raw) if raw else None,
                        "query": {
                            key: values[0]
                            for key, values in parse_qs(
                                urlsplit(self.path).query
                            ).items()
                        },
                    }
                )
                status, body = (
                    responses.pop(0)
                    if responses
                    else (500, {"message": "unexpected request"})
                )
                if callable(body):
                    body = body(owner.requests[-1])
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("request-id", "header-request-id")
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("AGENTKIT_", "VOLC", "BYTEPLUS_", "MA_RESOURCE_"))
            and key not in {"CLOUD_PROVIDER", "REGION"}
        }
        self.env.update(
            {
                "MA_RESOURCE_BASE_URL": self.base,
                "MA_RESOURCE_API_KEY": "account-key-fixture",
                "AGENTKIT_RESOURCE_STATE": str(self.state),
                "AGENTKIT_HTTP_RETRIES": "0",
                "AGENTKIT_POLL_INTERVAL_SECONDS": "1",
                "AGENTKIT_WAIT_TIMEOUT_SECONDS": "3",
                "AGENTKIT_ENVIRONMENT_ID": "env_demo",
                "AGENTKIT_ENVIRONMENT_BASE_URL": "https://external.example.com",
                "AGENTKIT_ENVIRONMENT_KEY": "environment-key-fixture",
            }
        )

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def call(self, script, *args, code=0, env=None, json_output=True):
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / SCRIPTS[script]),
                *(["--json"] if json_output else []),
                *args,
            ],
            env=self.env if env is None else env,
            capture_output=True,
            text=True,
            timeout=12,
        )
        self.assertEqual(
            completed.returncode, code, completed.stdout + completed.stderr
        )
        output = completed.stdout + completed.stderr
        self.assertNotIn("environment-key-fixture", output)
        self.assertNotIn("account-key-fixture", output)
        self.assertNotIn("private-value", output)
        return completed

    def top_env(self, provider="volcengine"):
        env = {
            key: value
            for key, value in self.env.items()
            if not key.startswith("MA_RESOURCE_")
        }
        prefix = provider.upper()
        env.update(
            {
                "AGENTKIT_CLOUD_PROVIDER": provider,
                f"{prefix}_AGENTKIT_HOST": f"127.0.0.1:{self.server.server_port}",
                f"{prefix}_AGENTKIT_SCHEME": "http",
                f"{prefix}_ACCESS_KEY": "ak-fixture",
                f"{prefix}_SECRET_KEY": "sk-fixture",
                f"{prefix}_SESSION_TOKEN": "sts-fixture",
                "VOLCENGINE_IAM_HOST": f"127.0.0.1:{self.server.server_port}",
                "VOLCENGINE_IAM_SCHEME": "http",
            }
        )
        return env

    def seed_state(self, revision=1):
        self.state.write_text(
            json.dumps(
                {
                    "endpoint": self.base,
                    "resource_id": "er_demo",
                    "revision": revision,
                    "status": "ready",
                }
            )
        )

    def test_workspace_parameter_reaches_get_and_list_but_not_update(self):
        self.responses = [
            (200, {"Result": {**resource(), "WorkspaceId": "ws-selected"}}),
            (200, {"Result": {"Items": [], "NextToken": None}}),
            (200, {"Result": {**resource(), "WorkspaceId": "ws-selected"}}),
        ]
        self.call("get", "--resource-id", "er_demo", "--workspace-id", "ws-selected")
        self.assertEqual(self.requests[-1]["body"]["WorkspaceId"], "ws-selected")
        self.call("list", "--workspace-id", "ws-selected")
        self.assertEqual(self.requests[-1]["body"]["WorkspaceId"], "ws-selected")
        self.call(
            "update",
            "--resource-id",
            "er_demo",
            "--expected-revision",
            "1",
            "--name",
            "workspace-update",
            "--workspace-id",
            "ws-selected",
        )
        self.assertNotIn("WorkspaceId", self.requests[-1]["body"])

    def test_complete_lifecycle_uses_latest_wire_contract(self):
        self.responses = [
            (200, {"Result": resource("Creating", observed_generation=0)}),
            (200, {"Result": resource()}),
        ]
        output = self.call(
            "create",
            "--name",
            "latest-contract",
            "--role-name",
            "ExistingRole",
            "--client-token",
            "create-001",
            "--sandbox-env-vars",
            '{"APP_MODE":"private-value"}',
            "--sandbox-networking",
            '{"CustomVPC":"vpc-demo"}',
            "--runtime-resources",
            '{"cpu_milli":2000,"memory_mb":4096}',
            "--wait",
            json_output=False,
        )
        self.assertIn("[成功] 环境资源创建成功", output.stdout)
        created = self.requests[0]["body"]
        self.assertEqual(created["Name"], "latest-contract")
        self.assertEqual(created["ClientToken"], "create-001")
        self.assertEqual(
            created["Target"],
            {
                "Type": "Ark",
                "EnvironmentId": "env_demo",
                "BaseUrl": "https://external.example.com",
                "EnvironmentKey": "environment-key-fixture",
            },
        )
        self.assertEqual(
            created["Runtime"]["Resources"],
            {"CpuMilli": 2000, "MemoryMb": 4096},
        )
        self.assertEqual(created["Sandbox"]["EnvVars"], {"APP_MODE": "private-value"})
        self.assertEqual(created["Sandbox"]["Networking"], {"CustomVPC": "vpc-demo"})
        self.assertNotIn("ResourceMode", created)
        self.assertNotIn("Profile", created["Sandbox"])
        self.assertEqual(self.requests[1]["body"], {"ResourceId": "er_demo"})

        self.responses = [(200, {"Result": resource(revision=2)})]
        self.call(
            "update",
            "--expected-revision",
            "1",
            "--name",
            "updated",
            "--clear-description",
            "--client-token",
            "update-001",
        )
        updated = self.requests[-1]["body"]
        self.assertEqual(updated["ExpectedRevision"], 1)
        self.assertEqual(updated["UpdateMask"], ["Name", "Description"])
        self.assertIsNone(updated["Description"])
        self.assertNotIn("Target", updated)

        self.responses = [
            (200, {"Result": {"ResourceId": "er_demo"}}),
            (200, {"Result": resource("Deleted", revision=3)}),
        ]
        self.call("delete", "--client-token", "delete-001", "--wait")
        self.assertEqual(
            self.requests[-2]["body"],
            {"ResourceId": "er_demo", "ClientToken": "delete-001"},
        )
        self.assertEqual(json.loads(self.state.read_text())["status"], "deleted")

    def test_list_uses_items_next_token_and_pascal_filters(self):
        self.responses = [
            (
                200,
                {
                    "Result": {
                        "Items": [resource()],
                        "NextToken": "cursor-2",
                    }
                },
            ),
            (200, {"Result": {"Items": [], "NextToken": None}}),
        ]
        output = self.call(
            "list",
            "--target-type",
            "ark",
            "--status",
            "delete_failed",
            "--include-deleted",
            "--max-results",
            "1",
            "--all",
        )
        self.assertIn('"MixedCaseName"', output.stdout)
        self.assertNotIn('"mixed_case_name"', output.stdout)
        self.assertEqual(
            self.requests[0]["body"],
            {
                "TargetType": "Ark",
                "Status": "DeleteFailed",
                "IncludeDeleted": True,
                "MaxResults": 1,
            },
        )
        self.assertEqual(
            self.requests[1]["body"],
            {
                **self.requests[0]["body"],
                "NextToken": "cursor-2",
            },
        )
        self.assertFalse(self.state.exists())

    def test_runtime_and_role_updates_generate_exact_masks(self):
        self.seed_state()
        self.iam_responses = [(200, {"Result": {"Role": {"RoleName": "CustomerRole"}}})]
        self.responses = [(200, {"Result": resource(revision=2)})]
        self.call(
            "update",
            "--resource-id",
            "er_demo",
            "--expected-revision",
            "1",
            "--runtime-resources",
            '{"cpu_milli":4000,"memory_mb":8192}',
            "--role-name",
            "CustomerRole",
            "--client-token",
            "runtime-update",
            env=self.top_env(),
        )
        request = self.requests[-1]["body"]
        self.assertEqual(request["UpdateMask"], ["Runtime.Resources", "RoleName"])
        self.assertEqual(
            request["Runtime"]["Resources"],
            {"CpuMilli": 4000, "MemoryMb": 8192},
        )
        self.assertEqual(request["RoleName"], "CustomerRole")
        self.assertEqual(
            request["Target"], {"EnvironmentKey": "environment-key-fixture"}
        )

    def test_agentkit_create_omits_ark_only_fields_and_empty_sandbox(self):
        self.responses = [(200, {"Result": resource()})]
        self.call(
            "create",
            "--target-type",
            "agentkit",
            "--name",
            "agentkit-target",
        )
        body = self.requests[-1]["body"]
        self.assertEqual(
            body["Target"], {"Type": "AgentKit", "EnvironmentId": "env_demo"}
        )
        for field in ("Runtime", "RoleName", "Sandbox"):
            self.assertNotIn(field, body)

    def test_get_normalizes_current_response_and_saves_only_progress(self):
        self.responses = [(200, {"Result": resource()})]
        output = self.call("get", "--resource-id", "er_demo")
        self.assertIn('"config"', output.stdout)
        self.assertIn('"cpu_milli": 2000', output.stdout)
        self.assertIn('"CustomPolicy": "preserved"', output.stdout)
        state = json.loads(self.state.read_text())
        self.assertEqual(state["resource_id"], "er_demo")
        self.assertEqual(state["revision"], 1)
        self.assertNotIn("config", state)
        self.assertNotIn("env_vars", state)

    def test_error_code_and_generation_control_completion(self):
        failed = resource("Ready", error_code="ProviderReadFailed")
        self.responses = [(200, {"Result": failed})]
        output = self.call(
            "get",
            "--resource-id",
            "er_demo",
            "--wait",
            "ready",
            code=1,
            json_output=False,
        )
        self.assertIn("ProviderReadFailed", output.stdout)
        self.assertIn("status and error_code", output.stderr)

        stale = resource("Ready", desired_generation=2, observed_generation=1)
        self.responses = [(200, {"Result": stale})] * 3
        output = self.call(
            "get",
            "--resource-id",
            "er_demo",
            "--wait",
            "ready",
            code=1,
            env={**self.env, "AGENTKIT_WAIT_TIMEOUT_SECONDS": "1"},
        )
        self.assertIn("polling timed out", output.stderr)

    def test_top_signing_for_both_providers(self):
        for provider in ("volcengine", "byteplus"):
            with self.subTest(provider=provider):
                self.responses = [(200, {"Result": resource()})]
                self.call(
                    "get",
                    "--resource-id",
                    "er_demo",
                    env=self.top_env(provider),
                )
                request = self.requests[-1]
                self.assertEqual(
                    request["query"],
                    {
                        "Action": "GetEnvironmentResource",
                        "Version": "2025-10-30",
                    },
                )
                self.assertTrue(
                    request["headers"]["Authorization"].startswith(
                        "HMAC-SHA256 Credential=ak-fixture/"
                    )
                )
                self.assertEqual(request["headers"]["X-Security-Token"], "sts-fixture")
                self.assertEqual(
                    request["headers"]["X-Content-Sha256"],
                    hashlib.sha256(request["raw"]).hexdigest(),
                )

    def test_explicit_role_is_validated_before_top_create(self):
        self.iam_responses = [(200, {"Result": {"Role": {"RoleName": "CustomerRole"}}})]
        self.responses = [(200, {"Result": resource("Creating")})]
        self.call(
            "create",
            "--name",
            "role-test",
            "--role-name",
            "CustomerRole",
            env=self.top_env(),
        )
        self.assertEqual(
            [request["query"]["Action"] for request in self.requests],
            ["GetRole", "CreateEnvironmentResource"],
        )
        self.assertEqual(self.requests[-1]["body"]["RoleName"], "CustomerRole")

    def test_retry_reuses_identical_pascal_body(self):
        self.responses = [
            (503, {"message": "busy"}),
            (200, {"Result": resource()}),
        ]
        self.call(
            "create",
            "--role-name",
            "ExistingRole",
            env={**self.env, "AGENTKIT_HTTP_RETRIES": "1"},
        )
        self.assertEqual(self.requests[0]["raw"], self.requests[1]["raw"])

    def test_http_and_top_errors_include_diagnostics(self):
        self.responses = [
            (
                409,
                {
                    "reason": "RevisionConflict",
                    "message": "conflict",
                    "bizCode": 1001,
                    "RequestId": "direct-id",
                },
            )
        ]
        output = self.call("get", "--resource-id", "er_demo", code=1)
        for value in ("HTTP 409", "RevisionConflict", "bizCode=1001", "direct-id"):
            self.assertIn(value, output.stderr)

        self.responses = [
            (
                200,
                {
                    "ResponseMetadata": {
                        "RequestId": "top-id",
                        "Error": {
                            "Code": "InvalidActionOrVersion",
                            "Message": "unavailable",
                        },
                    }
                },
            )
        ]
        output = self.call("get", "--resource-id", "er_demo", code=1)
        self.assertIn("InvalidActionOrVersion", output.stderr)
        self.assertIn("top-id", output.stderr)

    def test_malformed_success_shapes_never_update_state(self):
        cases = [
            {},
            {"Result": None},
            {"Result": {}},
            {"Result": {"ResourceId": "er_demo"}},
            {"Result": {"Items": [{}], "NextToken": None}},
        ]
        for index, response in enumerate(cases):
            with self.subTest(index=index):
                self.responses = [(200, response)]
                script = "list" if index == len(cases) - 1 else "get"
                args = () if script == "list" else ("--resource-id", "er_demo")
                self.call(script, *args, code=1)
                self.assertFalse(self.state.exists())

    def test_all_dry_runs_need_no_credentials_and_write_no_state(self):
        env = {
            key: value
            for key, value in self.env.items()
            if not key.startswith(("MA_RESOURCE_", "AGENTKIT_ENVIRONMENT_"))
        }
        cases = [
            ("create",),
            ("get", "--resource-id", "er_demo"),
            ("list",),
            (
                "update",
                "--resource-id",
                "er_demo",
                "--expected-revision",
                "1",
                "--name",
                "new",
            ),
            ("delete", "--resource-id", "er_demo"),
        ]
        for script, *args in cases:
            output = self.call(script, *args, "--dry-run", env=env)
            body = json.loads(output.stdout)["body"]
            if script == "delete":
                self.assertNotIn("expected_revision", body)
            if script == "create":
                self.assertEqual(body["name"], "self-hosted-sandbox-http")
        self.assertEqual(self.requests, [])
        self.assertFalse(self.state.exists())

    def test_update_uses_cached_revision_but_delete_needs_only_id(self):
        self.seed_state(revision=7)
        self.responses = [(200, {"Result": resource(revision=8)})]
        self.call("update", "--name", "cached-update")
        self.assertEqual(self.requests[-1]["body"]["ExpectedRevision"], 7)

        self.responses = [(200, {"Result": {"ResourceId": "er_demo"}})]
        self.call("delete")
        deleted = self.requests[-1]["body"]
        self.assertEqual(deleted["ResourceId"], "er_demo")
        self.assertNotIn("ExpectedRevision", deleted)

    def test_state_is_bound_to_endpoint(self):
        self.state.write_text(
            json.dumps(
                {"endpoint": "https://other.example.com", "resource_id": "er_demo"}
            )
        )
        output = self.call("get", code=1)
        self.assertIn("another endpoint", output.stderr)
        self.assertEqual(self.requests, [])

    def test_invalid_cli_inputs_send_no_requests(self):
        self.call("create", "--client-token", "bad token", code=2)
        self.call("create", "--name", "missing-role", code=2)
        self.call("list", "--max-results", "101", code=2)
        self.call(
            "update",
            "--resource-id",
            "er_demo",
            "--expected-revision",
            "1",
            code=2,
        )
        self.call(
            "update",
            "--resource-id",
            "er_demo",
            "--expected-revision",
            "1",
            "--sandbox-env-vars",
            '{"NUMBER":1}',
            code=1,
        )
        self.call(
            "create",
            "--target-type",
            "agentkit",
            "--runtime-resources",
            "{}",
            code=2,
        )
        self.assertEqual(self.requests, [])

    def test_repeated_next_token_fails_closed(self):
        self.responses = [
            (200, {"Result": {"Items": [], "NextToken": "repeated"}}),
            (200, {"Result": {"Items": [], "NextToken": "repeated"}}),
        ]
        output = self.call("list", "--all", code=1)
        self.assertIn("repeated NextToken", output.stderr)
        self.assertEqual(len(self.requests), 2)


if __name__ == "__main__":
    unittest.main()
