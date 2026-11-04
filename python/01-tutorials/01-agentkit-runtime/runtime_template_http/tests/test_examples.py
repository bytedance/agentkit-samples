"""RuntimeTemplate 示例的离线 HTTP 契约测试。"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest import mock
from urllib.parse import parse_qs, urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import _common  # noqa: E402
import _config  # noqa: E402
import _http_client  # noqa: E402
import _iam_roles  # noqa: E402


class ContractHandler(BaseHTTPRequestHandler):
    """在内存中实现五个 Action 的最小 TOP 响应契约。"""

    requests: list[tuple[str, dict[str, Any], dict[str, str]]] = []
    template: dict[str, Any] | None = None
    paginate_list = False
    create_status = "Ready"
    get_error = False

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _send(
        self,
        action: str,
        result: dict[str, Any] | None = None,
        *,
        status: int = 200,
        error: tuple[str, str] | None = None,
    ) -> None:
        metadata: dict[str, Any] = {
            "RequestId": "req_test",
            "Action": action,
            "Version": _http_client.API_VERSION,
        }
        payload: dict[str, Any] = {"ResponseMetadata": metadata}
        if error:
            metadata["Error"] = {"Code": error[0], "Message": error[1]}
        else:
            payload["Result"] = result
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:
        action = parse_qs(urlsplit(self.path).query)["Action"][0]
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        type(self).requests.append(
            (action, body, {key: value for key, value in self.headers.items()})
        )
        if action == "CreateRuntimeTemplate":
            forbidden = {"Provider", "ProviderConfig", "RuntimeId"}
            if forbidden.intersection(body):
                self._send(
                    action,
                    status=400,
                    error=("InvalidRequest", "existing Runtime is forbidden"),
                )
                return
            type(self).template = {
                "RuntimeTemplateId": "rt_test",
                "Name": body["Name"],
                "Description": body.get("Description"),
                "RoleName": body["RoleName"],
                "Status": type(self).create_status,
                "CreateTime": "2026-10-16T00:00:00Z",
                "UpdateTime": "2026-10-16T00:00:00Z",
                "Resources": body["Resources"],
                "ImageUrl": body.get("ImageUrl"),
                "Envs": body.get("Envs", {}),
                "Runtime": body.get("Runtime", {}),
                "Meta": body.get("Meta", {}),
            }
            if "WorkspaceId" in body:
                type(self).template["WorkspaceId"] = body["WorkspaceId"]
            self._send(action, type(self).template)
            return
        if action == "GetRuntimeTemplate":
            if type(self).get_error:
                self._send(
                    action,
                    status=500,
                    error=("InternalError", "injected polling failure"),
                )
                return
            if type(self).template is None:
                self._send(
                    action,
                    status=404,
                    error=("ResourceNotFound", "template not found"),
                )
            else:
                self._send(action, type(self).template)
            return
        if action == "ListRuntimeTemplates":
            items = []
            if type(self).template is not None:
                summary = {
                    key: type(self).template[key]
                    for key in (
                        "RuntimeTemplateId",
                        "Name",
                        "Description",
                        "Status",
                        "CreateTime",
                        "UpdateTime",
                    )
                }
                if type(self).paginate_list and body.get("NextToken") == "page-2":
                    summary["RuntimeTemplateId"] = "rt_second"
                    summary["Name"] = "second"
                items.append(summary)
            next_token = (
                "page-2" if type(self).paginate_list and "NextToken" not in body else ""
            )
            self._send(action, {"Items": items, "NextToken": next_token})
            return
        if action == "UpdateRuntimeTemplate":
            if type(self).template is None:
                self._send(
                    action,
                    status=404,
                    error=("ResourceNotFound", "template not found"),
                )
                return
            if not set(body["UpdateMask"]) <= {"Description", "Meta"}:
                self._send(
                    action,
                    status=409,
                    error=("Conflict", "managed Runtime is immutable"),
                )
                return
            for field in body["UpdateMask"]:
                type(self).template[field] = body[field]
            self._send(action, type(self).template)
            return
        if action == "DeleteRuntimeTemplate":
            template_id = body["RuntimeTemplateId"]
            type(self).template = None
            self._send(action, {"RuntimeTemplateId": template_id})
            return
        self._send(
            action,
            status=404,
            error=("ResourceNotFound", "unknown action"),
        )

    def do_GET(self) -> None:
        query = parse_qs(urlsplit(self.path).query)
        action = query["Action"][0]
        params = {key: values[0] for key, values in query.items()}
        type(self).requests.append(
            (action, params, {key: value for key, value in self.headers.items()})
        )
        if action == "GetRole":
            self._send(
                action,
                {"Role": {"RoleName": params["RoleName"]}},
            )
            return
        self._send(
            action,
            status=404,
            error=("ResourceNotFound", "unknown action"),
        )


class ExampleTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ContractHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self) -> None:
        ContractHandler.requests = []
        ContractHandler.template = None
        ContractHandler.paginate_list = False
        ContractHandler.create_status = "Ready"
        ContractHandler.get_error = False
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.config = Path(self.temporary.name) / "config.yaml"
        self.config.write_text(
            """\
