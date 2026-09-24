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


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "resource.json"
        self.requests = []
        self.responses = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                owner.requests.append(
                    {
                        "url": self.path,
                        "headers": dict(self.headers),
                        "raw": raw,
                        "body": json.loads(raw),
                    }
                )
                status, body = (
                    owner.responses.pop(0)
                    if owner.responses
                    else (500, {"message": "unexpected request"})
                )
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
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
            ("create", ["--client-token", "plain-create"], resource("creating")),
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
                self.responses = [(200, response)]
                self.call(script, *args, env=env)
        self.assertEqual(json.loads(self.state.read_text())["status"], "deleting")

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


if __name__ == "__main__":
    unittest.main()
