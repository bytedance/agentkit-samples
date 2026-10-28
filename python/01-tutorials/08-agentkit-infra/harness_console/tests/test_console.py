"""Offline protocol tests use real local HTTP servers, never cloud resources."""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import CATALOG, SAMPLE, Console
from server import make_server


class Upstream(BaseHTTPRequestHandler):
    calls: ClassVar[list] = []
    rows: ClassVar[dict] = {}
    events: ClassVar[list] = []

    def log_message(self, *_):
        pass

    def respond(self, body, status=200):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        body = json.loads(
            self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}"
        )
        action = parse_qs(urlsplit(self.path).query).get("Action", [""])[0]
        self.calls.append(("POST", self.path, body, dict(self.headers)))
        if action:
            result = {}
            for kind, spec in CATALOG.items():
                if kind == "sessions":
                    continue
                rows = self.rows[kind]
                if (
                    kind == "stores"
                    and action in (spec["create"], spec["delete"])
                    and "ClientToken" in body
                ):
                    return self.respond(
                        {
                            "ResponseMetadata": {
                                "Error": {"Code": "UnexpectedClientToken"}
                            }
                        },
                        400,
                    )
                if action == spec["list"]:
                    if kind == "stores":
                        result = {"SessionStores": list(rows.values()), "NextToken": ""}
                    elif kind == "endpoints" and not body.get("NextToken"):
                        result = {"Items": [], "NextToken": "page-2"}
                    else:
                        result = {
                            "Items": [
                                row
                                for row in rows.values()
                                if (
                                    row.get("Status") == body["Status"]
                                    if body.get("Status")
                                    else row.get("Status") != "Archived"
                                    or body.get("IncludeArchived")
                                )
                            ],
                            "NextToken": "",
                        }
                    break
                if action == spec["get"]:
                    rid = body[spec["id"]]
                    if rid not in rows:
                        return self.respond(
                            {"ResponseMetadata": {"Error": {"Code": "NotFound"}}}, 404
                        )
                    result = rows[rid]
                    break
                if action == spec["create"]:
                    rid = kind + "-new"
                    result = {**body, spec["id"]: rid, "Status": "Active"}
                    if kind == "keys":
                        result["Key"] = "new-environment-secret"
                    rows[rid] = {k: v for k, v in result.items() if k != "Key"}
                    break
                if action == spec.get("archive"):
                    rid = body[spec["id"]]
                    rows[rid]["Status"] = "Archived"
                    result = rows[rid]
                    break
                if action == spec["delete"]:
                    rows.pop(body[spec["id"]], None)
                    result = {spec["id"]: body[spec["id"]]}
                    break
            return self.respond({"Result": result})
        if self.path == "/gateway/v1/sessions":
            result = {**body, "id": "session-new", "status": "idle"}
            self.rows["sessions"]["session-new"] = result
            return self.respond(result)
        if self.path.endswith("/archive"):
            return self.respond({"id": "session-new", "status": "terminated"})
        if self.path.endswith("/events"):
            event = body["events"][0]
            if not any(e["id"] == event["id"] for e in self.events):
                self.events.append({**event, "sequence": len(self.events) + 1})
                self.events.append(
                    {
                        "id": "reply-" + event["id"],
                        "sequence": len(self.events) + 1,
                        "type": "agent.message",
                        "content": [
                            {"type": "text", "text": "你好，本地协议测试成功。"}
                        ],
                    }
                )
                self.events.append(
                    {
                        "id": "idle-" + event["id"],
                        "sequence": len(self.events) + 1,
                        "type": "session.status_idle",
                        "stop_reason": {"type": "end_turn"},
                    }
                )
            return self.respond(
                {"data": [e for e in self.events if e["id"] == event["id"]]}
            )
        self.respond({"error": {"message": "unknown route"}}, 404)

    def do_GET(self):
        self.calls.append(("GET", self.path, None, dict(self.headers)))
        path = urlsplit(self.path)
        if path.path.endswith("/events"):
            after = int(parse_qs(path.query).get("after_sequence", [0])[0])
            return self.respond(
                {
                    "data": [e for e in self.events if e["sequence"] > after],
                    "has_more": False,
                }
            )
        if path.path == "/gateway/v1/sessions":
            return self.respond(
                {"data": list(self.rows["sessions"].values()), "next_page": None}
            )
        rid = path.path.rsplit("/", 1)[-1]
        if rid in self.rows["sessions"]:
            return self.respond(self.rows["sessions"][rid])
        self.respond({"error": {"type": "not_found_error"}}, 404)

    def do_DELETE(self):
        self.calls.append(("DELETE", self.path, None, dict(self.headers)))
        rid = self.path.rsplit("/", 1)[-1]
        if "/sessions/" in self.path:
            self.rows["sessions"].pop(rid, None)
        self.respond({"id": rid})


