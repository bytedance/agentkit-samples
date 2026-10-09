"""Offline CLI protocol tests. No real cloud credentials or resources are used."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = {
    "create": "01_create_environment_resource.py",
    "get": "02_get_environment_resource.py",
    "list": "03_list_environment_resources.py",
    "update": "04_update_environment_resource.py",
    "delete": "05_delete_environment_resource.py",
}


def resource(status="ready", revision=1, operation="op_create", generation=1):
    return {
        "resource_id": "er_demo",
        "status": status,
        "revision": revision,
        "desired_generation": generation,
        "observed_generation": generation
        if status in {"ready", "deleted"}
        else generation - 1,
        "operation_id": operation,
        "last_operation": {
            "id": operation,
            "status": "completed" if status in {"ready", "deleted"} else "pending",
        },
        "target": {"type": "ark", "environment_id": "env_demo"},
        "spec": {"sandbox": {"env_vars": {"APP_MODE": "private-value"}}},
    }


def top_resource():
    """PascalCase shape observed in the live TOP EnvironmentResources list."""
    return {
        "ResourceId": "er_demo",
        "EnvironmentId": "env_demo",
        "ResourceMode": "RuntimeAndSandbox",
        "Status": "Ready",
        "Revision": 1,
        "DesiredGeneration": 1,
        "ObservedGeneration": 1,
        "Target": {"Type": "Ark", "EnvironmentId": "env_demo"},
        "Spec": {
            "Sandbox": {
                "Profile": "ArkSkills",
                "ImageUrl": "registry.example.com/sandbox:v1",
                "EnvVars": {
                    "APP_MODE": "private-value",
                    "MixedCaseName": "private-value",
                },
                "Resources": {"CustomCPU": "2"},
                "Networking": {"CustomVPC": "vpc-demo"},
                "Agentkit": {"CustomOption": True},
            },
        },
        "Components": {"History": [{"Status": "Ready", "Generation": 1}]},
        "LastOperation": {
            "Id": "op_create",
            "Status": "Completed",
            "Step": "Publish",
            "ErrorCode": None,
        },
        "OperationId": "op_create",
        "ToolId": "tool_demo",
        "RuntimeId": "runtime_demo",
    }


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
        self.assertNotIn("environment-key-fixture", completed.stdout + completed.stderr)
        self.assertNotIn("account-key-fixture", completed.stdout + completed.stderr)
        self.assertNotIn("private-value", completed.stdout + completed.stderr)
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

    def test_direct_lifecycle_and_explicit_revision_replay(self):
        self.responses = [(200, resource("creating")), (200, resource())]
        output = self.call(
            "create",
            "--client-token",
            "create-001",
            "--wait",
            "--sandbox-env-vars",
            '{"APP_MODE":"private-value"}',
            json_output=False,
        )
        self.assertIn("[已受理]", output.stdout)
        self.assertIn("[成功] 环境资源创建成功", output.stdout)
        self.assertIn("资源 ID: er_demo", output.stdout)
        self.assertNotIn('"phase"', output.stdout)
        created = self.requests[0]
        self.assertEqual(created["url"], "/CreateEnvironmentResource")
        self.assertEqual(created["headers"]["x-api-key"], "account-key-fixture")
        self.assertNotIn("X-Top-Account-Id", created["headers"])
        self.assertEqual(
            created["body"]["target"]["environment_key"], "environment-key-fixture"
        )
        self.assertEqual(created["body"]["resource_mode"], "runtime_and_sandbox")
        self.assertEqual(created["body"]["sandbox"]["profile"], "ark_skills")
        self.assertEqual(
            created["body"]["runtime"],
            {
                "image_url": "enterprise-public-cn-beijing.cr.volces.com/vefaas-public/agentkit-selfhostsandbox:runtime-ark-skills-0.0.2"
            },
        )
        self.assertEqual(self.requests[1]["body"], {"resource_id": "er_demo"})

        self.responses = [(200, resource(revision=2, operation="op_metadata"))] * 2
        args = (
            "--expected-revision",
            "1",
            "--client-token",
            "rename-001",
            "--name",
            "new",
            "--clear-description",
            "--wait",
        )
        self.call("update", *args)
        self.call(
            "update", *args
        )  # Cache now contains revision=2; retry still sends revision=1.
        first, second = self.requests[-2:]
        self.assertEqual(first["raw"], second["raw"])
        self.assertEqual(first["body"]["expected_revision"], 1)
        self.assertEqual(first["body"]["update_mask"], ["name", "description"])
        self.assertIsNone(first["body"]["description"])
        self.assertNotIn("target", first["body"])

        self.responses = [
            (200, resource("updating", 3, "op_spec", 2)),
            (200, resource("ready", 3, "op_spec", 2)),
        ]
        self.call(
            "update",
            "--expected-revision",
            "2",
            "--client-token",
            "spec-001",
            "--sandbox-env-vars",
            "{}",
            "--wait",
        )
        updated = self.requests[-2]["body"]
        self.assertEqual(updated["sandbox"], {"env_vars": {}})
        self.assertEqual(updated["update_mask"], ["sandbox.env_vars"])
        self.assertEqual(
            updated["target"], {"environment_key": "environment-key-fixture"}
        )

        self.responses = [
            (200, resource("deleting", 4, "op_delete", 2)),
            (200, resource("deleted", 4, "op_delete", 2)),
        ]
        output = self.call(
            "delete",
            "--expected-revision",
            "3",
            "--client-token",
            "delete-001",
            "--wait",
            json_output=False,
        )
        self.assertIn("[成功] 环境资源删除成功", output.stdout)
        self.assertIn("当前状态: 已删除 (deleted)", output.stdout)
        self.assertEqual(
            self.requests[-2]["body"],
            {
                "resource_id": "er_demo",
                "expected_revision": 3,
                "client_token": "delete-001",
            },
        )
        state = json.loads(self.state.read_text())
        self.assertEqual(state["status"], "deleted")
        self.assertNotIn("key-fixture", self.state.read_text())
        self.assertNotIn("env_vars", state)
        self.responses = [(200, resource("deleted", 4, "op_delete", 2))]
        self.call("get", "--wait", "deleted")

    def test_top_envelope_signing_and_byteplus_configuration(self):
        for provider in ("volcengine", "byteplus"):
            with self.subTest(provider=provider):
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
                    }
                )
                self.responses = [(200, {"Result": resource()})]
                self.call("get", "--resource-id", "er_demo", env=env)
                request = self.requests[-1]
                self.assertEqual(urlsplit(request["url"]).path, "/")
                self.assertEqual(
                    parse_qs(urlsplit(request["url"]).query),
                    {"Action": ["GetEnvironmentResource"], "Version": ["2025-10-30"]},
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

    def test_top_accepts_plain_resource_and_list_responses(self):
        env = {
            key: value
            for key, value in self.env.items()
            if not key.startswith("MA_RESOURCE_")
        }
        env.update(
            {
                "VOLCENGINE_AGENTKIT_HOST": f"127.0.0.1:{self.server.server_port}",
                "VOLCENGINE_AGENTKIT_SCHEME": "http",
                "VOLCENGINE_ACCESS_KEY": "ak-fixture",
                "VOLCENGINE_SECRET_KEY": "sk-fixture",
            }
        )
        cases = [
            (
                "create",
                ["--client-token", "plain-create", "--role-name", "ExistingRole"],
                resource("creating"),
            ),
            ("get", ["--resource-id", "er_demo"], resource()),
            ("list", [], {"data": [resource()], "next_page": None}),
            (
                "update",
                [
                    "--resource-id",
                    "er_demo",
                    "--client-token",
                    "plain-update",
                    "--expected-revision",
                    "1",
                    "--name",
                    "updated",
                ],
                resource(revision=2),
            ),
            (
                "delete",
                [
                    "--resource-id",
                    "er_demo",
                    "--client-token",
                    "plain-delete",
                    "--expected-revision",
                    "2",
                ],
                resource("deleting", revision=3),
            ),
        ]
        for script, args, response in cases:
            with self.subTest(script=script):
                self.iam_responses = [
                    (200, {"Result": {"Role": {"RoleName": "ExistingRole"}}})
                ]
                self.responses = [(200, response)]
                self.call(
                    script,
                    *args,
                    env={
                        **env,
                        **{
                            key: value
                            for key, value in self.top_env().items()
                            if key.startswith("VOLCENGINE_IAM_")
                        },
                    },
                )
        self.assertEqual(json.loads(self.state.read_text())["status"], "deleting")

    def test_top_pascal_list_and_mixed_response_pagination(self):
        self.responses = [
            (
                200,
                {
                    "ResponseMetadata": {"RequestId": "list-request"},
                    "Result": {
                        "EnvironmentResources": [top_resource()],
                        "NextPage": "cursor-2",
                    },
                },
            ),
            (200, {"data": [], "next_page": None}),
        ]
        output = self.call("list", "--all", env=self.top_env())
        self.assertEqual(self.requests[0]["body"], {})
        self.assertEqual(self.requests[1]["body"], {"page": "cursor-2"})
        for field in (
            '"resource_id": "er_demo"',
            '"last_operation"',
            '"history"',
            '"image_url"',
            '"APP_MODE"',
            '"MixedCaseName"',
            '"CustomCPU"',
            '"CustomVPC"',
            '"CustomOption"',
        ):
            self.assertIn(field, output.stdout)
        self.assertNotIn('"app_mode"', output.stdout)
        self.assertFalse(self.state.exists())
        self.responses = [(200, {"Result": {"EnvironmentResources": [top_resource()]}})]
        output = self.call("list", env=self.top_env(), json_output=False)
        self.assertIn("er_demo | 已就绪 (ready)", output.stdout)
        self.assertIn("累计 1 条", output.stdout)
        self.responses = [(200, {"Result": {"EnvironmentResources": []}})]
        output = self.call("list", env=self.top_env(), json_output=False)
        self.assertIn("没有符合条件的资源", output.stdout)

    def test_pascal_resource_responses_support_lifecycle_and_state(self):
        cases = [
            ("create", ["--target-type", "agentkit", "--wait"], "ready"),
            ("get", ["--wait", "ready"], "ready"),
            ("update", ["--name", "updated", "--wait"], "ready"),
            ("delete", ["--wait"], "deleted"),
        ]
        for script, args, status in cases:
            with self.subTest(script=script):
                value = {**top_resource(), "Status": status.title()}
                self.responses = [(200, {"Result": value})]
                output = self.call(script, *args, env=self.top_env())
                self.assertIn('"phase": "completed"', output.stdout)
                state = json.loads(self.state.read_text())
                self.assertEqual(state["resource_id"], "er_demo")
                self.assertEqual(state["status"], status)
                self.assertEqual(state["revision"], 1)

    def test_pascal_rolled_back_operation_is_still_a_failure(self):
        failed = top_resource()
        failed["LastOperation"].update(
            Status="FailedClean", ErrorCode="Provider.Failure"
        )
        self.responses = [(200, {"Result": failed})]
        output = self.call(
            "get",
            "--resource-id",
            "er_demo",
            "--wait",
            "ready",
            env=self.top_env(),
            code=1,
            json_output=False,
        )
        self.assertIn("Provider.Failure", output.stdout)
        self.assertIn("resource operation failed", output.stderr)
        self.assertNotIn("[完成]", output.stdout)

    def test_malformed_pascal_list_is_not_treated_as_empty_success(self):
        for value in (
            {},
            {"EnvironmentResources": None},
            {"EnvironmentResources": [{}]},
            {"EnvironmentResources": [{"ResourceId": ""}]},
            {"EnvironmentResources": [], "NextPage": 123},
        ):
            with self.subTest(value=value):
                self.responses = [
                    (
                        200,
                        {
                            "ResponseMetadata": {"RequestId": "bad-list"},
                            "Result": value,
                        },
                    )
                ]
                output = self.call("list", env=self.top_env(), code=1)
                self.assertIn("Result fields=", output.stderr)
                self.assertIn("RequestId=bad-list", output.stderr)
                self.assertNotIn("query List/Get", output.stderr)
                self.assertFalse(self.state.exists())

    def test_malformed_success_responses_do_not_update_state(self):
        for response in (
            {},
            {"Result": None},
            {"Result": []},
            {"Result": {}},
            {"resource_id": "er_demo"},
            {"ResponseMetadata": {"RequestId": "request-fixture"}},
        ):
            with self.subTest(response=response):
                self.responses = [(200, response)]
                completed = self.call("get", "--resource-id", "er_demo", code=1)
                self.assertIn("top-level fields=", completed.stderr)
                self.assertFalse(self.state.exists())
        self.responses = [(200, {"data": [{}]})]
        self.call("list", code=1)
        self.assertFalse(self.state.exists())

    def test_all_dry_runs_without_credentials_or_state_writes(self):
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
                "--sandbox-env-vars",
                "{}",
            ),
            (
                "delete",
                "--resource-id",
                "er_demo",
                "--expected-revision",
                "1",
            ),
        ]
        for script, *args in cases:
            completed = self.call(script, *args, "--dry-run", env=env)
            body = json.loads(completed.stdout)["body"]
            if script in {"create", "update", "delete"}:
                self.assertRegex(body["client_token"], r"^[0-9a-f]{32}$")
            if script == "create":
                self.assertEqual(body["target"]["type"], "ark")
                self.assertEqual(
                    body["sandbox"]["image_url"],
                    "enterprise-public-cn-beijing.cr.volces.com/vefaas-public/agentkit-selfhostsandbox:tool-ark-skills-0.0.2",
                )
                self.assertEqual(
                    body["runtime"]["image_url"],
                    "enterprise-public-cn-beijing.cr.volces.com/vefaas-public/agentkit-selfhostsandbox:runtime-ark-skills-0.0.2",
                )
                for field in ("name", "description", "region"):
                    self.assertNotIn(field, body)
                self.assertNotIn("env_vars", body["sandbox"])
        self.assertEqual(self.requests, [])
        self.assertFalse(self.state.exists())

    def test_agentkit_mode_omits_ark_fields(self):
        self.responses = [(200, resource())] * 2
        self.call(
            "create", "--target-type", "agentkit", "--client-token", "local-create"
        )
        body = self.requests[-1]["body"]
        self.assertEqual(body["resource_mode"], "sandbox_only")
        self.assertEqual(body["sandbox"]["profile"], "ma_infra")
        self.assertEqual(
            body["target"], {"type": "agentkit", "environment_id": "env_demo"}
        )
        self.assertNotIn("runtime", body)
        self.call(
            "update",
            "--target-type",
            "agentkit",
            "--expected-revision",
            "1",
            "--client-token",
            "local-update",
            "--sandbox-resources",
            '{"cpu":"2"}',
            "--sandbox-networking",
            "{}",
        )
        self.assertNotIn("target", self.requests[-1]["body"])
        self.assertEqual(
            self.requests[-1]["body"]["update_mask"],
            ["sandbox.resources", "sandbox.networking"],
        )

    def test_list_filters_pagination_and_empty_body(self):
        self.responses = [
            (200, {"data": [resource()], "next_page": "cursor-2"}),
            (200, {"data": [], "next_page": None}),
        ]
        output = self.call(
            "list",
            "--target-type",
            "ark",
            "--limit",
            "1",
            "--include-deleted",
            "--all",
            json_output=False,
        )
        self.assertIn("第 1 页，1 条资源", output.stdout)
        self.assertIn("er_demo | 已就绪 (ready)", output.stdout)
        self.assertIn("累计 1 条", output.stdout)
        self.assertEqual(
            self.requests[0]["body"],
            {"target_type": "ark", "limit": 1, "include_deleted": True},
        )
        self.assertEqual(
            self.requests[1]["body"], {**self.requests[0]["body"], "page": "cursor-2"}
        )
        self.assertFalse(self.state.exists())
        self.responses = [(200, {"data": [], "next_page": None})]
        output = self.call("list", json_output=False)
        self.assertIn("没有符合条件的资源", output.stdout)
        self.assertEqual(self.requests[-1]["body"], {})

    def test_repeated_cursor_fails(self):
        self.responses = [(200, {"data": [], "next_page": "repeated"})] * 2
        completed = self.call("list", "--all", code=1)
        self.assertIn("repeated next_page", completed.stderr)
        self.assertEqual(len(self.requests), 2)

    def test_rolled_back_ready_is_not_success(self):
        failed = resource(revision=2, operation="op_failed", generation=2)
        failed["observed_generation"] = 1
        failed["last_operation"]["status"] = "failed_clean"
        failed["last_operation"]["error_code"] = "Provider.InvalidParameter.RoleName"
        self.responses = [(200, failed)]
        completed = self.call(
            "get",
            "--resource-id",
            "er_demo",
            "--wait",
            "ready",
            code=1,
            json_output=False,
        )
        self.assertIn("[失败]", completed.stdout)
        self.assertIn("失败原因: Provider.InvalidParameter.RoleName", completed.stdout)
        self.assertNotIn("[成功]", completed.stdout)
        self.assertIn("possibly rolled back", completed.stderr)
        self.assertNotIn('"phase": "completed"', completed.stdout)

    def test_generation_mismatch_times_out_without_success(self):
        stale = resource(generation=2)
        stale["observed_generation"] = 1
        self.responses = [(200, stale)] * 3
        env = {**self.env, "AGENTKIT_WAIT_TIMEOUT_SECONDS": "1"}
        completed = self.call(
            "get", "--resource-id", "er_demo", "--wait", "ready", code=1, env=env
        )
        self.assertIn("polling timed out", completed.stderr)
        self.assertNotIn('"phase": "completed"', completed.stdout)

    def test_metadata_completion_does_not_require_a_new_generation(self):
        metadata = resource(revision=3, operation="op_metadata", generation=2)
        metadata["observed_generation"] = 1
        metadata["last_operation"]["step"] = "metadata"
        self.responses = [(200, metadata)]
        completed = self.call(
            "update",
            "--resource-id",
            "er_demo",
            "--expected-revision",
            "2",
            "--client-token",
            "metadata-001",
            "--name",
            "new",
            "--wait",
        )
        self.assertIn('"phase": "completed"', completed.stdout)

    def test_operation_change_is_not_our_success(self):
        self.responses = [
            (200, resource("creating")),
            (200, resource(operation="op_other")),
        ]
        completed = self.call(
            "create", "--client-token", "create-001", "--wait", code=1
        )
        self.assertIn("another operation", completed.stderr)

    def test_errors_and_automatic_retry_keep_the_same_body(self):
        self.responses = [(503, {"message": "busy"}), (200, resource())]
        env = {**self.env, "AGENTKIT_HTTP_RETRIES": "1"}
        self.call("create", env=env)
        self.assertEqual(self.requests[0]["raw"], self.requests[1]["raw"])
        self.responses = [
            (
                409,
                {
                    "reason": "Conflict",
                    "message": "RevisionConflict environment-key-fixture",
                },
            )
        ]
        completed = self.call(
            "delete", "--expected-revision", "1", "--client-token", "delete-001", code=1
        )
        self.assertIn("RevisionConflict", completed.stderr)
        self.responses = [
            (
                200,
                {
                    "ResponseMetadata": {
                        "Error": {
                            "Code": "InvalidActionOrVersion",
                            "Message": "unavailable",
                        }
                    }
                },
            )
        ]
        completed = self.call("get", "--resource-id", "er_demo", code=1)
        self.assertIn("InvalidActionOrVersion", completed.stderr)

    def test_invalid_cli_inputs_do_not_send_requests(self):
        self.call("create", "--client-token", "bad token", code=2)
        self.call("list", "--limit", "101", code=2)
        self.call(
            "update",
            "--resource-id",
            "er_demo",
            "--client-token",
            "update-001",
            "--expected-revision",
            "1",
            code=2,
        )
        self.call(
            "update",
            "--resource-id",
            "er_demo",
            "--client-token",
            "update-001",
            "--expected-revision",
            "1",
            "--sandbox-env-vars",
            '{"NUMBER":1}',
            code=1,
        )
        self.assertEqual(self.requests, [])

    def test_state_cannot_silently_cross_endpoints(self):
        self.state.write_text(
            json.dumps(
                {"endpoint": "https://another.example.com", "resource_id": "er_demo"}
            )
        )
        completed = self.call("get", code=1)
        self.assertIn("another endpoint", completed.stderr)
        self.assertEqual(self.requests, [])

    def test_mutations_use_cached_id_and_latest_revision(self):
        self.responses = [(200, resource())]
        self.call("get", "--resource-id", "er_demo")
        self.responses = [(200, resource(revision=2, operation="op_metadata"))]
        output = self.call("update", "--name", "updated-from-state", json_output=False)
        self.assertIn("[成功] 环境资源更新成功", output.stdout)
        self.assertIn("当前版本 (revision): 2", output.stdout)
        update = self.requests[-1]["body"]
        self.assertEqual(update["resource_id"], "er_demo")
        self.assertEqual(update["expected_revision"], 1)
        self.assertEqual(update["update_mask"], ["name"])
        self.assertRegex(update["client_token"], r"^[0-9a-f]{32}$")

        self.responses = [(200, resource("deleting", revision=3))]
        output = self.call("delete", json_output=False)
        self.assertIn("[已受理] 删除请求已提交", output.stdout)
        self.assertNotIn("[成功]", output.stdout)
        deletion = self.requests[-1]["body"]
        self.assertEqual(deletion["resource_id"], "er_demo")
        self.assertEqual(deletion["expected_revision"], 2)
        self.assertRegex(deletion["client_token"], r"^[0-9a-f]{32}$")
        self.assertEqual(json.loads(self.state.read_text())["revision"], 3)

    def test_human_submission_does_not_claim_async_success(self):
        self.responses = [(200, resource("creating"))]
        output = self.call("create", json_output=False)
        self.assertIn("[已受理] 创建请求已提交", output.stdout)
        self.assertIn("资源 ID: er_demo", output.stdout)
        self.assertIn("继续等待:", output.stdout)
        self.assertIn("本次请求 token:", output.stdout)
        self.assertNotIn("[成功]", output.stdout)
        self.assertNotIn('"phase"', output.stdout)
        preview = self.call("delete", "--dry-run", json_output=False)
        self.assertIn("[预览]", preview.stdout)
        self.assertIn("本次使用版本 (revision): 1", preview.stdout)
        self.assertEqual(len(self.requests), 1)

    def test_mutations_reject_missing_invalid_or_mismatched_state(self):
        self.call("delete", "--dry-run", code=1)
        for revision in (None, 0, -1, True, "1", 1.5):
            with self.subTest(revision=revision):
                self.state.write_text(
                    json.dumps(
                        {
                            "endpoint": self.base,
                            "resource_id": "er_demo",
                            "revision": revision,
                        }
                    )
                )
                completed = self.call("delete", "--dry-run", code=1)
                self.assertIn("state revision", completed.stderr)
        self.state.write_text(
            json.dumps({"endpoint": self.base, "resource_id": "er_demo", "revision": 1})
        )
        completed = self.call(
            "update", "--resource-id", "er_other", "--name", "new", "--dry-run", code=1
        )
        self.assertIn("does not match state", completed.stderr)
        self.state.write_text(
            json.dumps(
                {
                    "endpoint": "https://other.example.com",
                    "resource_id": "er_demo",
                    "revision": 1,
                }
            )
        )
        completed = self.call("delete", "--dry-run", code=1)
        self.assertIn("another endpoint", completed.stderr)
        self.assertEqual(self.requests, [])

    def test_explicit_mutation_parameters_override_cached_values(self):
        self.state.write_text(
            json.dumps({"endpoint": self.base, "resource_id": "er_demo", "revision": 9})
        )
        completed = self.call("delete", "--expected-revision", "3", "--dry-run")
        self.assertEqual(json.loads(completed.stdout)["body"]["expected_revision"], 3)
        self.state.write_text("invalid unrelated state")
        completed = self.call(
            "delete",
            "--resource-id",
            "er_other",
            "--expected-revision",
            "4",
            "--dry-run",
        )
        body = json.loads(completed.stdout)["body"]
        self.assertEqual(body["resource_id"], "er_other")
        self.assertEqual(body["expected_revision"], 4)
        self.assertEqual(self.requests, [])

    def test_explicit_runtime_role_is_only_validated_and_replayed(self):
        env = self.top_env()
        for _ in range(2):
            self.iam_responses = [
                (200, {"Result": {"Role": {"RoleName": "CustomerRole"}}})
            ]
            self.responses = [(200, resource("creating"))]
            output = self.call(
                "create",
                "--role-name",
                " CustomerRole ",
                "--client-token",
                "same-create",
                env=env,
                json_output=False,
            )
            self.assertIn("Runtime IAM Role: CustomerRole", output.stdout)
        self.assertEqual(
            [request["query"]["Action"] for request in self.requests],
            ["GetRole", "CreateEnvironmentResource"] * 2,
        )
        self.assertEqual(self.requests[1]["raw"], self.requests[3]["raw"])
        self.assertEqual(self.requests[1]["body"]["role_name"], "CustomerRole")
        self.assertNotIn("role_name", self.requests[1]["body"]["runtime"])
        iam = self.requests[0]
        self.assertEqual(iam["method"], "GET")
        self.assertEqual(iam["raw"], b"")
        self.assertEqual(
            iam["query"],
            {"Action": "GetRole", "Version": "2018-01-01", "RoleName": "CustomerRole"},
        )
        self.assertIn("/cn-beijing/iam/request", iam["headers"]["Authorization"])
        self.assertEqual(iam["headers"]["X-Security-Token"], "sts-fixture")
        self.assertEqual(
            iam["headers"]["X-Content-Sha256"], hashlib.sha256(b"").hexdigest()
        )

    def test_runtime_role_reuse_follows_role_and_policy_pages(self):
        self.iam_responses = [
            (200, {"Result": {"RoleMetadata": [{"RoleName": "Other"}], "Total": 2}}),
            (200, {"Roles": [{"RoleName": "Reusable"}], "Total": 2}),
            (
                200,
                {
                    "AttachedPolicyMetadata": [{"PolicyName": "CustomerPolicy"}],
                    "Total": 1,
                },
            ),
            (
                200,
                {
                    "Result": {
                        "AttachedPolicyMetadata": [{"PolicyName": "Unrelated"}],
                        "Total": 2,
                    }
                },
            ),
            (
                200,
                {
                    "AttachedPolicyMetadata": [
                        {
                            "PolicyName": "agentkitdefaultruntimeaccess",
                            "PolicyType": "System",
                        }
                    ],
                    "Total": 2,
                },
            ),
        ]
        self.responses = [(200, resource("creating"))]
        self.call("create", env=self.top_env())
        self.assertEqual(self.requests[-1]["body"]["role_name"], "Reusable")
        self.assertEqual(
            [r["query"]["Offset"] for r in self.requests[:-1]],
            ["0", "1", "0", "0", "1"],
        )
        self.assertTrue(
            all(
                r["query"]["Action"] in {"ListRoles", "ListAttachedRolePolicies"}
                for r in self.requests[:-1]
            )
        )

    def test_policy_response_without_total_is_not_paged(self):
        for wrapped, total in ((False, {}), (True, {}), (True, {"Total": None})):
            with self.subTest(wrapped=wrapped, total=total):
                self.requests = []
                policies = {
                    "AttachedPolicyMetadata": [
                        {"PolicyName": "AgentKitDefaultRuntimeAccess"}
                    ],
                    **total,
                }
                response = {"Result": policies} if wrapped else policies
                self.iam_responses = [
                    (200, {"RoleMetadata": [{"RoleName": "Reusable"}], "Total": 1}),
                    (200, response),
                    # Some IAM responses have no Total and ignore Offset. The
                    # old client requested this same response again and failed.
                    (200, response),
                ]
                self.responses = [(200, resource("creating"))]
                self.call("create", env=self.top_env())
                self.assertEqual(
                    [r["query"]["Action"] for r in self.requests],
                    [
                        "ListRoles",
                        "ListAttachedRolePolicies",
                        "CreateEnvironmentResource",
                    ],
                )
                self.assertEqual(self.requests[-1]["body"]["role_name"], "Reusable")
                self.assertEqual(len(self.iam_responses), 1)

    def test_role_response_without_total_is_not_paged(self):
        for wrapped in (False, True):
            with self.subTest(wrapped=wrapped):
                self.requests = []
                roles = {"RoleMetadata": [{"RoleName": "Reusable"}]}
                self.iam_responses = [
                    (200, {"Result": roles} if wrapped else roles),
                    (
                        200,
                        {
                            "AttachedPolicyMetadata": [
                                {"PolicyName": "AgentKitDefaultRuntimeAccess"}
                            ],
                            "Total": 1,
                        },
                    ),
                ]
                self.responses = [(200, resource("creating"))]
                self.call("create", env=self.top_env())
                self.assertEqual(
                    [r["query"]["Action"] for r in self.requests],
                    [
                        "ListRoles",
                        "ListAttachedRolePolicies",
                        "CreateEnvironmentResource",
                    ],
                )
                self.assertEqual(self.requests[-1]["body"]["role_name"], "Reusable")

    def test_auto_runtime_role_creation_and_trust_policy(self):
        for service, trusted_service in (
            ("agentkit", "vefaas"),
            ("agentkit_stg", "vefaas_dev"),
        ):
            with self.subTest(service=service):
                self.requests = []
                self.iam_responses = [
                    (200, {"Result": {"RoleMetadata": [], "Total": 0}}),
                    (
                        404,
                        {
                            "ResponseMetadata": {
                                "Error": {"Code": "RoleNotExist", "Message": "absent"}
                            }
                        },
                    ),
                    (
                        200,
                        lambda request: {
                            "Result": {
                                "Role": {"RoleName": request["query"]["RoleName"]}
                            }
                        },
                    ),
                    (200, {"Result": {}}),
                ]
                self.responses = [(200, resource("creating"))]
                env = {**self.top_env(), "VOLCENGINE_AGENTKIT_SERVICE": service}
                self.call("create", env=env)
                self.assertEqual(
                    [r["query"]["Action"] for r in self.requests],
                    [
                        "ListRoles",
                        "GetRole",
                        "CreateRole",
                        "AttachRolePolicy",
                        "CreateEnvironmentResource",
                    ],
                )
                created = self.requests[2]["query"]
                role_name = created["RoleName"]
                self.assertRegex(
                    role_name, r"^AgentKit_Runtime_Default_ServiceRole_[a-z0-9]{7}$"
                )
                self.assertEqual(created["DisplayName"], role_name)
                self.assertEqual(
                    json.loads(created["TrustPolicyDocument"]),
                    {
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": ["sts:AssumeRole"],
                                "Principal": {"Service": [trusted_service]},
                            }
                        ]
                    },
                )
                attached = self.requests[3]["query"]
                self.assertEqual(attached["RoleName"], role_name)
                self.assertEqual(attached["PolicyName"], "AgentKitDefaultRuntimeAccess")
                self.assertEqual(attached["PolicyType"], "System")
                self.assertEqual(self.requests[4]["body"]["role_name"], role_name)

    def test_iam_failures_stop_before_resource_creation(self):
        cases = [
            (
                ["--role-name", "Missing"],
                [(404, {"ResponseMetadata": {"Error": {"Code": "RoleNotExist"}}})],
                "does not exist",
            ),
            (
                [],
                [
                    (
                        403,
                        {
                            "ResponseMetadata": {
                                "RequestId": "iam-denied",
                                "Error": {
                                    "Code": "AccessDenied",
                                    "Message": "environment-key-fixture",
                                },
                            }
                        },
                    )
                ],
                "RequestId=iam-denied",
            ),
            (
                [],
                [
                    (200, {"RoleMetadata": [{"RoleName": "Unreadable"}], "Total": 1}),
                    (403, {"reason": "AccessDenied"}),
                ],
                "AccessDenied",
            ),
            (
                [],
                [
                    (200, {"RoleMetadata": [], "Total": 0}),
                    (403, {"reason": "AccessDenied"}),
                ],
                "AccessDenied",
            ),
            (
                ["--role-name", "Customer"],
                [(200, {"Result": {"Role": {"RoleName": "Different"}}})],
                "mismatched",
            ),
        ]
        for args, responses, message in cases:
            with self.subTest(args=args, message=message):
                self.requests = []
                self.iam_responses = responses
                output = self.call("create", *args, env=self.top_env(), code=1)
                self.assertIn(message, output.stderr)
                self.assertTrue(all(r["method"] == "GET" for r in self.requests))
                self.assertFalse(self.state.exists())

    def test_malformed_or_repeated_iam_pages_fail_closed(self):
        for responses in (
            [(200, {})],
            [(200, {"RoleMetadata": [{}], "Total": 1})],
            [(200, {"RoleMetadata": [], "Total": 1})],
            [(200, {"RoleMetadata": [{"RoleName": "Same"}], "Total": 2})] * 2,
            [
                (200, {"RoleMetadata": [{"RoleName": "Role"}], "Total": 1}),
                (200, {"AttachedPolicyMetadata": [{}], "Total": 1}),
            ],
            [(200, {"RoleMetadata": [{"RoleName": "Role"}], "Total": 1})]
            + [
                (
                    200,
                    {"AttachedPolicyMetadata": [{"PolicyName": "Policy"}], "Total": 2},
                )
            ]
            * 2,
        ):
            with self.subTest(responses=responses):
                self.requests = []
                self.iam_responses = responses
                self.call("create", env=self.top_env(), code=1)
                self.assertTrue(
                    all(r["query"]["Action"].startswith("List") for r in self.requests)
                )

    def test_attach_conflict_requires_confirmed_policy(self):
        for confirmed in (False, True):
            with self.subTest(confirmed=confirmed):
                self.requests = []
                self.iam_responses = [
                    (200, {"RoleMetadata": [], "Total": 0}),
                    (404, {"ResponseMetadata": {"Error": {"Code": "RoleNotExist"}}}),
                    (200, lambda r: {"Role": {"RoleName": r["query"]["RoleName"]}}),
                    (409, {"ResponseMetadata": {"Error": {"Code": "Conflict"}}}),
                ]
                policies = (
                    [{"PolicyName": "AgentKitDefaultRuntimeAccess"}]
                    if confirmed
                    else []
                )
                self.iam_responses += [
                    (200, {"AttachedPolicyMetadata": policies, "Total": len(policies)})
                ] * (1 if confirmed else 4)
                self.responses = [(200, resource("creating"))]
                output = self.call(
                    "create", env=self.top_env(), code=0 if confirmed else 1
                )
                self.assertEqual(
                    any(r["method"] == "POST" for r in self.requests), confirmed
                )
                if not confirmed:
                    self.assertIn("policy attachment failed", output.stderr)

    def test_other_transports_pass_role_without_calling_volcengine_iam(self):
        for env in (self.env, self.top_env("byteplus")):
            with self.subTest(provider=env.get("AGENTKIT_CLOUD_PROVIDER")):
                self.requests = []
                self.responses = [(200, resource("creating"))]
                self.call("create", "--role-name", "ExistingRole", env=env)
                self.assertEqual(len(self.requests), 1)
                self.assertEqual(self.requests[0]["method"], "POST")
                self.assertEqual(self.requests[0]["body"]["role_name"], "ExistingRole")

    def test_role_dry_run_and_agentkit_mode_never_call_iam(self):
        output = self.call("create", "--dry-run", env=self.top_env())
        self.assertEqual(
            json.loads(output.stdout)["body"]["role_name"],
            "<auto-selected-runtime-role>",
        )
        output = self.call(
            "create",
            "--dry-run",
            env={**self.top_env(), "AGENTKIT_RUNTIME_ROLE_NAME": "FromEnv"},
        )
        self.assertEqual(json.loads(output.stdout)["body"]["role_name"], "FromEnv")
        self.call("create", "--role-name", " ", code=2)
        self.call("create", "--target-type", "agentkit", "--role-name", "Role", code=2)
        self.assertEqual(self.requests, [])
        self.responses = [(200, resource("creating"))]
        self.call("create", "--target-type", "agentkit", env=self.top_env())
        self.assertEqual(len(self.requests), 1)
        self.assertNotIn("role_name", self.requests[0]["body"])

    def test_http_errors_include_status_business_code_and_request_id(self):
        cases = [
            (
                400,
                {
                    "reason": "InvalidParameter",
                    "message": "environment-key-fixture",
                    "bizCode": 1234,
                    "RequestId": "direct-id",
                },
                ("HTTP 400", "InvalidParameter", "bizCode=1234", "RequestId=direct-id"),
            ),
            (
                200,
                {
                    "RequestId": "outer-id",
                    "ResponseMetadata": {
                        "RequestId": "metadata-id",
                        "Error": {
                            "Code": "InvalidActionOrVersion",
                            "Message": "denied",
                        },
                    },
                },
                ("HTTP 200", "InvalidActionOrVersion", "RequestId=metadata-id"),
            ),
            (403, {"reason": "Forbidden"}, ("HTTP 403", "RequestId=header-request-id")),
        ]
        for status, body, messages in cases:
            with self.subTest(status=status):
                self.responses = [(status, body)]
                output = self.call("get", "--resource-id", "er_demo", code=1)
                for message in messages:
                    self.assertIn(message, output.stderr)

    def test_failed_mutations_exit_nonzero_without_wait(self):
        failed = resource()
        failed["last_operation"]["status"] = "failed_clean"
        for script, args in (
            ("create", []),
            (
                "update",
                [
                    "--resource-id",
                    "er_demo",
                    "--expected-revision",
                    "1",
                    "--name",
                    "new",
                ],
            ),
            ("delete", ["--resource-id", "er_demo", "--expected-revision", "1"]),
        ):
            with self.subTest(script=script):
                self.responses = [(200, failed)]
                output = self.call(script, *args, code=1)
                self.assertIn("resource operation failed", output.stderr)
                self.assertNotIn('"phase": "completed"', output.stdout)


if __name__ == "__main__":
    unittest.main()
