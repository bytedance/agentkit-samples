"""Harness Infra 资源到对话示例的离线协议测试。"""

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCRIPTS = {
    "create": "01_create_resources.py",
    "chat": "02_invoke_session_http.py",
    "chat_anthropic": "02_invoke_session_ant_sdk.py",
    "chat_ark": "02_invoke_session_ark_sdk.py",
    "cleanup": "03_cleanup_resources.py",
}


def tool_events(*, sequence_start=None):
    events = []
    for offset, name in enumerate(("write", "edit", "read", "grep", "glob", "bash")):
        event = {
            "id": f"tool-{name}",
            "type": "agent.tool_use",
            "content": [{"type": "tool_use", "name": name}],
        }
        if sequence_start is not None:
            event["sequence"] = sequence_start + offset
        events.append(event)
    return events


def tool_execution_events(*, sequence_start=1):
    """构造六个工具调用及其成功结果，模拟服务端持久化关联事件。"""

    events = []
    for offset, name in enumerate(("write", "edit", "read", "grep", "glob", "bash")):
        use_sequence = sequence_start + offset * 2
        use_id = f"tool-{name}"
        events.extend(
            [
                {
                    "id": use_id,
                    "type": "agent.tool_use",
                    "sequence": use_sequence,
                    "content": [{"type": "tool_use", "name": name}],
                },
                {
                    "id": f"result-{name}",
                    "type": "agent.tool_result",
                    "sequence": use_sequence + 1,
                    "tool_use_id": use_id,
                    "is_error": False,
                    "content": f"{name} completed",
                },
            ]
        )
    return events