version: 1
volcengine:
  access_key: test-access-key
  secret_key: test-secret-key
  region: cn-beijing
runtime_template:
  session_store_id: ss-test
  id: ""
  status: ""
  endpoint: ""
  name_prefix: config-template
  description: Created from YAML
  role_name: Role
  resources:
    cpu_milli: 1000
    memory_mib: 2048
    min_replicas: 1
    max_replicas: 2
  image_url: null
  envs:
    LOG_LEVEL: info
  meta:
    source: yaml
  runtime: {}
"""
        )
        self.env = {
            "AGENTKIT_RUNTIME_TEMPLATE_CONFIG": str(self.config),
            "AGENTKIT_CLOUD_PROVIDER": "volcengine",
            "VOLCENGINE_AGENTKIT_HOST": f"127.0.0.1:{self.server.server_port}",
            "VOLCENGINE_AGENTKIT_SCHEME": "http",
            "VOLCENGINE_ACCESS_KEY": "test-access-key",
            "VOLCENGINE_SECRET_KEY": "test-secret-key",
            "VOLCENGINE_IAM_HOST": f"127.0.0.1:{self.server.server_port}",
            "VOLCENGINE_IAM_SCHEME": "http",
        }

    def run_script(
        self, script: str, *arguments: str, ok: bool = True
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(ROOT / script), *arguments],
            cwd=ROOT,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        if ok and result.returncode:
            self.fail(
                f"{script} failed:\nstdout={result.stdout}\nstderr={result.stderr}"
            )
        return result

    def test_workspace_is_sent_for_create_and_reads_but_not_updates(self):
        self.run_script(
            "01_create_runtime_template.py", "--workspace-id", "ws-selected"
        )
        self.assertEqual(ContractHandler.requests[-1][1]["WorkspaceId"], "ws-selected")
        self.run_script("02_get_runtime_template.py", "--workspace-id", "ws-selected")
        self.assertEqual(ContractHandler.requests[-1][1]["WorkspaceId"], "ws-selected")
        self.run_script(
            "04_update_runtime_template.py",
            "--workspace-id",
            "ws-selected",
            "--description",
            "new",
        )
        self.assertNotIn("WorkspaceId", ContractHandler.requests[-1][1])

    def test_saved_workspace_rejects_another_scope_before_update(self):
        self.run_script("01_create_runtime_template.py", "--workspace-id", "ws-1")
        root = yaml.safe_load(self.config.read_text())
        self.assertEqual(root["workspace_id"], "ws-1")
        self.assertEqual(root["runtime_template"]["workspace_id"], "ws-1")
        before = len(ContractHandler.requests)
        result = self.run_script(
            "04_update_runtime_template.py",
            "--workspace-id",
            "ws-2",
            "--description",
            "new",
            ok=False,
        )
        self.assertIn("another Workspace", result.stderr)
        self.assertEqual(len(ContractHandler.requests), before)

    def test_create_loads_defaults_from_yaml_config(self) -> None:
        self.run_script("01_create_runtime_template.py")
        self.assertEqual(ContractHandler.requests[-1][1]["SessionStoreId"], "ss-test")

        action, create, _headers = ContractHandler.requests[-1]
        self.assertEqual(action, "CreateRuntimeTemplate")
        self.assertRegex(
            create["Name"],
            r"^config-template-\d{14}-[0-9a-f]{8}$",
        )
        self.assertEqual(create["Description"], "Created from YAML")
        self.assertEqual(create["RoleName"], "Role")
        self.assertEqual(
            create["Resources"],
            {
                "CpuMilli": 1000,
                "MemoryMiB": 2048,
                "MinReplicas": 1,
                "MaxReplicas": 2,
            },
        )
        self.assertEqual(create["Envs"], {"LOG_LEVEL": "info"})
        self.assertEqual(create["Meta"], {"source": "yaml"})
        self.assertNotIn("ImageUrl", create)
        self.assertNotIn("Runtime", create)

    def test_cli_arguments_override_yaml_config(self) -> None:
        self.run_script(
            "01_create_runtime_template.py",
            "--name",
            "cli-name",
            "--cpu-milli",
            "3000",
            "--envs",
            '{"LOG_LEVEL":"debug"}',
        )
        create = ContractHandler.requests[-1][1]
        self.assertEqual(create["Name"], "cli-name")
        self.assertEqual(create["Resources"]["CpuMilli"], 3000)
        self.assertEqual(create["Envs"], {"LOG_LEVEL": "debug"})
        self.assertEqual(create["Meta"], {"source": "yaml"})

    def test_dry_run_allows_example_credentials(self) -> None:
        content = self.config.read_text()
        self.config.write_text(
            content.replace("test-access-key", "your-volcengine-access-key").replace(
                "test-secret-key",
                "your-volcengine-secret-key",
            )
        )
        result = self.run_script(
            "01_create_runtime_template.py",
            "--dry-run",
            "--json",
        )
        self.assertIn('"Phase": "dry-run"', result.stdout)

    def test_network_request_rejects_example_credentials(self) -> None:
        content = self.config.read_text()
        self.config.write_text(
            content.replace("test-access-key", "your-volcengine-access-key")
        )
        self.env.pop("VOLCENGINE_ACCESS_KEY")
        result = self.run_script(
            "03_list_runtime_templates.py",
            ok=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("still contains an example placeholder", result.stderr)

    def test_missing_config_reports_example_path(self) -> None:
        missing = Path(self.temporary.name) / "missing.yaml"
        self.env["AGENTKIT_RUNTIME_TEMPLATE_CONFIG"] = str(missing)
        result = self.run_script(
            "03_list_runtime_templates.py",
            "--dry-run",
            ok=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(str(_config.EXAMPLE_CONFIG_PATH), result.stderr)

    def test_complete_lifecycle_uses_pascal_case_contract(self) -> None:
        self.run_script(
            "01_create_runtime_template.py",
            "--name",
            "contract-test",
            "--role-name",
            "CustomerRuntimeRole",
            "--image-url",
            "registry.example.com/runtime:v1",
            "--envs",
            '{"LOG_LEVEL":"info"}',
            "--meta",
            '{"purpose":"test"}',
            "--wait",
        )
        action, create, headers = ContractHandler.requests[-1]
        self.assertEqual(action, "CreateRuntimeTemplate")
        self.assertIn("MemoryMiB", create["Resources"])
        self.assertNotIn("MemoryMb", create["Resources"])
        self.assertFalse(
            {"Provider", "ProviderConfig", "RuntimeId"}.intersection(create)
        )
        self.assertTrue(headers["Authorization"].startswith("HMAC-SHA256 "))

        self.run_script("02_get_runtime_template.py", "--json")
        self.run_script("03_list_runtime_templates.py", "--all")
        self.run_script(
            "04_update_runtime_template.py",
            "--clear-description",
            "--clear-meta",
            "--wait",
        )
        update = ContractHandler.requests[-1][1]
        self.assertEqual(update["UpdateMask"], ["Description", "Meta"])
        self.assertIsNone(update["Description"])
        self.assertIsNone(update["Meta"])
        self.assertFalse(
            {"Resources", "ImageUrl", "Runtime", "Envs"}.intersection(update)
        )

        self.run_script(
            "05_delete_runtime_template.py",
            "--reason",
            "test cleanup",
            "--wait",
        )
        delete = ContractHandler.requests[-2][1]
        self.assertEqual(delete["Reason"], "test cleanup")
        runtime = yaml.safe_load(self.config.read_text())["runtime_template"]
        self.assertEqual(runtime["id"], "")
        self.assertEqual(runtime["status"], "")
        self.assertEqual(runtime["endpoint"], "")

    def test_config_state_is_0600_and_contains_no_response_envs(self) -> None:
        self.run_script(
            "01_create_runtime_template.py",
            "--name",
            "state-test",
            "--role-name",
            "Role",
            "--envs",
            '{"PRIVATE_VALUE":"plaintext"}',
        )
        mode = stat.S_IMODE(self.config.stat().st_mode)
        self.assertEqual(mode, 0o600)
        runtime = yaml.safe_load(self.config.read_text())["runtime_template"]
        self.assertEqual(runtime["id"], "rt_test")
        self.assertEqual(runtime["status"], "Ready")
        self.assertIn("Version=2025-10-30", runtime["endpoint"])
        self.assertNotIn("PRIVATE_VALUE", runtime)

    def test_create_persists_id_before_polling_failure(self) -> None:
        ContractHandler.create_status = "Building"
        ContractHandler.get_error = True
        result = self.run_script(
            "01_create_runtime_template.py",
            "--name",
            "recoverable-create",
            "--role-name",
            "Role",
            "--wait",
            ok=False,
        )
        self.assertNotEqual(result.returncode, 0)
        runtime = yaml.safe_load(self.config.read_text())["runtime_template"]
        self.assertEqual(runtime["id"], "rt_test")
        self.assertEqual(runtime["status"], "Building")

    def test_volcengine_dry_run_auto_selects_default_role(self) -> None:
        self.env.pop("VOLCENGINE_AGENTKIT_HOST")
        self.env.pop("VOLCENGINE_AGENTKIT_SCHEME")
        self.env["AGENTKIT_CLOUD_PROVIDER"] = "volcengine"
        self.config.write_text(
            self.config.read_text().replace("role_name: Role", 'role_name: ""')
        )
        result = self.run_script(
            "01_create_runtime_template.py",
            "--name",
            "volcengine-preview",
            "--dry-run",
            "--json",
        )
        self.assertIn("open.volcengineapi.com", result.stdout)
        self.assertIn(
            '"RoleName": "AgentKitDefaultRuntimeAccess"',
            result.stdout,
        )
        runtime = yaml.safe_load(self.config.read_text())["runtime_template"]
        self.assertEqual(runtime["id"], "")

    def test_byteplus_dry_run_uses_byteplus_endpoint_and_explicit_role(self) -> None:
        self.env["AGENTKIT_CLOUD_PROVIDER"] = "byteplus"
        result = self.run_script(
            "01_create_runtime_template.py",
            "--name",
            "byteplus-preview",
            "--role-name",
            "BytePlusRuntimeRole",
            "--dry-run",
            "--json",
        )
        self.assertIn(
            "agentkit.ap-southeast-1.byteplusapi.com",
            result.stdout,
        )
        self.assertIn('"RoleName": "BytePlusRuntimeRole"', result.stdout)
        runtime = yaml.safe_load(self.config.read_text())["runtime_template"]
        self.assertEqual(runtime["id"], "")

    def test_list_all_passes_next_token_to_the_second_page(self) -> None:
        self.run_script(
            "01_create_runtime_template.py",
            "--name",
            "first",
            "--role-name",
            "Role",
        )
        ContractHandler.requests = []
        ContractHandler.paginate_list = True
        result = self.run_script(
            "03_list_runtime_templates.py",
            "--max-results",
            "1",
            "--all",
            "--json",
        )
        bodies = [
            body
            for action, body, _headers in ContractHandler.requests
            if action == "ListRuntimeTemplates"
        ]
        self.assertEqual(
            bodies,
            [
                {"MaxResults": 1},
                {"MaxResults": 1, "NextToken": "page-2"},
            ],
        )
        self.assertIn('"RuntimeTemplateId": "rt_second"', result.stdout)
        self.assertIn('"NextToken": ""', result.stdout)

    def test_dry_run_does_not_access_network_or_update_config_state(self) -> None:
        self.env["VOLCENGINE_AGENTKIT_HOST"] = "127.0.0.1:1"
        result = self.run_script(
            "01_create_runtime_template.py",
            "--name",
            "dry-run",
            "--role-name",
            "Role",
            "--envs",
            '{"TOKEN":"must-not-print"}',
            "--dry-run",
            "--json",
        )
        self.assertIn("<redacted>", result.stdout)
        self.assertNotIn("must-not-print", result.stdout)
        runtime = yaml.safe_load(self.config.read_text())["runtime_template"]
        self.assertEqual(runtime["id"], "")

    def test_byteplus_requires_preexisting_role_name(self) -> None:
        self.env["AGENTKIT_CLOUD_PROVIDER"] = "byteplus"
        self.config.write_text(
            self.config.read_text().replace("role_name: Role", 'role_name: ""')
        )
        result = self.run_script(
            "01_create_runtime_template.py",
            "--name",
            "missing-byteplus-role",
            "--dry-run",
            ok=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("automatic IAM role setup is available only", result.stderr)

    def test_create_rejects_incomplete_explicit_runtime(self) -> None:
        result = self.run_script(
            "01_create_runtime_template.py",
            "--name",
            "runtime-test",
            "--role-name",
            "Role",
            "--port",
            "8000",
            "--dry-run",
            ok=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--start-command", result.stderr)

    def test_update_requires_a_supported_field(self) -> None:
        result = self.run_script(
            "04_update_runtime_template.py",
            "--runtime-template-id",
            "rt_test",
            "--dry-run",
            ok=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--description", result.stderr)

    def test_client_token_allows_middle_spaces_and_trims_edges(self) -> None:
        self.assertEqual(
            _common.client_token("  token with space  "), "token with space"
        )
        with self.assertRaises(Exception):
            _common.client_token("token\nvalue")

    def test_default_runtime_role_is_created_and_policy_attached(self) -> None:
        not_found = _http_client.AgentKitHttpError(
            "IAM GetRole",
            "RoleNotExist",
            "not found",
            status_code=404,
        )
        client = mock.Mock()
        client.endpoint.service = "agentkit"
        client.call.side_effect = [
            not_found,
            {"Role": {"RoleName": _iam_roles.DEFAULT_RUNTIME_ROLE_NAME}},
            {},
        ]
        with (
            mock.patch.dict(
                os.environ,
                {"AGENTKIT_CLOUD_PROVIDER": "volcengine"},
                clear=True,
            ),
            mock.patch.object(_iam_roles, "IamHttpClient", return_value=client),
        ):
            role_name, reused = _iam_roles.prepare_runtime_role(
                _iam_roles.DEFAULT_RUNTIME_ROLE_NAME,
                dry_run=False,
            )
        self.assertEqual(role_name, _iam_roles.DEFAULT_RUNTIME_ROLE_NAME)
        self.assertFalse(reused)
        self.assertEqual(
            [call.args[0] for call in client.call.call_args_list],
            ["GetRole", "CreateRole", "AttachRolePolicy"],
        )

    def test_default_runtime_role_is_reused(self) -> None:
        client = mock.Mock()
        client.call.return_value = {
            "Role": {"RoleName": _iam_roles.DEFAULT_RUNTIME_ROLE_NAME}
        }
        with (
            mock.patch.dict(
                os.environ,
                {"AGENTKIT_CLOUD_PROVIDER": "volcengine"},
                clear=True,
            ),
            mock.patch.object(_iam_roles, "IamHttpClient", return_value=client),
        ):
            role_name, reused = _iam_roles.prepare_runtime_role(
                None,
                dry_run=False,
            )
        self.assertEqual(role_name, _iam_roles.DEFAULT_RUNTIME_ROLE_NAME)
        self.assertTrue(reused)
        client.call.assert_called_once_with(
            "GetRole",
            {"RoleName": _iam_roles.DEFAULT_RUNTIME_ROLE_NAME},
        )

    def test_top_signature_includes_session_token(self) -> None:
        credentials = _http_client.Credentials("ak", "sk", "session")
        headers = _http_client.sign_headers(
            "POST",
            "open.example.com",
            {"Action": "ListRuntimeTemplates", "Version": "2025-10-30"},
            b"{}",
            credentials=credentials,
            service="agentkit",
            region="cn-beijing",
            now=dt.datetime(2026, 10, 16, tzinfo=dt.timezone.utc),
        )
        self.assertEqual(headers["X-Security-Token"], "session")
        self.assertIn("x-security-token", headers["Authorization"])
        self.assertNotIn("sk", headers["Authorization"])

    def test_error_response_retains_request_id(self) -> None:
        response = mock.Mock()
        response.status_code = 409
        response.reason = "Conflict"
        response.json.return_value = {
            "ResponseMetadata": {
                "RequestId": "req_conflict",
                "Error": {"Code": "Conflict", "Message": "name exists"},
            }
        }
        with self.assertRaises(_http_client.AgentKitHttpError) as context:
            _http_client._response_json("CreateRuntimeTemplate", response)
        self.assertEqual(context.exception.request_id, "req_conflict")

    def test_numeric_scripts_are_importable(self) -> None:
        for path in sorted(ROOT.glob("0[1-5]_*.py")):
            spec = importlib.util.spec_from_file_location(path.stem, path)
            self.assertIsNotNone(spec)
            self.assertIsNotNone(spec.loader)

    def test_source_never_exposes_existing_runtime_fields(self) -> None:
        create_source = (ROOT / "01_create_runtime_template.py").read_text()
        for forbidden in ("ProviderConfig", "RuntimeId", '"Provider"'):
            self.assertNotIn(forbidden, create_source)

    def test_redaction_keeps_pagination_and_idempotency_tokens(self) -> None:
        value = _common.redact(
            {
                "NextToken": "next-page",
                "ClientToken": "retry-token",
                "SecretToken": "secret",
            }
        )
        self.assertEqual(value["NextToken"], "next-page")
        self.assertEqual(value["ClientToken"], "retry-token")
        self.assertEqual(value["SecretToken"], "<redacted>")

    def test_readmes_document_yaml_config_and_have_no_placeholder_image(self) -> None:
        chinese = (ROOT / "README.md").read_text()
        english = (ROOT / "README_en.md").read_text()
        self.assertIn("config.yaml.example", chinese)
        self.assertIn("config.yaml.example", english)
        self.assertNotIn("BYTEPLUS_", chinese)
        self.assertNotIn("VOLCENGINE_", english)
        self.assertIn("https://agentkit.ap-southeast-1.byteplusapi.com", english)
        self.assertIn("BYTEPLUS_AGENTKIT_SESSION_TOKEN", english)
        self.assertNotIn("registry.example.com", chinese)
        self.assertNotIn("registry.example.com", english)


if __name__ == "__main__":
    unittest.main()
