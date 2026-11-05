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
from _clients import ControlConfig, HarnessInfraError
from _tls import TlsClient


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
        self.options.update(tls_project_id="project-1", tls_topic_id="topic-1")
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

    def test_default_observability_on_both_resources(self) -> None:
        """未配置观测选项时，两个创建接口都明确开启应用监控和日志采集。"""
        requests = [
            backend.tool_request(self.options, "token", "tool"),
            backend.runtime_request(
                self.options, self.conn, "cn-beijing", "tool-1", "token", "runtime"
            ),
        ]
        for body in requests:
            with self.subTest(name=body["Name"]):
                self.assertIs(body["ApmplusEnable"], True)
                self.assertEqual(
                    body["TlsConfiguration"],
                    {
                        "EnableLog": True,
                        "TlsProjectId": "project-1",
                        "TlsTopicId": "topic-1",
                    },
                )

    def test_observability_can_be_disabled_independently(self) -> None:
        """用户可分别关闭应用监控或日志采集，两个请求都保留显式 false。"""
        for apmplus, enable_log in ((False, True), (True, False), (False, False)):
            with (
                self.subTest(apmplus=apmplus, enable_log=enable_log),
                patch.object(
                    backend,
                    "_read_yaml",
                    return_value={
                        "self_host": {
                            "agentkit_sandbox": {
                                "apmplus_enable": apmplus,
                                "enable_log": enable_log,
                            }
                        }
                    },
                ),
            ):
                options = backend.settings()
                options.update(tls_project_id="project-1", tls_topic_id="topic-1")
                requests = [
                    backend.tool_request(options, "token", "tool"),
                    backend.runtime_request(
                        options, self.conn, "cn-beijing", "tool-1", "token", "runtime"
                    ),
                ]
                for body in requests:
                    self.assertIs(body["ApmplusEnable"], apmplus)
                    self.assertIs(body["TlsConfiguration"]["EnableLog"], enable_log)
                    if not enable_log:
                        self.assertEqual(body["TlsConfiguration"], {"EnableLog": False})

    def test_tls_configuration_requires_complete_ids(self) -> None:
        """未准备日志资源时禁止生成会被线上接口拒绝的日志开启请求。"""
        with patch.object(backend, "_read_yaml", return_value={}):
            options = backend.settings()
        self.assertEqual(options["tls_project_id"], "")
        self.assertEqual(options["tls_topic_id"], "")
        with self.assertRaisesRegex(RuntimeError, "prepare TLS"):
            backend.tool_request(options, "token", "tool")
        for name in ("tls_project_id", "tls_topic_id"):
            with (
                self.subTest(name=name),
                patch.object(
                    backend,
                    "_read_yaml",
                    return_value={"self_host": {"agentkit_sandbox": {name: "id-1"}}},
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "set both"):
                    backend.settings()

    def test_tls_creation_resumes_after_ambiguous_topic_create(self) -> None:
        """项目创建后主题响应丢失，重跑按名称找回主题并保持两个资源的归属。"""
        options = {**self.options, "tls_project_id": "", "tls_topic_id": ""}
        state = backend.deployment_state(self.client, options)
        with patch.object(backend, "TlsClient") as constructor:
            tls = constructor.return_value
            tls.call.side_effect = [
                {"Projects": []},
                {"ProjectId": "project-1"},
                {"Topics": []},
                RuntimeError("network"),
            ]
            with self.assertRaisesRegex(RuntimeError, "network"):
                backend.ensure_tls(
                    SimpleNamespace(region="cn-beijing"),
                    options,
                    state,
                    json_output=True,
                )
            recovered = json.loads(self.path.read_text())
            self.assertEqual(recovered["tls"]["project"]["id"], "project-1")
            self.assertNotIn("topic", recovered["tls"])
            tls.call.reset_mock()
            tls.call.side_effect = [
                {
                    "Topics": [
                        {
                            "TopicName": f"{state['names']['runtime']}-logs",
                            "TopicId": "topic-1",
                            "Description": (
                                f"AgentKit SelfHosted backend {state['names']['runtime']}"
                            ),
                        }
                    ]
                }
            ]
            prepared = backend.ensure_tls(
                SimpleNamespace(region="cn-beijing"),
                options,
                recovered,
                json_output=True,
            )
            tls.call.assert_called_once()
            self.assertEqual(tls.call.call_args.args[0], "DescribeTopics")
            self.assertEqual(prepared["tls_topic_id"], "topic-1")
            self.assertTrue(recovered["tls"]["project"]["owned"])
            self.assertTrue(recovered["tls"]["topic"]["owned"])
            tls.call.reset_mock()
            backend.ensure_tls(
                SimpleNamespace(region="cn-beijing"),
                options,
                recovered,
                json_output=True,
            )
            tls.call.assert_not_called()

    def test_tls_configured_resources_require_matching_ownership(self) -> None:
        """已有主题必须属于指定 TLS 项目，TLS 项目也必须属于目标 IAM 项目。"""
        for iam_project, topic_project in (
            ("default", "project-1"),
            ("other", "project-1"),
            ("default", "project-other"),
        ):
            with (
                self.subTest(iam_project=iam_project, topic_project=topic_project),
                patch.object(backend, "TlsClient") as constructor,
            ):
                state = backend.deployment_state(self.client, self.options)
                constructor.return_value.call.side_effect = [
                    {"ProjectId": "project-1", "IamProjectName": iam_project},
                    {"TopicId": "topic-1", "ProjectId": topic_project},
                ]
                if iam_project == "default" and topic_project == "project-1":
                    prepared = backend.ensure_tls(
                        None, self.options, state, json_output=True
                    )
                    self.assertEqual(prepared["tls_topic_id"], "topic-1")
                    self.assertFalse(state["tls"]["topic"]["owned"])
                else:
                    with self.assertRaisesRegex(RuntimeError, "must belong"):
                        backend.ensure_tls(None, self.options, state, json_output=True)

    def test_tls_disabled_does_not_create_client_or_state(self) -> None:
        """关闭日志时不调用 TLS，且不增加日志资源状态。"""
        options = {**self.options, "enable_log": False}
        state = backend.deployment_state(self.client, options)
        with patch.object(backend, "TlsClient") as constructor:
            self.assertIs(
                backend.ensure_tls(None, options, state, json_output=True), options
            )
        constructor.assert_not_called()
        self.assertNotIn("tls", state)

    def test_tls_name_collision_is_not_claimed(self) -> None:
        """同名资源不属于当前部署时拒绝复用，避免将他人资源登记为自有。"""
        options = {**self.options, "tls_project_id": "", "tls_topic_id": ""}
        state = backend.deployment_state(self.client, options)
        with patch.object(backend, "TlsClient") as constructor:
            constructor.return_value.call.return_value = {
                "Projects": [
                    {
                        "ProjectName": f"{state['names']['runtime']}-logs",
                        "Description": "unrelated",
                        "ProjectId": "other-project",
                    }
                ]
            }
            with self.assertRaisesRegex(RuntimeError, "name collision"):
                backend.ensure_tls(None, options, state, json_output=True)
            self.assertEqual(constructor.return_value.call.call_count, 1)
        self.assertNotIn("project", state["tls"])

    def test_tls_missing_name_is_created_but_other_errors_propagate(self) -> None:
        """名称查询的资源不存在可进入创建；权限失败不得被误判为资源缺失。"""
        options = {**self.options, "tls_project_id": "", "tls_topic_id": ""}
        state = backend.deployment_state(self.client, options)
        with patch.object(backend, "TlsClient") as constructor:
            tls = constructor.return_value
            tls.call.side_effect = [
                HarnessInfraError(
                    "TLS DescribeProjects", "ProjectNotExists", "", status_code=404
                ),
                {"ProjectId": "project-1"},
                HarnessInfraError(
                    "TLS DescribeTopics", "TopicNotExist", "", status_code=404
                ),
                {"TopicID": "topic-1"},
            ]
            prepared = backend.ensure_tls(
                SimpleNamespace(region="cn-beijing"), options, state, json_output=True
            )
            self.assertEqual(prepared["tls_topic_id"], "topic-1")
            self.assertEqual(
                [call.args[0] for call in tls.call.call_args_list],
                ["DescribeProjects", "CreateProject", "DescribeTopics", "CreateTopic"],
            )
            state.pop("tls")
            tls.call.reset_mock()
            tls.call.side_effect = HarnessInfraError(
                "TLS DescribeProjects", "AccessDenied", "", status_code=403
            )
            with self.assertRaises(HarnessInfraError):
                backend.ensure_tls(None, options, state, json_output=True)
            self.assertEqual(tls.call.call_count, 1)

    def test_tls_selection_change_rejected_before_network(self) -> None:
        """已持久化的日志选择器变化时拒绝重跑，不创建额外资源。"""
        state = backend.deployment_state(self.client, self.options)
        state["tls"] = {"selection": {"project_id": "", "topic_id": ""}}
        with patch.object(backend, "TlsClient") as constructor:
            with self.assertRaisesRegex(RuntimeError, "TLS configuration changed"):
                backend.ensure_tls(None, self.options, state, json_output=True)
        constructor.assert_not_called()

    def test_observability_rejects_non_boolean_configuration(self) -> None:
        """拒绝字符串或数字开关，避免将字符串 false 当作真值开启采集。"""
        for name in ("apmplus_enable", "enable_log"):
            for value in ("false", 0, 1, None):
                with (
                    self.subTest(name=name, value=value),
                    patch.object(
                        backend,
                        "_read_yaml",
                        return_value={"self_host": {"agentkit_sandbox": {name: value}}},
                    ),
                ):
                    with self.assertRaisesRegex(RuntimeError, f"{name}.*boolean"):
                        backend.settings()

    def test_creation_reports_actual_observability(self) -> None:
        """即使请求开启观测，就绪输出也以查询结果为准，不宣称已经开启。"""
        for kind in ("tool", "runtime"):
            with self.subTest(kind=kind):
                state = backend.deployment_state(self.client, self.options)
                resource = "Tool" if kind == "tool" else "Runtime"
                body = (
                    backend.tool_request(self.options, "token", "tool")
                    if kind == "tool"
                    else backend.runtime_request(
                        self.options,
                        self.conn,
                        "cn-beijing",
                        "tool-1",
                        "token",
                        "runtime",
                    )
                )
                self.client.call.return_value = {f"{resource}Id": f"{kind}-1"}
                with (
                    patch.object(
                        backend,
                        "wait_until",
                        return_value={
                            "Status": "Ready",
                            "ApmplusEnable": False,
                            "TlsConfiguration": {"EnableLog": False},
                        },
                    ),
                    patch.object(backend, "emit") as emit,
                ):
                    backend.ensure_resource(
                        self.client, state, kind, body, json_output=True
                    )
                events = [
                    call
                    for call in emit.call_args_list
                    if call.args[0] == "observability"
                ]
                self.assertEqual(len(events), 2)
                self.assertIn("为了方便观测", events[0].args[1])
                self.assertIs(events[0].kwargs["planned"], True)
                self.assertIs(events[0].kwargs["apmplus_enable"], True)
                self.assertIs(events[0].kwargs["enable_log"], True)
                self.assertIs(events[1].kwargs["planned"], False)
                self.assertIs(events[1].kwargs["apmplus_enable"], False)
                self.assertIs(events[1].kwargs["enable_log"], False)

    def test_missing_observability_is_reported_as_unknown(self) -> None:
        """查询未返回配置时显示未知，禁止套用本地默认开关。"""
        with patch.object(backend, "emit") as emit:
            backend.emit_observability(
                "Tool", {"TlsConfiguration": None}, json_output=True
            )
        self.assertIn("未返回", emit.call_args.args[1])
        self.assertNotIn("默认", emit.call_args.args[1])
        self.assertIsNone(emit.call_args.kwargs["apmplus_enable"])
        self.assertIsNone(emit.call_args.kwargs["enable_log"])

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
            patch.object(backend, "TlsClient") as tls,
            patch.object(backend, "write_backend") as write,
            patch.object(backend, "emit") as emit,
        ):
            backend.main(dispatcher=True)
        client.assert_not_called()
        tls.assert_not_called()
        write.assert_not_called()
        self.assertFalse(self.path.exists())
        events = [
            call for call in emit.call_args_list if call.args[0] == "observability"
        ]
        self.assertEqual(
            [call.kwargs["resource"] for call in events], ["Tool", "Runtime"]
        )
        for event in events:
            self.assertIs(event.kwargs["planned"], True)
            self.assertIn("默认", event.args[1])

    def test_dry_run_tls_plan_matches_creation_or_reuse(self) -> None:
        """自动日志列入创建计划；只复用 Tool 时无需准备新的日志资源。"""
        for dispatcher, existing, expected in (
            (False, "", ["PrepareTls", "CreateTool"]),
            (True, "", ["PrepareTls", "CreateTool", "CreateRuntime"]),
            (False, "tool-existing", ["GetTool"]),
            (True, "tool-existing", ["PrepareTls", "GetTool", "CreateRuntime"]),
        ):
            options = {
                **self.options,
                "tls_project_id": "",
                "tls_topic_id": "",
                "existing_tool_id": existing,
            }
            with (
                self.subTest(dispatcher=dispatcher, existing=existing),
                patch("sys.argv", ["backend.py", "--dry-run", "--json"]),
                patch.object(
                    backend,
                    "validated_config",
                    return_value=SimpleNamespace(
                        control=SimpleNamespace(region="cn-beijing"),
                        environment=SimpleNamespace(type="SelfHosted"),
                        session=SimpleNamespace(endpoint_base_url=""),
                    ),
                ),
                patch.object(backend, "settings", return_value=options),
                patch.dict(os.environ, {}, clear=True),
                patch.object(backend, "TopClient") as client,
                patch.object(backend, "TlsClient") as tls,
                patch.object(backend, "write_backend") as write,
                patch.object(backend, "emit") as emit,
            ):
                backend.main(dispatcher=dispatcher)
            client.assert_not_called()
            tls.assert_not_called()
            write.assert_not_called()
            plan = emit.call_args_list[0].kwargs["actions"]
            self.assertEqual([item["action"] for item in plan], expected)
            for item in plan:
                if item["action"].startswith("Create"):
                    self.assertEqual(
                        item["body"]["TlsConfiguration"]["TlsTopicId"], "<TlsTopicId>"
                    )

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
            "ApmplusEnable": False,
            "TlsConfiguration": {"EnableLog": True},
        }
        with patch.object(backend, "emit") as emit:
            tool_id = backend.reuse_tool(self.client, state, options, json_output=True)
        self.assertEqual(tool_id, "tool-existing")
        self.client.call.assert_called_once_with("GetTool", {"ToolId": tool_id})
        self.assertFalse(state["resources"]["tool"]["owned"])
        self.assertEqual(emit.call_args.args[0], "observability")
        self.assertIs(emit.call_args.kwargs["planned"], False)
        self.assertIs(emit.call_args.kwargs["apmplus_enable"], False)
        self.assertIs(emit.call_args.kwargs["enable_log"], True)

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