def fixture(directory):
    Upstream.calls, Upstream.events = [], []
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    host = f"127.0.0.1:{upstream.server_port}"
    Upstream.rows = {k: {} for k in CATALOG}
    Upstream.rows["endpoints"] = {
        "ep-one": {
            "EndpointId": "ep-one",
            "Domain": "local-protocol-fixture",
            "BaseUrl": f"http://{host}/gateway",
            "Status": "Ready",
        }
    }
    Upstream.rows["keys"] = {
        "key-one": {
            "ApiKeyId": "key-one",
            "Name": "本地测试密钥",
            "EndpointId": "ep-one",
            "EnvironmentId": "env-one",
        }
    }
    Upstream.rows["environments"] = {
        "env-one": {
            "EnvironmentId": "env-one",
            "Name": "测试运行环境",
            "Status": "Active",
        }
    }
    Upstream.rows["harnesses"] = {
        "harness-one": {
            "HarnessId": "harness-one",
            "Name": "通用助手",
            "Status": "Active",
            "AgentLoop": "adk",
        }
    }
    Upstream.rows["stores"] = {
        "ss-one": {
            "SessionStoreId": "ss-one",
            "Name": "test-storage",
            "Status": "Ready",
            "ProviderType": "SERVERLESS_PG",
        }
    }
    Upstream.rows["templates"] = {
        "runtime-one": {
            "RuntimeTemplateId": "runtime-one",
            "SessionStoreId": "ss-one",
            "Name": "default",
            "Status": "Ready",
        }
    }
    Upstream.rows["sessions"] = {
        "session-one": {
            "id": "session-one",
            "title": "Harness Infra 工作空间",
            "status": "idle",
            "environment_id": "env-one",
        }
    }
    config = yaml.safe_load((SAMPLE.parent / "config.yaml.example").read_text())
    config["volcengine"].update(
        access_key="local-access-key", secret_key="local-secret-key"
    )
    config["harness"]["model"]["api_key_name"] = "model-key-name"
    config["environment"]["env_api_key"] = {
        "id": "key-one",
        "value": "local-environment-secret",
    }
    config["environment"]["endpoint_id"] = "ep-one"
    config["console"] = {"control_rest_base_url": f"http://{host}"}
    path = Path(directory) / "config.yaml"
    path.write_text(yaml.safe_dump(config))
    with patch.dict(
        os.environ,
        {"HARNESS_INFRA_CONTROL_HOST": host, "HARNESS_INFRA_CONTROL_SCHEME": "http"},
    ):
        console = Console(path, Path(directory) / "keys.json")
    return upstream, console


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.upstream, self.console = fixture(self.directory.name)
        self.http = make_server(self.console, 0)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.http.server_port}"
        self.boot = requests.get(self.url + "/api/bootstrap", timeout=5).json()
        self.ctx = {"endpoint_id": "ep-one", "key_id": "key-one"}

    def tearDown(self):
        for server in (self.http, self.upstream):
            server.shutdown()
            server.server_close()
        self.directory.cleanup()

    def post(self, path, body):
        return requests.post(
            self.url + "/api/" + path,
            json=body,
            headers={"X-Console-Token": self.boot["csrf"]},
            timeout=5,
        )

    def test_config_and_http_boundary(self):
        boot = json.dumps(self.boot)
        for secret in self.console.secrets():
            if secret:
                self.assertNotIn(secret, boot)
        self.assertEqual(
            requests.post(
                self.url + "/api/list", json={"kind": "endpoints"}, timeout=5
            ).status_code,
            403,
        )
        self.assertEqual(
            requests.get(
                self.url + "/api/bootstrap",
                headers={"Host": "attacker.example"},
                timeout=5,
            ).status_code,
            403,
        )
        self.assertEqual(
            requests.get(
                self.url + "/api/bootstrap",
                headers={"Origin": "https://attacker.example"},
                timeout=5,
            ).status_code,
            403,
        )
        self.assertEqual(
            requests.get(self.url + "/config.yaml", timeout=5).status_code, 404
        )
        self.assertEqual(self.post("create", {"kind": "unknown"}).status_code, 400)
        self.assertEqual(
            self.post("get", {"kind": "sessions", "id": "../secrets"}).status_code, 400
        )

    def test_top_pagination_get_and_signature(self):
        first = self.post("list", {"kind": "endpoints"}).json()
        self.assertEqual(first, {"items": [], "next_cursor": "page-2"})
        second = self.post(
            "list", {"kind": "endpoints", "cursor": first["next_cursor"]}
        ).json()
        self.assertEqual(second["items"][0]["EndpointId"], "ep-one")
        self.assertEqual(
            self.post("get", {"kind": "endpoints", "id": "ep-one"}).json()[
                "EndpointId"
            ],
            "ep-one",
        )
        for _, path, body, headers in Upstream.calls:
            self.assertIn("Version=2025-10-30", path)
            self.assertIn("MaxResults", body)
            self.assertTrue(headers["Authorization"].startswith("HMAC-SHA256"))
            self.assertNotIn("X-Top-Account-Id", headers)

    def test_resource_crud_and_key_restart(self):
        for kind in ("harnesses", "templates", "environments", "resources", "keys"):
            body = {
                "Name": "offline-test",
                "EnvironmentId": "env-one",
                "EndpointId": "ep-one",
            }
            if kind == "templates":
                body["SessionStoreId"] = "ss-one"
            response = self.post(
                "create", {"kind": kind, "body": body, "token": "stable-token"}
            )
            self.assertEqual(response.status_code, 200, response.text)
            rid = response.json()[CATALOG[kind]["id"]]
            self.assertEqual(
                self.post("get", {"kind": kind, "id": rid}).status_code, 200
            )
            if kind == "keys":
                self.assertNotIn("new-environment-secret", response.text)
                self.assertEqual(self.console.state_path.stat().st_mode & 0o777, 0o600)
                with patch.dict(
                    os.environ,
                    {
                        "HARNESS_INFRA_CONTROL_HOST": self.console.control.config.host,
                        "HARNESS_INFRA_CONTROL_SCHEME": "http",
                    },
                ):
                    other = Console(self.console.path, self.console.state_path)
                self.assertEqual(other.keys[rid]["value"], "new-environment-secret")
            self.assertEqual(
                self.post(
                    "archive" if kind == "harnesses" else "delete",
                    {
                        "kind": kind,
                        "id": rid,
                        "token": "delete-token",
                        "reason": "不再使用",
                    },
                ).status_code,
                200,
            )
            self.assertEqual(
                self.post("get", {"kind": kind, "id": rid}).status_code,
                200 if kind == "harnesses" else 404,
            )
        self.assertNotIn("keys-new", self.console.keys)
        actions = [
            parse_qs(urlsplit(c[1]).query).get("Action", [""])[0]
            for c in Upstream.calls
        ]
        self.assertIn("ArchiveHarness", actions)
        self.assertNotIn("DeleteHarness", actions)

    def test_session_store_config_and_crud_contract(self):
        preset = self.boot["presets"]["stores"]
        self.assertEqual(preset["ProviderType"], "SERVERLESS_PG")
        self.assertEqual(preset["ProjectName"], "default")
        self.assertNotIn("VpcConfig", preset)
        legacy = dict(self.console.raw)
        legacy.pop("session_store", None)
        self.assertEqual(self.console.make_presets(legacy)["stores"], preset)
        private = dict(
            legacy,
            session_store={
                "project_name": "private-project",
                "network": {
                    "use_private_network": True,
                    "vpc_id": "vpc-test",
                    "subnet_ids": ["subnet-test"],
                },
            },
        )
        private_preset = self.console.make_presets(private)["stores"]
        self.assertEqual(
            private_preset["VpcConfig"],
            {"VpcId": "vpc-test", "SubnetIds": ["subnet-test"]},
        )
        created = self.post(
            "create", {"kind": "stores", "body": private_preset, "token": "ignored"}
        )
        self.assertEqual(created.status_code, 200, created.text)
        self.assertNotIn("ClientToken", Upstream.calls[-1][2])
        rid = created.json()["SessionStoreId"]
        self.assertEqual(
            self.post("get", {"kind": "stores", "id": rid}).status_code, 200
        )
        page = self.post(
            "list", {"kind": "stores", "filters": {"ProjectName": "private-project"}}
        )
        self.assertEqual(page.status_code, 200, page.text)
        self.assertTrue(
            any(row["SessionStoreId"] == rid for row in page.json()["items"])
        )
        self.assertEqual(Upstream.calls[-1][2]["ProjectName"], "private-project")
        with patch.object(
            self.console.control,
            "call",
            return_value={"SessionStores": [], "NextToken": "next"},
        ) as call:
            page = self.console.list("stores", cursor="previous")
            self.assertEqual(page["next_cursor"], "next")
            self.assertEqual(call.call_args.args[1]["NextToken"], "previous")
        deleted = self.post("delete", {"kind": "stores", "id": rid, "token": "ignored"})
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(Upstream.calls[-1][2], {"SessionStoreId": rid})
        self.assertEqual(
            self.post("get", {"kind": "stores", "id": rid}).status_code, 404
        )

    def test_session_store_network_validation_before_create(self):
        for vpc in (
            {"VpcId": "vpc-test", "SubnetIds": []},
            {"VpcId": "vpc-test", "SubnetIds": ["one", "two"]},
            {"SubnetIds": ["one"]},
        ):
            before = len(Upstream.calls)
            result = self.post(
                "create",
                {
                    "kind": "stores",
                    "body": {**self.boot["presets"]["stores"], "VpcConfig": vpc},
                },
            )
            self.assertEqual(result.status_code, 400, result.text)
            self.assertEqual(len(Upstream.calls), before)

    def test_runtime_template_requires_ready_pg_without_altering_legacy(self):
        for store_id, status, provider in (
            ("", "Ready", "SERVERLESS_PG"),
            ("ss-one", "Creating", "SERVERLESS_PG"),
            ("ss-one", "Ready", "OTHER"),
        ):
            Upstream.rows["stores"]["ss-one"].update(
                Status=status, ProviderType=provider
            )
            before = len(Upstream.calls)
            result = self.post(
                "create",
                {
                    "kind": "templates",
                    "body": {"Name": "new-runtime", "SessionStoreId": store_id},
                    "token": "t",
                },
            )
            self.assertEqual(result.status_code, 400, result.text)
            self.assertFalse(
                any(
                    "Action=CreateRuntimeTemplate" in c[1]
                    for c in Upstream.calls[before:]
                )
            )
        Upstream.rows["stores"]["ss-one"].update(
            Status="Ready", ProviderType="SERVERLESS_PG"
        )
        result = self.post(
            "create",
            {
                "kind": "templates",
                "body": {"Name": "new-runtime", "SessionStoreId": "ss-one"},
                "token": "t",
            },
        )
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(Upstream.calls[-1][2]["SessionStoreId"], "ss-one")
        # Existing templates stay readable; no migration/rebinding on list/get.
        Upstream.rows["templates"]["runtime-one"].pop("SessionStoreId")
        self.assertEqual(
            self.post("get", {"kind": "templates", "id": "runtime-one"}).status_code,
            200,
        )

    def test_expired_page_token_is_rejected_before_mutation(self):
        before = len(Upstream.calls)
        response = requests.post(
            self.url + "/api/create",
            json={"kind": "endpoints", "body": {}},
            headers={"X-Console-Token": "old-server-token"},
            timeout=5,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "ConsoleTokenExpired")
        self.assertEqual(len(Upstream.calls), before)

    def test_config_runtime_values_refresh_without_restart(self):
        raw = yaml.safe_load(self.console.path.read_text())
        raw["environment"]["env_api_key"] = {"id": "", "value": ""}
        raw["session"]["id"] = ""
        self.console.path.write_text(yaml.safe_dump(raw))
        self.assertEqual(self.console.bootstrap()["local_keys"], [])
        raw["environment"]["env_api_key"] = {
            "id": "key-one",
            "value": "fresh-environment-secret",
        }
        raw["session"]["id"] = "session-one"
        self.console.path.write_text(yaml.safe_dump(raw))
        boot = requests.get(self.url + "/api/bootstrap", timeout=5).json()
        self.assertEqual(boot["default_session"], "session-one")
        self.assertEqual(boot["local_keys"][0]["id"], "key-one")
        self.assertNotIn("fresh-environment-secret", json.dumps(boot))
        response = self.post("list", {"kind": "sessions", "context": self.ctx})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Upstream.calls[-1][3]["x-api-key"], "fresh-environment-secret")

    def test_config_scope_change_blocks_data_plane_refresh(self):
        raw = yaml.safe_load(self.console.path.read_text())
        raw["volcengine"]["access_key"] = "different-account"
        self.console.path.write_text(yaml.safe_dump(raw))
        self.assertIn("重启", self.console.bootstrap()["config_refresh_error"])
        before = len(Upstream.calls)
        self.assertEqual(
            self.post("list", {"kind": "sessions", "context": self.ctx}).status_code,
            400,
        )
        self.assertEqual(len(Upstream.calls), before)

    def test_runtime_delete_requires_reason_and_forwards_it(self):
        before = len(Upstream.calls)
        body = {"kind": "templates", "id": "runtime-one", "token": "delete-token"}
        for reason in (None, "", "   ", "测" * 342):
            response = self.post("delete", {**body, "reason": reason})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(len(Upstream.calls), before)
        response = self.post("delete", {**body, "reason": "  清理不再使用的模板  "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Upstream.calls[-1][2],
            {
                "RuntimeTemplateId": "runtime-one",
                "Reason": "清理不再使用的模板",
                "ClientToken": "delete-token",
            },
        )

    def test_harness_delete_never_calls_archive(self):
        before = len(Upstream.calls)
        response = self.post(
            "delete", {"kind": "harnesses", "id": "harness-one", "token": "t"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(Upstream.calls), before)
        self.assertEqual(Upstream.rows["harnesses"]["harness-one"]["Status"], "Active")
        archived = self.post(
            "archive", {"kind": "harnesses", "id": "harness-one", "token": "t"}
        )
        self.assertEqual(archived.status_code, 200)
        self.assertEqual(
            Upstream.rows["harnesses"]["harness-one"]["Status"], "Archived"
        )

    def test_session_chat_and_delete_protocol(self):
        body = {
            "agent": {"type": "agent", "id": "harness-one"},
            "environment_id": "env-one",
            "runtime_template_id": "runtime-one",
        }
        response = self.post(
            "create",
            {
                "kind": "sessions",
                "body": body,
                "context": self.ctx,
                "token": "session-token",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        rid = response.json()["id"]
        session_call = [c for c in Upstream.calls if c[1] == "/gateway/v1/sessions"][-1]
        self.assertEqual(session_call[3]["x-api-key"], "local-environment-secret")
        self.assertEqual(session_call[3]["x-ark-key-name"], "model-key-name")
        self.assertEqual(session_call[3]["Idempotency-Key"], "session-token")
        self.assertEqual(
            self.post("list", {"kind": "sessions", "context": self.ctx}).status_code,
            200,
        )
        event = {
            "id": rid,
            "context": self.ctx,
            "prompt": "你好",
            "event_id": "same-event-id",
        }
        sent = self.post("send", event).json()["data"][0]
        self.post("send", event)
        self.assertEqual(len(Upstream.events), 3)
        events = self.post(
            "events", {"id": rid, "context": self.ctx, "after": sent["sequence"]}
        ).json()["data"]
        self.assertEqual(events[-1]["stop_reason"]["type"], "end_turn")
        self.assertEqual(
            self.post(
                "delete", {"kind": "sessions", "id": rid, "context": self.ctx}
            ).status_code,
            200,
        )
        self.assertEqual(
            self.post(
                "get", {"kind": "sessions", "id": rid, "context": self.ctx}
            ).status_code,
            404,
        )
        operations = [(c[0], c[1]) for c in Upstream.calls if rid in c[1]]
        self.assertLess(
            operations.index(("POST", f"/gateway/v1/sessions/{rid}/archive")),
            operations.index(("DELETE", f"/gateway/v1/sessions/{rid}")),
        )

    def test_binding_mismatch_never_sends_secret(self):
        self.ctx["endpoint_id"] = "ep-other"
        self.assertEqual(
            self.post("events", {"id": "session-one", "context": self.ctx}).status_code,
            400,
        )
        self.assertFalse(any("/gateway" in c[1] for c in Upstream.calls))
        self.ctx["endpoint_id"] = "ep-one"
        response = self.post(
            "create",
            {
                "kind": "sessions",
                "body": {"environment_id": "env-other"},
                "context": self.ctx,
                "token": "t",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(any("/gateway" in c[1] for c in Upstream.calls))

    def test_endpoint_delete_rest_or_explicit_unavailable(self):
        response = self.post("delete", {"kind": "endpoints", "id": "ep-one"})
        self.assertEqual(response.status_code, 200)
        call = Upstream.calls[-1]
        self.assertEqual(call[:2], ("DELETE", "/v1/endpoint/ep-one"))
        self.assertIn("Authorization", call[3])
        self.console.rest_base = ""
        self.assertEqual(
            self.post("delete", {"kind": "endpoints", "id": "ep-one"}).status_code, 400
        )

    def test_environment_preset_defaults_and_configured_resources(self):
        for environment_type in ("Cloud", "SelfHosted"):
            raw = copy.deepcopy(self.console.raw)
            raw["environment"]["type"] = environment_type
            raw["environment"].pop("resources")
            config = self.console.make_presets(raw)["environments"]["Config"]
            self.assertEqual(config["Type"], environment_type)
            self.assertEqual(config["Resources"], {"CpuMilli": 2000, "MemoryMb": 4096})
            raw["environment"]["resources"] = {
                "cpu_milli": 4000,
                "memory_mb": 8192,
            }
            config = self.console.make_presets(raw)["environments"]["Config"]
            self.assertEqual(config["Resources"], {"CpuMilli": 4000, "MemoryMb": 8192})

    def test_empty_environment_packages_omitted_without_dropping_real_packages(self):
        self.assertNotIn("Packages", self.boot["presets"]["environments"]["Config"])
        raw = copy.deepcopy(self.console.raw)
        raw["environment"]["package"] = {"npm": ["lodash"], "apt": []}
        preset = self.console.make_presets(raw)["environments"]
        self.assertEqual(preset["Config"]["Packages"], {"Npm": ["lodash"]})
        for packages in ({}, {"Npm": [], "Apt": []}, {"Npm": ["lodash"]}):
            body = {
                "Name": "package-check",
                "Config": {"Type": "Cloud", "Packages": packages},
            }
            result = self.post(
                "create",
                {"kind": "environments", "body": body, "token": "package-test"},
            )
            self.assertEqual(result.status_code, 200, result.text)
            sent = Upstream.calls[-1][2]["Config"]
            if packages.get("Npm"):
                self.assertEqual(sent["Packages"], packages)
            else:
                self.assertNotIn("Packages", sent)

    def test_saved_secret_defaults_do_not_become_mask_strings(self):
        self.console.presets["templates"]["Envs"] = {"API_TOKEN": "runtime-secret"}
        boot = self.console.bootstrap()
        self.assertNotIn("Envs", boot["presets"]["templates"])
        self.console.create(
            "templates", {"Name": "test", "SessionStoreId": "ss-one"}, token="t"
        )
        self.assertEqual(Upstream.calls[-1][2]["Envs"], {"API_TOKEN": "runtime-secret"})
        self.console.create(
            "templates",
            {"Name": "test", "SessionStoreId": "ss-one", "Envs": {}},
            token="t",
        )
        self.assertEqual(Upstream.calls[-1][2]["Envs"], {})

    def test_replayed_key_without_secret_is_not_reported_as_available(self):
        with patch.object(
            self.console.control,
            "call",
            return_value={"ApiKeyId": "replayed-key", "Replayed": True},
        ):
            response = self.post(
                "create", {"kind": "keys", "body": {}, "token": "token"}
            )
        self.assertFalse(response.json()["local_key_available"])

    def test_redacted_mcp_credentials_round_trip(self):
        self.console.presets["harnesses"]["McpServers"] = [
            {"Name": "mcp", "Headers": {"Authorization": "sensitive-credential"}}
        ]
        body = self.console.bootstrap()["presets"]["harnesses"]
        self.assertNotIn("sensitive-credential", json.dumps(body))
        body["Name"] = "custom-name"
        self.console.create("harnesses", body, token="token")
        self.assertEqual(
            Upstream.calls[-1][2]["McpServers"][0]["Headers"]["Authorization"],
            "sensitive-credential",
        )
        self.assertEqual(Upstream.calls[-1][2]["Name"], "custom-name")

    def test_malformed_upstream_and_repeated_cursor_are_errors(self):
        with patch.object(
            self.console.control,
            "call",
            return_value={"Items": [], "NextToken": "loop"},
        ):
            self.assertEqual(
                self.post("list", {"kind": "keys", "cursor": "loop"}).status_code, 400
            )
        with patch.object(self.console.control, "call", return_value={}):
            self.assertNotEqual(self.post("list", {"kind": "keys"}).status_code, 200)


if __name__ == "__main__":
    unittest.main()