def load_workflow_module():
    path = ROOT / "_workflow.py"
    spec = importlib.util.spec_from_file_location("example_workflow", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load workflow module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def top(result):
    return {
        "ResponseMetadata": {"RequestId": "request-fixture"},
        "Result": result,
    }


def top_error(code, message="not found"):
    return {
        "ResponseMetadata": {
            "RequestId": "request-fixture",
            "Error": {"Code": code, "Message": message},
        }
    }


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state.json"
        self.config = Path(self.temporary.name) / "config.yaml"
        # Fill connection settings only in isolated copies, never the checkout templates.
        self.sample = Path(self.temporary.name) / "resource_to_chat_http"
        self.sample.mkdir()
        for source in ROOT.glob("*.py"):
            shutil.copy2(source, self.sample / source.name)
        self.shell_templates = {}
        for name in ("02_invoke_session.sh", "02_sse_session.sh"):
            source = ROOT / name
            # Local scripts may already contain live connection settings.
            # Reset only the test copies before testing empty/configured states.
            template = re.sub(
                r"^(ENDPOINT|SESSION_ID|ENV_API_KEY)=.*$",
                r'\1=""',
                source.read_text(),
                flags=re.MULTILINE,
            )
            (self.sample / name).write_text(template)
            self.shell_templates[name] = template
        suffix = uuid.uuid4().hex
        self.control_access = f"test-access-{suffix}"
        self.control_secret = f"test-signing-{suffix}"
        self.environment_key = f"test-data-auth-{suffix}"
        self.requests = []
        self.responses = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.respond()

            def do_POST(self):
                self.respond()

            def do_DELETE(self):
                self.respond()

            def respond(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                request = {
                    "method": self.command,
                    "path": self.path,
                    "headers": dict(self.headers),
                    "raw": raw,
                    "body": json.loads(raw) if raw else None,
                    "query": {
                        key: values[0]
                        for key, values in parse_qs(urlsplit(self.path).query).items()
                    },
                }
                owner.requests.append(request)
                if not owner.responses:
                    status, body = 500, {"message": "unexpected request"}
                else:
                    status, body = owner.responses.pop(0)
                if callable(body):
                    body = body(request)
                self.send_response(status)
                self.send_header(
                    "Content-Type",
                    "text/event-stream"
                    if isinstance(body, str)
                    else "application/json",
                )
                self.send_header("request-id", "header-request-id")
                self.end_headers()
                self.wfile.write(
                    (body if isinstance(body, str) else json.dumps(body)).encode()
                )

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.config.write_text(
            json.dumps(
                {
                    "version": 1,
                    "session": {
                        "id": "",
                        "name": "",
                        "endpoint_base_url": "",
                        "title": "Harness Infra test session",
                        "prompt": "test sandbox prompt",
                    },
                    "harness": {
                        "system_prompt": "test system prompt",
                        "model": {
                            "agent_name": "model-fixture",
                            "api_base": "https://ark.example.com/api/v3",
                            "api_key_name": "model-key-name",
                            "project_name": "default",
                        },
                        "agent_loop": "adk",
                        "tools": [],
                        "skills": [],
                        "mcp_servers": [],
                    },
                    "session_store": {
                        "project_name": "default",
                        "network": {
                            "use_private_network": False,
                            "vpc_id": "",
                            "subnet_ids": [],
                        },
                    },
                    "runtime_template": {
                        "role_name": "AgentKitDefaultRuntimeAccess",
                        "resources": {
                            "cpu_milli": 1000,
                            "memory_mib": 2048,
                            "min_replicas": 1,
                            "max_replicas": 1,
                        },
                        "image_url": None,
                        "envs": {},
                        "runtime": {},
                    },
                    "environment": {
                        "type": "Cloud",
                        "resources": {
                            "cpu_milli": 2000,
                            "memory_mb": 4096,
                        },
                        "metadata": {"purpose": "test"},
                        "endpoint_id": "",
                        "env_api_key": {"id": "", "value": ""},
                    },
                    "volcengine": {
                        "access_key": "${HARNESS_INFRA_ACCESS_KEY}",
                        "secret_key": "${HARNESS_INFRA_SECRET_KEY}",
                        "region": "${HARNESS_INFRA_REGION}",
                    },
                }
            ),
            encoding="utf-8",
        )
        self.env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(
                (
                    "HARNESS_INFRA_",
                    "VOLCENGINE_",
                    "ARK_",
                    "http_proxy",
                    "https_proxy",
                    "all_proxy",
                    "HTTP_PROXY",
                    "HTTPS_PROXY",
                    "ALL_PROXY",
                )
            )
        }
        self.env.update(
            {
                "HARNESS_INFRA_ACCESS_KEY": self.control_access,
                "HARNESS_INFRA_SECRET_KEY": self.control_secret,
                "HARNESS_INFRA_REGION": "cn-beijing",
                "HARNESS_INFRA_SERVICE": "agentkit_test",
                "HARNESS_INFRA_CONTROL_HOST": f"127.0.0.1:{self.server.server_port}",
                "HARNESS_INFRA_CONTROL_SCHEME": "http",
                "HARNESS_INFRA_CONFIG": str(self.config),
                "HARNESS_INFRA_IAM_HOST": f"127.0.0.1:{self.server.server_port}",
                "HARNESS_INFRA_IAM_SCHEME": "http",
                "HARNESS_INFRA_STATE": str(self.state),
                "HARNESS_INFRA_HTTP_RETRIES": "0",
                "HARNESS_INFRA_WAIT_TIMEOUT_SECONDS": "3",
                "HARNESS_INFRA_POLL_INTERVAL_SECONDS": "1",
                "HARNESS_INFRA_DATA_TIMEOUT_SECONDS": "3",
            }
        )

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def call(
        self, script, *args, code=0, env=None, json_output=True, show_env_key=False
    ):
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(self.sample / SCRIPTS[script]),
                *(["--json"] if json_output else []),
                *args,
            ],
            env=self.env if env is None else env,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(
            completed.returncode, code, completed.stdout + completed.stderr
        )
        output = completed.stdout + completed.stderr
        for secret in (
            self.control_access,
            self.control_secret,
        ):
            self.assertNotIn(secret, output)
        if not show_env_key:
            self.assertNotIn(self.environment_key, output)
        self.assertNotIn(self.environment_key, completed.stderr)
        return completed

    def create_responses(self):
        return [
            (
                200,
                top(
                    {
                        "Items": [
                            {
                                "EndpointId": "ep_demo",
                                "BaseUrl": self.base + "/gateway",
                                "Status": "ready",
                            }
                        ],
                        "NextToken": None,
                    }
                ),
            ),
            (
                200,
                top(
                    {
                        "EnvironmentId": "env_demo",
                        "Status": "Active",
                    }
                ),
            ),
            (
                200,
                top(
                    {
                        "EnvironmentId": "env_demo",
                        "Status": "Active",
                    }
                ),
            ),
            (
                200,
                top(
                    {
                        "Items": [
                            {
                                "ResourceId": "er_demo",
                                "Status": "Creating",
                            }
                        ],
                        "NextToken": None,
                    }
                ),
            ),
            (
                200,
                top(
                    {
                        "ResourceId": "er_demo",
                        "Status": "Ready",
                        "Revision": 1,
                        "DesiredGeneration": 1,
                        "ObservedGeneration": 1,
                    }
                ),
            ),
            (
                200,
                top(
                    {
                        "HarnessId": "agent_demo",
                        "HarnessVersion": 1,
                        "Status": "Active",
                    }
                ),
            ),
            (
                200,
                top(
                    {
                        "SessionStoreId": "ss_demo",
                        "Name": "offline-store",
                        "ProviderType": "SERVERLESS_PG",
                        "Status": "Creating",
                    }
                ),
            ),
            (
                200,
                top(
                    {
                        "SessionStoreId": "ss_demo",
                        "Name": "offline-store",
                        "ProviderType": "SERVERLESS_PG",
                        "Status": "Ready",
                    }
                ),
            ),
            (
                200,
                top(
                    {
                        "Role": {
                            "RoleName": "AgentKitDefaultRuntimeAccess",
                        }
                    }
                ),
            ),
            (
                200,
                top(
                    {
                        "RuntimeTemplateId": "rt_demo",
                        "Status": "Building",
                    }
                ),
            ),
            (
                200,
                top(
                    {
                        "RuntimeTemplateId": "rt_demo",
                        "Status": "Ready",
                    }
                ),
            ),
            (
                200,
                top(
                    {
                        "ApiKeyId": "key_demo",
                        "Key": self.environment_key,
                    }
                ),
            ),
            (
                200,
                {
                    "id": "sesn_demo",
                    "name": "session-fixture",
                    "title": "Harness Infra test session",
                    "status": "idle",
                    "ark_api_key_name": "model-key-name",
                },
            ),
        ]

    def turn_events(self, request=None):
        sent = next(
            request
            for request in reversed(self.requests)
            if request["method"] == "POST"
            and urlsplit(request["path"]).path.endswith("/events")
        )
        user_event = sent["body"]["events"][0]
        events = [
            {**user_event, "sequence": 1},
            *tool_execution_events(sequence_start=2),
            {
                "id": "answer",
                "type": "agent.message",
                "sequence": 14,
                "content": [{"type": "text", "text": "TOOL USE VERIFIED 391"}],
            },
            {
                "id": "idle",
                "type": "session.status_idle",
                "sequence": 15,
                "stop_reason": {"type": "end_turn"},
            },
        ]
        if request is not None and request["query"].get("order") == "desc":
            events.reverse()
        return {
            "data": events,
            "has_more": False,
            "next_page": None,
        }

    def requires_action_events(self):
        sent = next(
            request
            for request in reversed(self.requests)
            if request["method"] == "POST"
            and urlsplit(request["path"]).path.endswith("/events")
        )
        return {
            "data": [
                {**sent["body"]["events"][0], "sequence": 1},
                {
                    "id": "idle",
                    "type": "session.status_idle",
                    "sequence": 2,
                    "stop_reason": {"type": "requires_action"},
                },
            ],
            "has_more": False,
            "next_page": None,
        }

    def chat_responses(self):
        return [
            (
                200,
                {
                    "data": [
                        {
                            "id": "user-event",
                            "type": "user.message",
                            "sequence": 1,
                        }
                    ],
                    "has_more": False,
                    "next_page": None,
                },
            ),
            (200, lambda request: self.turn_events(request)),
        ]

    def anthropic_chat_responses(self):
        return [
            (
                200,
                {
                    "data": [],
                    "has_more": False,
                    "next_page": None,
                },
            ),
            (
                200,
                {
                    "data": [{"id": "user-event", "type": "user.message"}],
                    "has_more": False,
                    "next_page": None,
                },
            ),
            (200, lambda request: self.turn_events(request)),
        ]

    def ark_chat_responses(self):
        return [
            (
                200,
                {
                    "data": [{"id": "user-event", "type": "user.message"}],
                    "has_more": False,
                    "next_page": None,
                },
            ),
            (200, lambda request: self.turn_events(request)),
        ]

    def cleanup_responses(self, *, include_api_key=True, include_session=True):
        responses = []
        if include_session:
            responses.extend(
                [
                    (200, {"id": "sesn_demo", "status": "terminated"}),
                    (200, {"id": "sesn_demo", "type": "session_deleted"}),
                    (
                        404,
                        {
                            "error": {
                                "type": "not_found_error",
                                "message": "not found",
                            }
                        },
                    ),
                ]
            )
        if include_api_key:
            responses.append((200, top({"ApiKeyId": "key_demo"})))
        responses.extend(
            [
                (200, top({"RuntimeTemplateId": "rt_demo"})),
                (404, top_error("ResourceNotFound")),
                (
                    200,
                    top(
                        {
                            "SessionStoreId": "ss_demo",
                            "ProviderType": "SERVERLESS_PG",
                            "Status": "Deleting",
                        }
                    ),
                ),
                (404, top_error("ResourceNotFound")),
                (200, top({"ResourceId": "er_demo"})),
                (
                    200,
                    top(
                        {
                            "ResourceId": "er_demo",
                            "Status": "Deleted",
                            "Revision": 2,
                        }
                    ),
                ),
                (200, top({"EnvironmentId": "env_demo"})),
                (404, top_error("InvalidEnvironment.NotFound")),
                (
                    200,
                    top(
                        {
                            "HarnessId": "agent_demo",
                            "Status": "Archived",
                        }
                    ),
                ),
            ]
        )
        return responses

    def test_full_control_chat_cleanup_lifecycle(self):
        self.responses = self.create_responses()
        self.call("create", "--prefix", "offline")
        state = json.loads(self.state.read_text())
        self.assertEqual(state["status"], "resources_ready")
        self.assertEqual(state["resources"]["environment"]["id"], "env_demo")
        self.assertEqual(state["resources"]["environment_resource"]["status"], "Ready")

        top_requests = [
            request for request in self.requests if "Action" in request["query"]
        ]
        actions = [request["query"]["Action"] for request in top_requests]
        self.assertEqual(
            actions,
            [
                "ListEndpoints",
                "CreateEnvironment",
                "GetEnvironment",
                "ListEnvironmentResources",
                "GetEnvironmentResource",
                "CreateHarness",
                "CreateSessionStore",
                "GetSessionStore",
                "GetRole",
                "CreateRuntimeTemplate",
                "GetRuntimeTemplate",
                "CreateAPIKey",
            ],
        )
        create_environment = top_requests[1]["body"]
        self.assertEqual(
            create_environment["Config"]["Resources"],
            {"CpuMilli": 2000, "MemoryMb": 4096},
        )
        create_harness = top_requests[5]["body"]
        self.assertEqual(create_harness["AgentLoop"], "adk")
        self.assertEqual(
            create_harness["Model"],
            {
                "Id": "model-fixture",
                "BaseUrl": "https://ark.example.com/api/v3",
            },
        )
        create_session_store = top_requests[6]["body"]
        self.assertEqual(create_session_store["ProviderType"], "SERVERLESS_PG")
        self.assertEqual(create_session_store["ProjectName"], "default")
        self.assertNotIn("VpcConfig", create_session_store)
        create_runtime = top_requests[9]["body"]
        self.assertEqual(
            create_runtime["RoleName"],
            "AgentKitDefaultRuntimeAccess",
        )
        self.assertEqual(create_runtime["SessionStoreId"], "ss_demo")
        self.assertEqual(create_runtime["Resources"]["MemoryMiB"], 2048)
        self.assertNotIn("Envs", create_runtime)
        self.assertNotIn("Runtime", create_runtime)

        self.responses = self.chat_responses()
        output = self.call("chat")
        self.assertIn('"answer": "TOOL USE VERIFIED 391"', output.stdout)
        data_requests = [
            request
            for request in self.requests
            if urlsplit(request["path"]).path.startswith("/gateway/")
        ]
        self.assertEqual(
            [request["method"] for request in data_requests],
            ["POST", "POST", "GET"],
        )
        session_create = data_requests[0]
        self.assertEqual(session_create["body"]["runtime_template_id"], "rt_demo")
        self.assertEqual(session_create["headers"]["x-ark-key-name"], "model-key-name")
        self.assertEqual(
            session_create["headers"]["x-api-key"],
            self.environment_key,
        )
        state_text = self.state.read_text()
        self.assertNotIn(self.environment_key, state_text)
        state = json.loads(state_text)
        self.assertEqual(state["resources"]["session"]["status"], "idle")
        self.assertEqual(state["resources"]["api_key"]["status"], "active")
        persisted_config = yaml.safe_load(self.config.read_text())
        self.assertEqual(
            persisted_config["environment"]["env_api_key"],
            {"id": "key_demo", "value": self.environment_key},
        )
        self.assertEqual(persisted_config["session"]["id"], "sesn_demo")
        self.assertEqual(
            persisted_config["session"]["endpoint_base_url"],
            self.base + "/gateway",
        )

        self.responses = self.cleanup_responses()
        self.call("cleanup")
        state = json.loads(self.state.read_text())
        self.assertTrue(state["cleaned"])
        self.assertEqual(state["resources"]["runtime_template"]["status"], "deleted")
        self.assertEqual(state["resources"]["session_store"]["status"], "deleted")
        self.assertEqual(
            state["resources"]["environment_resource"]["status"], "Deleted"
        )
        self.assertEqual(state["resources"]["environment"]["status"], "deleted")
        self.assertEqual(state["resources"]["harness"]["status"], "Archived")
        self.assertEqual(state["resources"]["endpoint"]["status"], "ready")
        cleanup_actions = [
            request["query"]["Action"]
            for request in self.requests
            if "Action" in request["query"]
        ][-10:]
        self.assertEqual(
            cleanup_actions,
            [
                "DeleteAPIKey",
                "DeleteRuntimeTemplate",
                "GetRuntimeTemplate",
                "DeleteSessionStore",
                "GetSessionStore",
                "DeleteEnvironmentResource",
                "GetEnvironmentResource",
                "DeleteEnvironment",
                "GetEnvironment",
                "ArchiveHarness",
            ],
        )
        cleared_config = yaml.safe_load(self.config.read_text())
        self.assertEqual(
            cleared_config["environment"]["env_api_key"],
            {"id": "", "value": ""},
        )
        self.assertEqual(cleared_config["session"]["id"], "")
        self.assertEqual(cleared_config["session"]["endpoint_base_url"], "")
        self.assertEqual(self.responses, [])

    def test_cleanup_clears_shell_settings_on_success_and_failure(self):
        for fails in (False, True):
            with self.subTest(cleanup_fails=fails):
                self.responses = self.create_responses()
                self.call("create")
                configured = {}
                for name in self.shell_templates:
                    path = self.sample / name
                    script = path.read_text() + "\n# Keep my custom script edits.\n"
                    path.write_text(script)
                    configured[name] = script

                self.call("cleanup", "--dry-run")
                for name, script in configured.items():
                    self.assertEqual((self.sample / name).read_text(), script)

                self.responses = (
                    [(403, {"error": {"message": "cleanup denied"}})]
                    if fails
                    else self.cleanup_responses()
                )
                self.call("cleanup", code=1 if fails else 0)
                for name, script in configured.items():
                    expected = re.sub(
                        r"^(ENDPOINT|SESSION_ID|ENV_API_KEY)=.*$",
                        r"\1=''",
                        script,
                        flags=re.MULTILINE,
                    )
                    self.assertEqual((self.sample / name).read_text(), expected)
                self.assertEqual(self.responses, [])

    def test_configured_curl_script_uses_saved_session_and_preserves_edits(self):
        self.responses = self.create_responses()
        self.call("create")
        script = self.sample / "02_invoke_session.sh"
        self.assertFalse(self.config.with_name("02_invoke_session.sh").exists())
        self.assertEqual(script.stat().st_mode & 0o777, 0o700)

        self.responses = [(200, {"data": []})]
        result = subprocess.run(
            ["sh", str(script)],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        request = self.requests[-1]
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["path"], "/gateway/v1/sessions/sesn_demo/events")
        self.assertEqual(
            request["headers"]["Authorization"], f"Bearer {self.environment_key}"
        )
        self.assertEqual(request["headers"]["Content-Type"], "application/json")
        self.assertEqual(
            request["body"],
            {
                "events": [
                    {
                        "type": "user.message",
                        "content": [
                            {
                                "type": "text",
                                "text": "帮我查下「25财年 摩根大通的财报数据，然后分析比较下，然后做成一份分析PPT",
                            }
                        ],
                    }
                ]
            },
        )
        self.assertNotIn(self.environment_key, result.stdout + result.stderr)
        self.assertEqual(self.responses, [])

        # Refill from updated YAML without changing custom script content.
        custom = script.read_text().replace("分析PPT", "自定义报告")
        script.write_text(custom + "\n# Keep this local customization.\n")
        config = yaml.safe_load(self.config.read_text())
        updated_key = "test'$(printf should-not-expand)"
        config["environment"]["env_api_key"]["value"] = updated_key
        config["session"]["id"] = "sesn_updated"
        self.config.write_text(yaml.safe_dump(config))
        subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                "from _curl import configure_session_curl_scripts; configure_session_curl_scripts()",
            ],
            cwd=self.sample,
            env=self.env,
            check=True,
            capture_output=True,
            timeout=15,
        )
        self.responses = [(200, {"data": []})]
        subprocess.run(
            ["sh", str(script)],
            env=self.env,
            check=True,
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(
            self.requests[-1]["path"], "/gateway/v1/sessions/sesn_updated/events"
        )
        self.assertEqual(
            self.requests[-1]["headers"]["Authorization"], f"Bearer {updated_key}"
        )
        self.assertIn(
            "自定义报告", self.requests[-1]["body"]["events"][0]["content"][0]["text"]
        )
        self.assertIn("# Keep this local customization.", script.read_text())
        self.assertEqual(script.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.responses, [])

    def test_configured_sse_script_subscribes_without_sending_a_message(self):
        self.responses = self.create_responses()
        self.call("create")
        script = self.sample / "02_sse_session.sh"
        self.assertFalse(self.config.with_name("02_sse_session.sh").exists())
        self.assertEqual(script.stat().st_mode & 0o777, 0o700)
        frame = 'id: 51\nevent: agent.message\ndata: {"type":"agent.message","content":[{"type":"text","text":"reply"}]}\n\n'
        for cursor in ("0", "50"):
            self.responses = [(200, frame)]
            before = len(self.requests)
            result = subprocess.run(
                ["sh", str(script), cursor],
                env=self.env,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, frame)
            self.assertEqual(result.stderr, "")
            self.assertEqual(len(self.requests), before + 1)
            request = self.requests[-1]
            self.assertEqual(request["method"], "GET")
            self.assertEqual(
                urlsplit(request["path"]).path,
                "/gateway/v1/sessions/sesn_demo/events/stream",
            )
            self.assertEqual(request["query"]["after_sequence"], cursor)
            self.assertEqual(request["headers"]["Accept"], "text/event-stream")
            self.assertEqual(
                request["headers"]["Authorization"], f"Bearer {self.environment_key}"
            )
            self.assertEqual(self.responses, [])
        result = subprocess.run(
            ["sh", str(script), "bad"],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("non-negative integer", result.stderr)
        self.responses = [(401, {"error": "unauthorized"})]
        result = subprocess.run(
            ["sh", str(script)],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 22)
        self.assertNotIn(self.environment_key, result.stdout + result.stderr)
        self.assertEqual(self.responses, [])

    def test_signing_headers_cover_pascal_body(self):
        self.responses = self.create_responses()
        self.call("create")
        request = self.requests[1]
        self.assertTrue(
            request["headers"]["Authorization"].startswith(
                f"HMAC-SHA256 Credential={self.control_access}/"
            )
        )
        self.assertEqual(
            request["headers"]["X-Content-Sha256"],
            hashlib.sha256(request["raw"]).hexdigest(),
        )
        self.assertIn(
            "/cn-beijing/agentkit_test/request", request["headers"]["Authorization"]
        )

    def test_http_chat_can_run_multiple_times_with_one_environment_key(self):
        self.responses = self.create_responses()
        self.call("create")
        request_offset = len(self.requests)

        self.responses = self.chat_responses()
        self.call("chat")
        self.responses = self.chat_responses()
        self.call("chat")

        event_sends = [
            request
            for request in self.requests[request_offset:]
            if request["method"] == "POST"
            and urlsplit(request["path"]).path
            == "/gateway/v1/sessions/sesn_demo/events"
        ]
        self.assertEqual(len(event_sends), 2)
        self.assertNotEqual(
            event_sends[0]["body"]["events"][0]["id"],
            event_sends[1]["body"]["events"][0]["id"],
        )
        state = json.loads(self.state.read_text())
        self.assertEqual(state["status"], "resources_ready")
        self.assertEqual(state["resources"]["api_key"]["status"], "active")
        self.assertEqual(state["resources"]["session"]["status"], "idle")

    def test_http_chat_prints_each_tool_result(self):
        self.responses = self.create_responses()
        self.call("create")
        self.responses = self.chat_responses()

        output = self.call("chat")

        self.assertEqual(output.stdout.count('"phase": "tool_result"'), 6)
        for name in ("write", "edit", "read", "grep", "glob", "bash"):
            self.assertIn(f'"tool_name": "{name}"', output.stdout)
            self.assertIn(f'"result": "{name} completed"', output.stdout)

    def test_anthropic_sdk_uses_harness_data_plane_contract(self):
        self.responses = self.create_responses()
        self.call("create")
        request_offset = len(self.requests)
        self.responses = self.anthropic_chat_responses()
        output = self.call("chat_anthropic")
        self.assertIn('"answer": "TOOL USE VERIFIED 391"', output.stdout)
        sdk_requests = self.requests[request_offset:]
        self.assertEqual(
            [urlsplit(request["path"]).path for request in sdk_requests],
            [
                "/gateway/v1/sessions/sesn_demo/events",
                "/gateway/v1/sessions/sesn_demo/events",
                "/gateway/v1/sessions/sesn_demo/events",
            ],
        )
        sdk_headers = {
            name.lower(): value for name, value in sdk_requests[0]["headers"].items()
        }
        self.assertEqual(sdk_headers["x-api-key"], self.environment_key)
        self.assertEqual(self.responses, [])

    def test_anthropic_sdk_serializes_timestamped_tool_results(self):
        self.responses = self.create_responses()
        self.call("create")
        timestamp = "2026-10-16T02:15:52.883835Z"

        def timestamped_events(request):
            response = self.turn_events(request)
            for event in response["data"]:
                event["created_at"] = timestamp
                event["processed_at"] = timestamp
                if event["type"] == "agent.tool_result":
                    event["type"] = "user.tool_result"
                    event["content"] = [{"type": "text", "text": event["content"]}]
            return response

        for json_output in (False, True):
            with self.subTest(json_output=json_output):
                self.responses = self.anthropic_chat_responses()
                self.responses[-1] = (200, timestamped_events)
                output = self.call(
                    "chat_anthropic",
                    json_output=json_output,
                    env={**self.env, "COLUMNS": "240"},
                ).stdout
                self.assertIn("Anthropic SDK 对话校验通过", output)
                self.assertIn("TOOL USE VERIFIED 391", output)
                self.assertIn(timestamp, output)
                if json_output:
                    decoder = json.JSONDecoder()
                    events = []
                    remaining = output.strip()
                    while remaining:
                        event, end = decoder.raw_decode(remaining)
                        events.append(event)
                        remaining = remaining[end:].lstrip()
                    results = [e for e in events if e["phase"] == "tool_result"]
                    self.assertEqual(len(results), 6)
                    for event in results:
                        self.assertEqual(event["raw_result"]["created_at"], timestamp)
                        self.assertEqual(event["raw_result"]["processed_at"], timestamp)
                else:
                    self.assertEqual(output.count("原始事件 · JSON"), 6)
                    self.assertIn("智能体回复", output)
                self.assertEqual(self.responses, [])

    def test_ark_sdk_uses_harness_data_plane_contract(self):
        self.responses = self.create_responses()
        self.call("create")
        request_offset = len(self.requests)
        self.responses = self.ark_chat_responses()
        output = self.call("chat_ark")
        self.assertIn('"answer": "TOOL USE VERIFIED 391"', output.stdout)
        sdk_requests = self.requests[request_offset:]
        self.assertEqual(
            [urlsplit(request["path"]).path for request in sdk_requests],
            [
                "/gateway/v1/sessions/sesn_demo/events",
                "/gateway/v1/sessions/sesn_demo/events",
            ],
        )
        sdk_headers = {
            name.lower(): value for name, value in sdk_requests[0]["headers"].items()
        }
        self.assertEqual(sdk_headers["x-api-key"], self.environment_key)
        self.assertEqual(self.responses, [])

    def test_environment_prompt_default_and_selfhost(self):
        spec = importlib.util.spec_from_file_location(
            "create_prompt", ROOT / SCRIPTS["create"]
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module.sys.stdin, "isatty", return_value=True):
            for answer in ("", "y", "Y", "yes"):
                with patch("builtins.input", return_value=answer):
                    self.assertEqual(
                        module.choose_environment_type(None, json_output=False), "Cloud"
                    )
            with patch("builtins.input", side_effect=["invalid", "n"]):
                self.assertEqual(
                    module.choose_environment_type(None, json_output=False),
                    "SelfHosted",
                )
            with patch("builtins.input", side_effect=EOFError):
                with self.assertRaisesRegex(RuntimeError, "尚未创建资源"):
                    module.choose_environment_type(None, json_output=False)
            with patch("builtins.input") as prompt:
                self.assertEqual(
                    module.choose_environment_type(None, json_output=True), ""
                )
                self.assertEqual(
                    module.choose_environment_type("selfhost", json_output=False),
                    "SelfHosted",
                )
                prompt.assert_not_called()

    def test_selfhost_create_prints_connection_without_cloud_sandbox(self):
        raw = yaml.safe_load(self.config.read_text())
        raw["environment"].pop("resources")
        self.config.write_text(yaml.safe_dump(raw))
        responses = self.create_responses()
        self.responses = responses[:3] + responses[5:]
        output = self.call("create", "--env-mode", "selfhost", show_env_key=True)
        self.assertEqual(self.responses, [])
        connection = next(
            json.loads(line)
            for line in output.stdout.splitlines()
            if line.startswith('{"phase": "selfhost_connection"')
        )
        self.assertEqual(connection["ANTHROPIC_BASE_URL"], self.base + "/gateway")
        self.assertEqual(connection["ANTHROPIC_ENVIRONMENT_ID"], "env_demo")
        self.assertEqual(connection["ANTHROPIC_ENVIRONMENT_KEY"], self.environment_key)
        self.assertEqual(json.loads(output.stdout.splitlines()[-1]), connection)
        actions = [request["query"].get("Action") for request in self.requests]
        self.assertNotIn("ListEnvironmentResources", actions)
        self.assertNotIn("GetEnvironmentResource", actions)
        env_request = next(
            r for r in self.requests if r["query"].get("Action") == "CreateEnvironment"
        )
        self.assertEqual(env_request["body"]["Config"], {"Type": "SelfHosted"})
        state_text = self.state.read_text()
        self.assertNotIn(self.environment_key, state_text)
        state = json.loads(state_text)
        self.assertEqual(state["config"]["environment_type"], "SelfHosted")
        self.assertNotIn("environment_resource", state["resources"])
        self.assertEqual(
            yaml.safe_load(self.config.read_text())["environment"]["type"], "SelfHosted"
        )
        self.assertEqual(
            state["resources"]["session"]["parameters"]["runtime_type"],
            "agentkit_runtime",
        )

    def test_selfhost_yaml_create_and_cleanup(self):
        raw = yaml.safe_load(self.config.read_text())
        raw["environment"]["type"] = "SelfHosted"
        raw["environment"].pop("resources")
        self.config.write_text(yaml.safe_dump(raw))
        responses = self.create_responses()
        self.responses = responses[:3] + responses[5:]
        output = self.call("create", json_output=False, show_env_key=True)
        self.assertEqual(
            output.stdout.splitlines()[-4:-1],
            [
                f"ANTHROPIC_BASE_URL={self.base}/gateway",
                "ANTHROPIC_ENVIRONMENT_ID=env_demo",
                f"ANTHROPIC_ENVIRONMENT_KEY={self.environment_key}",
            ],
        )
        offset = len(self.requests)
        responses = self.cleanup_responses()
        self.responses = responses[:-5] + responses[-3:]
        self.call("cleanup")
        self.assertEqual(self.responses, [])
        self.assertNotIn(
            "DeleteEnvironmentResource",
            [r["query"].get("Action") for r in self.requests[offset:]],
        )

    def test_cloud_override_requires_cloud_resources(self):
        raw = yaml.safe_load(self.config.read_text())
        raw["environment"]["type"] = "SelfHosted"
        raw["environment"].pop("resources")
        self.config.write_text(yaml.safe_dump(raw))
        output = self.call("create", "--env-mode", "cloud", code=1)
        self.assertIn("environment.resources", output.stderr)
        self.assertEqual(self.requests, [])
        self.assertFalse(self.state.exists())

    def test_all_dry_runs_need_no_credentials_or_state(self):
        env = {
            key: value
            for key, value in self.env.items()
            if not key.startswith("HARNESS_INFRA_")
        }
        env["HARNESS_INFRA_CONFIG"] = str(self.config)
        for script in (
            "create",
            "chat",
            "chat_anthropic",
            "chat_ark",
            "cleanup",
        ):
            self.call(script, "--dry-run", env=env)
        self.assertEqual(self.requests, [])
        self.assertFalse(self.state.exists())

        self.assertFalse(self.config.with_name("02_invoke_session.sh").exists())
        self.assertFalse(self.config.with_name("02_sse_session.sh").exists())
        for name, original in self.shell_templates.items():
            self.assertEqual((self.sample / name).read_text(), original)

    def test_unconfigured_shell_templates_stop_before_network(self):
        for name, original in self.shell_templates.items():
            for setting in ("ENDPOINT", "SESSION_ID", "ENV_API_KEY"):
                self.assertIn(f'{setting}=""', original)
            result = subprocess.run(
                ["sh", str(self.sample / name)],
                env=self.env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ENDPOINT", result.stderr)
        self.assertEqual(self.requests, [])

    def test_chat_reads_session_from_yaml_without_control_plane_state(self):
        self.responses = self.create_responses()
        self.call("create")
        self.state.write_text("{invalid", encoding="utf-8")
        request_offset = len(self.requests)
        self.responses = self.chat_responses()
        self.call("chat")
        self.assertTrue(
            all(
                "Action" not in request["query"]
                for request in self.requests[request_offset:]
            )
        )

    def test_chat_rejects_idle_without_answer(self):
        self.responses = self.create_responses()
        self.call("create")
        responses = self.chat_responses()
        responses[1] = (
            200,
            lambda request: self.requires_action_events(),
        )
        self.responses = responses
        output = self.call("chat", code=1)
        self.assertIn("requires an unsupported client action", output.stderr)
        state = json.loads(self.state.read_text())
        self.assertEqual(state["resources"]["session"]["status"], "idle")
        self.assertEqual(state["resources"]["api_key"]["status"], "active")

    def test_api_key_quota_failure_keeps_control_resources_cleanable(self):
        responses = self.create_responses()
        responses[-2] = (
            400,
            top_error(
                "InvalidRequest",
                "The number of the APIKey has exceeded the quota.",
            ),
        )
        self.responses = responses
        output = self.call("create", code=1)
        self.assertIn("exceeded the quota", output.stderr)
        state = json.loads(self.state.read_text())
        self.assertNotIn("api_key", state["resources"])

        self.responses = self.cleanup_responses(
            include_api_key=False,
            include_session=False,
        )
        self.call("cleanup")
        state = json.loads(self.state.read_text())
        self.assertTrue(state["cleaned"])

    def test_malformed_top_success_is_rejected(self):
        self.responses = [
            (200, {"ResponseMetadata": {}}),
        ]
        output = self.call("create", code=1)
        self.assertIn("missing object Result", output.stderr)
        state = json.loads(self.state.read_text())
        self.assertEqual(state["status"], "initializing")

    def test_invalid_environment_stops_before_network_and_state(self):
        env = dict(self.env)
        env["HARNESS_INFRA_ACCESS_KEY"] = "<account-ak>"
        output = self.call("create", code=1, env=env)
        self.assertIn("example placeholder", output.stderr)
        self.assertEqual(self.requests, [])
        self.assertFalse(self.state.exists())

    def test_long_prefix_keeps_session_store_name_within_provider_limit(self):
        self.responses = self.create_responses()
        self.call("create", "--prefix", "p" * 40)
        request = next(
            item
            for item in self.requests
            if item["query"].get("Action") == "CreateSessionStore"
        )
        self.assertLessEqual(len(request["body"]["Name"]), 48)
        self.assertRegex(
            request["body"]["Name"],
            r"^p{17}-\d{14}-[a-f0-9]{8}-store$",
        )

    def test_missing_runtime_role_is_created_before_runtime_template(self):
        responses = self.create_responses()
        self.responses = [
            *responses[:8],
            (404, top_error("RoleNotExist")),
            (
                200,
                top(
                    {
                        "Role": {
                            "RoleName": "AgentKitDefaultRuntimeAccess",
                        }
                    }
                ),
            ),
            (200, top({})),
            *responses[9:],
        ]
        self.call("create")
        self.assertEqual(
            [request["query"]["Action"] for request in self.requests[8:12]],
            ["GetRole", "CreateRole", "AttachRolePolicy", "CreateRuntimeTemplate"],
        )
        self.assertEqual(
            self.requests[10]["query"]["PolicyName"],
            "AgentKitDefaultRuntimeAccess",
        )

    def test_runtime_role_failure_keeps_created_resources_in_state(self):
        self.responses = [
            *self.create_responses()[:8],
            (403, top_error("AccessDenied", "role lookup denied")),
        ]
        output = self.call("create", code=1)
        self.assertIn("role lookup denied", output.stderr)
        resources = json.loads(self.state.read_text())["resources"]
        for name in (
            "endpoint",
            "environment",
            "environment_resource",
            "harness",
            "session_store",
        ):
            self.assertTrue(resources[name]["id"])
        self.assertNotIn("runtime_template", resources)
        self.assertEqual(self.requests[-1]["query"]["Action"], "GetRole")
        self.assertEqual(self.responses, [])

    def test_policy_attach_conflict_is_treated_as_idempotent_success(self):
        responses = self.create_responses()
        self.responses = [
            *responses[:8],
            (404, top_error("RoleNotExist")),
            (
                200,
                top(
                    {
                        "Role": {
                            "RoleName": "AgentKitDefaultRuntimeAccess",
                        }
                    }
                ),
            ),
            (409, top_error("PolicyAttachConflict")),
            *responses[9:],
        ]
        self.call("create")
        self.assertEqual(
            [request["query"]["Action"] for request in self.requests[8:12]],
            ["GetRole", "CreateRole", "AttachRolePolicy", "CreateRuntimeTemplate"],
        )

    def test_environment_resource_is_hidden_from_user_output(self):
        self.responses = self.create_responses()
        output = self.call("create")
        self.assertNotIn("EnvironmentResource", output.stdout)

    def test_tool_names_are_extracted_and_validated(self):
        workflow = load_workflow_module()
        observed = set()
        for event in tool_events():
            observed.update(workflow.extract_tool_names(event))
        self.assertEqual(workflow.missing_tool_names(observed), [])
        self.assertEqual(
            workflow.extract_tool_names(
                {
                    "type": "agent.tool_use",
                    "content": [{"tool_name": "sandbox_write"}],
                }
            ),
            {"sandbox_write"},
        )
        executions = workflow.collect_tool_executions(tool_execution_events())
        self.assertEqual(
            [execution["tool_name"] for execution in executions],
            ["write", "edit", "read", "grep", "glob", "bash"],
        )
        self.assertTrue(all(not execution["failed"] for execution in executions))


if __name__ == "__main__":
    unittest.main()