class TlsClientTests(unittest.TestCase):
    """校验原生 TLS 请求协议及安全错误边界。"""

    def setUp(self) -> None:
        """使用合成凭据构造 TLS 客户端，避免依赖环境变量。"""
        self.client = TlsClient(
            ControlConfig("test-ak", "test-sk", "cn-beijing", "agentkit", "control")
        )

    def test_rest_path_query_and_tls_signing(self) -> None:
        """GET 使用原生路径和查询参数，按 TLS 服务签名并禁止重定向。"""
        response = Mock(status_code=200, headers={})
        response.json.return_value = {"Projects": []}
        with patch("_tls.requests.request", return_value=response) as request:
            self.client.call("DescribeProjects", {"ProjectName": "logs"}, method="GET")
        args, kwargs = request.call_args
        self.assertEqual(
            args, ("GET", "https://tls-cn-beijing.volces.com/DescribeProjects")
        )
        self.assertEqual(kwargs["params"], {"ProjectName": "logs"})
        self.assertEqual(kwargs["data"], b"{}")
        self.assertIn("/cn-beijing/TLS/request", kwargs["headers"]["Authorization"])
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["headers"]["x-tls-apiversion"], "0.3.0")

    def test_flat_tls_errors_preserve_request_id(self) -> None:
        """TLS 的扁平错误只输出错误码和请求标识，不泄露任意响应字段。"""
        response = Mock(status_code=403, headers={"x-tls-requestid": "request-1"})
        response.json.return_value = {
            "ErrorCode": "AccessDenied",
            "ErrorMessage": "permission denied",
            "Credential": "must-not-leak",
        }
        with patch("_tls.requests.request", return_value=response):
            with self.assertRaises(HarnessInfraError) as raised:
                self.client.call("CreateProject", {})
        self.assertEqual(raised.exception.request_id, "request-1")
        self.assertEqual(raised.exception.code, "AccessDenied")
        self.assertNotIn("must-not-leak", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
