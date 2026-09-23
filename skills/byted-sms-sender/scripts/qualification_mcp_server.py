# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
"""Stdio MCP server for SMS actions and the qualification MCP App."""

from __future__ import annotations

import io
import json
import queue
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, TextIO

from api_client import SmsApiClient, sanitize_output
from action_contracts import PUBLIC_QUERY_ACTIONS
from batch_wizard import run_batch_wizard
from qualification_display import browser_display_adapter, callback_display_adapter
from qualification_upload import QualificationUploadError
from qualification_wizard import run_qualification_wizard
import sms_cli


APP_VERSION = "1.9.4"
APP_RESOURCE_URI = "ui://volcengine-sms/qualification-v3.html"
APP_MIME_TYPE = "text/html;profile=mcp-app"
APP_TOOL_META = {
    "ui": {"resourceUri": APP_RESOURCE_URI},
    "ui/resourceUri": APP_RESOURCE_URI,
    "workbuddy": {"ui": {"launchSurface": "panel"}},
}
APP_TEMPLATE = (
    Path(__file__).resolve().parents[1] / "assets" / "private_form_mcp_app.html"
).read_text(encoding="utf-8")


def form_app_html(display_key: str, ready_event: str, finished_event: str, result_tool: str) -> str:
    config = {
        "displayKey": display_key, "readyEvent": ready_event,
        "finishedEvent": finished_event, "resultTool": result_tool,
        "version": APP_VERSION,
    }
    return APP_TEMPLATE.replace("__FORM_CONFIG_JSON__", json.dumps(config, ensure_ascii=False))


APP_HTML = form_app_html(
    "qualificationDisplay", "qualification:wizard-ready",
    "qualification:wizard-finished", "get_qualification_application_result",
)
BATCH_RESOURCE_URI = "ui://volcengine-sms/batch-creation-v1.html"
BATCH_APP_HTML = form_app_html(
    "batchDisplay", "batch:wizard-ready", "batch:wizard-finished",
    "get_batch_task_creation_result",
)
BATCH_TOOL_META = {
    "ui": {"resourceUri": BATCH_RESOURCE_URI},
    "ui/resourceUri": BATCH_RESOURCE_URI,
    "workbuddy": {"ui": {"launchSurface": "panel"}},
}
FORM_RESOURCES = {
    APP_RESOURCE_URI: ("火山引擎短信资质表单", APP_HTML),
    BATCH_RESOURCE_URI: ("火山引擎短信群发任务表单", BATCH_APP_HTML),
}
QUALIFICATION_FLOW_PROTOCOL = {
    "failed": "qualification_application_failed",
    "not_found": {"status": "qualification_application_not_found", "code": "qualification_flow_not_found"},
    "not_ready": {"status": "qualification_application_not_ready", "code": "qualification_flow_not_ready"},
    "panel_unavailable": "qualification_panel_not_visible",
    "browser_unavailable": "qualification_browser_not_visible",
    "cancelling": "qualification_application_cancelling",
    "browser_tool": "open_qualification_application_in_browser",
}
BATCH_FLOW_PROTOCOL = {
    "failed": "batch_creation_failed",
    "not_found": {"status": "batch_form_not_found", "code": "batch_flow_not_found"},
    "not_ready": {"status": "batch_form_not_ready", "code": "batch_flow_not_ready"},
    "panel_unavailable": "batch_panel_not_visible",
    "browser_unavailable": "batch_browser_not_visible",
    "cancelling": "batch_form_cancelling",
    "browser_tool": "open_batch_task_creation_in_browser",
}
FLOW_RESULT_TTL_SECONDS = 30 * 60
FLOW_SHUTDOWN_WAIT_SECONDS = 2
DISPLAY_READY_WAIT_SECONDS = 8
READ_ACTIONS = {
    "account-info",
    "api-read",
    "auth-doctor",
    "runtime-info",
    "batch-content-check",
    "batch-detail",
    "batch-list",
    "batch-precheck",
    "batch-template-demo",
    "list-message-groups",
    "list-qualifications",
    "list-signatures",
    "list-templates",
    "match-template",
    "message-group-detail",
    "send-preview",
    "send-status",
    "signature-preview",
    "template-preview",
}
WRITE_ACTIONS = {
    "batch-cancel",
    "batch-create",
    "batch-launch-preview",
    "batch-launch-submit",
    "send-submit",
    "signature-submit",
    "template-submit",
}


ClientFactory = Callable[[], SmsApiClient]


def _emit_mcp_app_event(event: str, **fields: Any) -> None:
    payload = {"event": event}
    payload.update(fields)
    sys.stderr.write(
        "QUALIFICATION_MCP_APP "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + "\n"
    )
    sys.stderr.flush()


@dataclass
class QualificationFlow:
    flow_id: str
    ready: "queue.Queue[object]" = field(default_factory=queue.Queue)
    thread: Optional[threading.Thread] = None
    url: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    display_ready: threading.Event = field(default_factory=threading.Event)
    display_mode: str = "mcp-app"
    finished_at: Optional[float] = None
    parameters: Dict[str, Any] = field(default_factory=dict)


class PrivateFormFlowManager:
    def __init__(self, client_factory: ClientFactory, *, runner: Callable, protocol: Mapping[str, Any]) -> None:
        self._client_factory = client_factory
        self._runner = runner
        self._protocol = protocol
        self._flows: Dict[str, QualificationFlow] = {}
        self._lock = threading.Lock()

    def _prune_finished(self) -> None:
        cutoff = time.monotonic() - FLOW_RESULT_TTL_SECONDS
        with self._lock:
            stale = [
                flow_id
                for flow_id, flow in self._flows.items()
                if flow.finished_at is not None and flow.finished_at <= cutoff
            ]
            for flow_id in stale:
                self._flows.pop(flow_id, None)

    def _active_flow(self) -> Optional[QualificationFlow]:
        for flow in self._flows.values():
            if (
                flow.thread is not None
                and flow.thread.is_alive()
                and flow.url
                and not flow.cancel_event.is_set()
            ):
                return flow
        return None

    def start(self, parameters: Optional[Mapping[str, Any]] = None) -> QualificationFlow:
        parameters = dict(parameters or {})
        self._prune_finished()
        with self._lock:
            active = self._active_flow()
            if active is not None:
                if active.parameters != parameters:
                    raise ValueError("Another form with different parameters is already open")
                _emit_mcp_app_event("flow_reused", flowId=active.flow_id)
                return active
            flow = QualificationFlow(uuid.uuid4().hex, parameters=parameters)
            self._flows[flow.flow_id] = flow
            _emit_mcp_app_event("flow_created", flowId=flow.flow_id)

        def present(url: str) -> None:
            with self._lock:
                flow.url = url
            _emit_mcp_app_event("flow_ready", flowId=flow.flow_id)
            flow.ready.put(url)

        def display_ready() -> None:
            if flow.display_ready.is_set():
                return
            flow.display_ready.set()
            _emit_mcp_app_event(
                "display_ready",
                flowId=flow.flow_id,
                mode=flow.display_mode,
            )

        def run() -> None:
            client = None
            try:
                client = self._client_factory()
                result = self._runner(
                    client,
                    **flow.parameters,
                    display=callback_display_adapter(
                        present,
                        name="mcp-app",
                        allows_embedding=True,
                    ),
                    cancel_event=flow.cancel_event,
                    on_display_ready=display_ready,
                )
                with self._lock:
                    flow.result = dict(result)
            except (QualificationUploadError, sms_cli.CliError) as error:
                with self._lock:
                    flow.error = {
                        "status": self._protocol["failed"],
                        "code": error.code,
                        "requestId": error.request_id,
                        "logId": error.log_id,
                        "outcomeUnknown": error.outcome_unknown,
                    }
                if flow.url is None:
                    # The worker owns the credentials; redact before handing an error to MCP.
                    secrets = tuple(getattr(client, "output_secrets", ()))
                    message = sanitize_output(str(error), secrets=secrets)
                    diagnostics = {
                        "request_id": error.request_id, "log_id": error.log_id,
                        "outcome_unknown": error.outcome_unknown,
                    }
                    public_error = sms_cli.CliError(
                        message, error.code, retryable=getattr(error, "retryable", False),
                        remediation=sanitize_output(getattr(error, "remediation", None), secrets=secrets),
                        **diagnostics,
                    )
                    flow.ready.put(public_error)
            except Exception:
                with self._lock:
                    flow.error = {
                        "status": self._protocol["failed"],
                        "code": "internal_error",
                        "outcomeUnknown": False,
                    }
                if flow.url is None:
                    flow.ready.put(RuntimeError("Private form failed"))
            finally:
                with self._lock:
                    flow.url = None
                    flow.finished_at = time.monotonic()

        flow.thread = threading.Thread(target=run, daemon=True)
        flow.thread.start()
        try:
            ready = flow.ready.get(timeout=60)
        except queue.Empty:
            flow.cancel_event.set()
            raise
        if isinstance(ready, BaseException):
            raise ready
        return flow

    def result(
        self,
        flow_id: str,
        *,
        wait_for_display_seconds: float = 0,
    ) -> Dict[str, Any]:
        self._prune_finished()
        with self._lock:
            flow = self._flows.get(flow_id)
        if flow is None:
            return {**self._protocol["not_found"], "completed": True}
        if wait_for_display_seconds > 0 and not flow.display_ready.is_set():
            flow.display_ready.wait(timeout=wait_for_display_seconds)
        with self._lock:
            if flow.result is not None:
                return {**flow.result, "completed": True}
            if flow.error is not None:
                return {**flow.error, "completed": True}
            return {
                "completed": False,
                "status": (
                    "waiting_for_customer"
                    if flow.display_ready.is_set()
                    else "waiting_for_display"
                ),
                "displayStatus": (
                    "opened" if flow.display_ready.is_set() else "waiting_for_host"
                ),
                "displayMode": flow.display_mode,
            }

    def ensure_visible(self, flow_id: str) -> Dict[str, Any]:
        result = self.result(
            flow_id,
            wait_for_display_seconds=DISPLAY_READY_WAIT_SECONDS,
        )
        if result.get("status") != "waiting_for_display":
            return result
        return {
            "status": self._protocol["panel_unavailable"],
            "displayStatus": "not_opened",
            "displayMode": "mcp-app",
            "code": self._protocol["panel_unavailable"],
            "preferredFallback": {
                "displayMode": "host",
                "requires": "local_url_preview",
                "cancelCurrentFlow": True,
            },
            "browserFallbackTool": self._protocol["browser_tool"],
            "browserFallbackArguments": {"flowId": flow_id},
        }

    def open_in_browser(self, flow_id: str) -> Dict[str, Any]:
        self._prune_finished()
        with self._lock:
            flow = self._flows.get(flow_id)
            if flow is None:
                return {**self._protocol["not_found"], "completed": True}
            if flow.finished_at is not None:
                if flow.result is not None:
                    return {**flow.result, "completed": True}
                if flow.error is not None:
                    return {**flow.error, "completed": True}
            url = flow.url
            if not url:
                return dict(self._protocol["not_ready"])
            flow.display_mode = "browser"

        browser_display_adapter().present(url)
        _emit_mcp_app_event("browser_open_requested", flowId=flow_id)
        result = self.result(
            flow_id,
            wait_for_display_seconds=DISPLAY_READY_WAIT_SECONDS,
        )
        if result.get("status") != "waiting_for_display":
            return result
        return {
            "status": self._protocol["browser_unavailable"],
            "displayStatus": "not_opened",
            "displayMode": "browser",
            "code": self._protocol["browser_unavailable"],
        }

    def cancel(self, flow_id: str) -> Dict[str, Any]:
        with self._lock:
            flow = self._flows.get(flow_id)
            if flow is None:
                return {**self._protocol["not_found"], "completed": True}
            if flow.finished_at is not None:
                if flow.result is not None:
                    return {**flow.result, "completed": True}
                if flow.error is not None:
                    return {**flow.error, "completed": True}
            flow.cancel_event.set()
            worker = flow.thread
        if worker is not None:
            worker.join(timeout=FLOW_SHUTDOWN_WAIT_SECONDS)
        if flow.finished_at is not None:
            return self.result(flow_id)
        return {"status": self._protocol["cancelling"], "completed": False, "fallbackAllowed": False}

    def cancel_all(self) -> None:
        with self._lock:
            flows = list(self._flows.values())
            for flow in flows:
                flow.cancel_event.set()
        for flow in flows:
            if flow.thread is not None and flow.thread.is_alive():
                flow.thread.join(timeout=FLOW_SHUTDOWN_WAIT_SECONDS)


class QualificationFlowManager(PrivateFormFlowManager):
    def __init__(self, client_factory: ClientFactory = SmsApiClient) -> None:
        super().__init__(client_factory, runner=run_qualification_wizard, protocol=QUALIFICATION_FLOW_PROTOCOL)


def _run_batch_form(client: SmsApiClient, *, display, cancel_event, on_display_ready, **parameters):
    flags = {
        "subAccount": "--sub-account", "taskName": "--task-name",
        "signature": "--signature", "templateId": "--template-id",
        "content": "--content", "sendTime": "--send-time",
    }
    if set(parameters) - (set(flags) | {"scheduled"}):
        raise ValueError("Unknown batch form fields")
    argv = ["batch-wizard"]
    for name, flag in flags.items():
        if name in parameters:
            if not isinstance(parameters[name], str) or not parameters[name]:
                raise ValueError("Batch form fields must be non-empty strings")
            argv.append(flag + "=" + parameters[name])
    if "scheduled" in parameters:
        scheduled = parameters["scheduled"]
        if not isinstance(scheduled, bool):
            raise ValueError("scheduled must be boolean")
        argv.append("--scheduled" if scheduled else "--immediate")
    args = sms_cli.build_parser().parse_args(argv)
    draft = sms_cli.BatchFormDraft(client, args)
    return run_batch_wizard(draft, display=display, cancel_event=cancel_event, on_display_ready=on_display_ready)


def _batch_form_tools() -> List[Dict[str, Any]]:
    properties = {
        "subAccount": {"type": "string", "minLength": 1,
                       "description": "消息组 ID，取模板 SubAccounts；All 范围时从 GetSubAccountListForAgent 返回的 subAccountId 选择"},
        "taskName": {"type": "string", "minLength": 1},
        "signature": {"type": "string", "minLength": 1},
        "templateId": {"type": "string", "minLength": 1},
        "content": {"type": "string", "minLength": 1},
        "scheduled": {"type": "boolean", "description": "会话中确认的发送方式：false 立即发送，true 定时发送"},
        "sendTime": {"type": "string", "description": "会话确认的定时时间，ISO 8601（Asia/Shanghai，+08:00）；定时发送时传入，页面可核对和修改"},
    }
    tools = [{
        "name": "open_batch_task_creation",
        "title": "打开群发任务私密表单",
        "description": "先在会话中确认客户想何时发送，再按已确定的模板、正文、消息组和发送时间打开群发表单。立即发送传 scheduled=false；定时发送传 scheduled=true 和 sendTime。页面预填该选择，客户下载名单模板、选择手机号 CSV、核对后最终确认。模板声明任务级正文时传入 content。",
        "inputSchema": {
            "type": "object", "properties": properties,
            "required": ["subAccount", "taskName", "signature", "templateId"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
        "_meta": BATCH_TOOL_META,
    }]
    for name, title, description, read_only, destructive, idempotent in (
        ("ensure_batch_task_creation_visible", "确认群发表单可见", "确认表单已完成渲染；未显示时按 Skill 关闭流程并回退。", True, False, True),
        ("open_batch_task_creation_in_browser", "在浏览器继续群发表单", "复用同一私密表单在系统浏览器展示。", False, False, False),
        ("get_batch_task_creation_result", "查询群发表单结果", "只返回任务状态、人数和文件摘要，不返回名单或私密地址。", True, False, True),
        ("cancel_batch_task_creation", "关闭群发表单", "关闭未提交的本机草稿。只有返回 fallbackAllowed=true 才可改走现有创建流程；不撤销已创建任务。", False, True, True),
    ):
        tools.append({
            "name": name, "title": title, "description": description,
            "inputSchema": {"type": "object", "properties": {"flowId": {"type": "string", "minLength": 1}}, "required": ["flowId"], "additionalProperties": False},
            "annotations": {"readOnlyHint": read_only, "destructiveHint": destructive, "idempotentHint": idempotent, "openWorldHint": False},
        })
    return tools



class QualificationMcpServer:
    def __init__(self, flow_manager: Optional[QualificationFlowManager] = None, batch_flow_manager: Optional[PrivateFormFlowManager] = None) -> None:
        self._flows = flow_manager or QualificationFlowManager()
        self._batch_flows = batch_flow_manager or PrivateFormFlowManager(
            SmsApiClient, runner=_run_batch_form, protocol=BATCH_FLOW_PROTOCOL
        )

    @staticmethod
    def _tool_result(
        text: str,
        structured: Mapping[str, Any],
        *,
        private_meta: Optional[Mapping[str, Any]] = None,
        is_error: bool = False,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "content": [{"type": "text", "text": text}],
            "structuredContent": dict(structured),
        }
        if is_error:
            result["isError"] = True
        if private_meta is not None:
            result["_meta"] = dict(private_meta)
        return result

    @staticmethod
    def _tools() -> List[Dict[str, Any]]:
        return [
            {
                "name": "open_qualification_application",
                "title": "打开火山引擎短信资质表单",
                "description": "在私密表单中创建短信资质；敏感材料不会进入对话。",
                "inputSchema": {"type": "object", "properties": {}},
                "annotations": {
                    "readOnlyHint": False,
                    "destructiveHint": False,
                    "idempotentHint": False,
                    "openWorldHint": True,
                },
                "_meta": dict(APP_TOOL_META),
            },
            {
                "name": "ensure_qualification_application_visible",
                "title": "确认短信资质表单可见",
                "description": "等待并确认右侧面板是否已加载，不打开其他窗口。",
                "inputSchema": {
                    "type": "object",
                    "properties": {"flowId": {"type": "string"}},
                    "required": ["flowId"],
                    "additionalProperties": False,
                },
                "annotations": {
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": False,
                },
            },
            {
                "name": "open_qualification_application_in_browser",
                "title": "在系统浏览器打开短信资质表单",
                "description": (
                    "仅当 MCP App 面板不可用且宿主没有本机 URL 内置预览能力时，"
                    "在系统默认浏览器打开同一个本机私密资质表单。"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {"flowId": {"type": "string"}},
                    "required": ["flowId"],
                    "additionalProperties": False,
                },
                "annotations": {
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": False,
                    "openWorldHint": True,
                },
            },
            {
                "name": "get_qualification_application_result",
                "title": "查询资质表单结果",
                "description": "读取当前私密资质表单的安全状态。",
                "inputSchema": {
                    "type": "object",
                    "properties": {"flowId": {"type": "string"}},
                    "required": ["flowId"],
                    "additionalProperties": False,
                },
                "annotations": {
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": False,
                },
            },
            {
                "name": "cancel_qualification_application",
                "title": "取消短信资质表单",
                "description": "关闭尚未提交的私密资质表单并清除本地草稿。",
                "inputSchema": {
                    "type": "object",
                    "properties": {"flowId": {"type": "string"}},
                    "required": ["flowId"],
                    "additionalProperties": False,
                },
                "annotations": {
                    "readOnlyHint": False,
                    "destructiveHint": True,
                    "idempotentHint": True,
                    "openWorldHint": False,
                },
            },
            {
                "name": "execute_sms_read_action",
                "title": "执行短信查询或预览",
                "description": (
                    "执行火山引擎短信只读查询、本地校验或不写入数据的操作预览。"
                    "查询传 action 和接口原生 params；本地预览等命令使用 argv。"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": sorted(PUBLIC_QUERY_ACTIONS)},
                        "params": {"type": "object"},
                        "argv": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                        }
                    },
                    "oneOf": [{"required": ["argv"]}, {"required": ["action", "params"]}],
                    "additionalProperties": False,
                },
                "annotations": {
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": True,
                },
            },
            {
                "name": "execute_sms_write_action",
                "title": "执行已授权的短信写操作",
                "description": (
                    "执行短信预览所需的名单上传，或已按 Skill 完成预览和客户确认的"
                    "短信申请、发送或任务写操作。"
                    "argv 使用 Skill 中 sms_cli.py 命令之后的参数。"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "argv": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                        }
                    },
                    "required": ["argv"],
                    "additionalProperties": False,
                },
                "annotations": {
                    "readOnlyHint": False,
                    "destructiveHint": True,
                    "idempotentHint": False,
                    "openWorldHint": True,
                },
            },
        ] + _batch_form_tools()

    @staticmethod
    def _execute_sms_action(
        arguments: Mapping[str, Any],
        allowed_actions: set[str],
    ) -> Dict[str, Any]:
        if "action" in arguments or "params" in arguments:
            action, params = arguments.get("action"), arguments.get("params")
            if (
                "api-read" not in allowed_actions or "argv" in arguments
                or not isinstance(action, str) or action not in PUBLIC_QUERY_ACTIONS
                or not isinstance(params, dict)
            ):
                raise ValueError("provide a public query Action and its params object")
            argv = ["api-read", "--action", action, "--params", json.dumps(params, ensure_ascii=False, allow_nan=False)]
        else:
            argv = arguments.get("argv")
        if (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(value, str) or not value for value in argv)
        ):
            raise ValueError("argv must be a non-empty string array")
        action = argv[0]
        if action not in allowed_actions:
            raise ValueError("action is not allowed by this tool")
        stdout = io.StringIO()
        stderr = io.StringIO()
        exit_code = sms_cli.main(argv, stdout=stdout, stderr=stderr)
        payload = stdout.getvalue().strip() or stderr.getvalue().strip()
        try:
            result = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise RuntimeError("SMS action returned invalid JSON") from exc
        if not isinstance(result, Mapping):
            raise RuntimeError("SMS action returned a non-object result")
        return QualificationMcpServer._tool_result(
            payload,
            result,
            is_error=exit_code != 0,
        )

    def _call_tool(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        name = str(params.get("name") or "")
        arguments = params.get("arguments")
        if not isinstance(arguments, Mapping):
            arguments = {}
        if name == "open_batch_task_creation":
            try:
                flow = self._batch_flows.start(arguments)
            except sms_cli.CliError as error:
                result = {
                    "status": "batch_creation_failed", "code": error.code,
                    "completed": True, "fallbackAllowed": False,
                    "outcomeUnknown": error.outcome_unknown,
                    "requestId": error.request_id, "logId": error.log_id,
                }
                if error.remediation is not None:
                    result["remediation"] = error.remediation
                return self._tool_result("群发表单准备失败：" + str(error), result, is_error=True)
            if flow.finished_at is not None:
                result = self._batch_flows.result(flow.flow_id)
                return self._batch_form_result(result)
            return self._tool_result(
                "正在打开群发任务私密表单，请确认页面可见后让客户在页面选择文件。",
                {"flowId": flow.flow_id, "status": "waiting_for_display", "completed": False, "displayMode": "mcp-app"},
                private_meta={**BATCH_TOOL_META, "batchDisplay": {"flowId": flow.flow_id, "url": flow.url}},
            )
        batch_operations = {
            "ensure_batch_task_creation_visible": self._batch_flows.ensure_visible,
            "open_batch_task_creation_in_browser": self._batch_flows.open_in_browser,
            "get_batch_task_creation_result": self._batch_flows.result,
            "cancel_batch_task_creation": self._batch_flows.cancel,
        }
        if name in batch_operations:
            flow_id = arguments.get("flowId")
            if not isinstance(flow_id, str) or not flow_id:
                raise ValueError("flowId is required")
            return self._batch_form_result(batch_operations[name](flow_id))
        if name == "open_qualification_application":
            flow = self._flows.start()
            return self._tool_result(
                f"正在打开私密资质表单（流程 ID：{flow.flow_id}）。"
                "请继续调用 ensure_qualification_application_visible 确认展示。",
                {
                    "flowId": flow.flow_id,
                    "status": "waiting_for_display",
                    "displayStatus": "waiting_for_host",
                    "displayMode": "mcp-app",
                },
                private_meta={
                    **APP_TOOL_META,
                    "qualificationDisplay": {
                        "flowId": flow.flow_id,
                        "url": flow.url,
                    }
                },
            )
        if name == "ensure_qualification_application_visible":
            flow_id = arguments.get("flowId")
            if not isinstance(flow_id, str) or not flow_id:
                raise ValueError("flowId is required")
            result = self._flows.ensure_visible(flow_id)
            if result.get("displayStatus") == "opened":
                text = "资质表单已在右侧面板加载，可以请客户继续填写。"
            elif result.get("displayStatus") == "not_opened":
                text = (
                    "右侧面板未加载。宿主有本机 URL 内置预览能力时，请先取消当前流程，"
                    "再使用 qualification-wizard --display host 在右侧预览；"
                    "宿主没有内置预览能力时，才调用 "
                    "open_qualification_application_in_browser。"
                )
            else:
                status = str(result.get("status") or "unknown")
                text = f"资质表单状态：{status}。"
            return self._tool_result(text, result)
        if name == "open_qualification_application_in_browser":
            flow_id = arguments.get("flowId")
            if not isinstance(flow_id, str) or not flow_id:
                raise ValueError("flowId is required")
            result = self._flows.open_in_browser(flow_id)
            if result.get("displayStatus") == "opened":
                text = "资质表单已在系统浏览器加载，可以请客户继续填写。"
            elif result.get("displayStatus") == "not_opened":
                text = "系统浏览器未能加载资质表单。"
            else:
                status = str(result.get("status") or "unknown")
                text = f"资质表单状态：{status}。"
            return self._tool_result(text, result)
        if name == "get_qualification_application_result":
            flow_id = arguments.get("flowId")
            if not isinstance(flow_id, str) or not flow_id:
                raise ValueError("flowId is required")
            result = self._flows.result(flow_id)
            display_status = result.get("displayStatus")
            if display_status == "opened":
                text = "资质表单已加载，正在等待客户填写。"
            elif display_status == "waiting_for_host":
                text = "资质表单尚未完成展示确认。"
            else:
                status = str(result.get("status") or "unknown")
                references = []
                if result.get("qualificationId"):
                    references.append(f"资质 ID：{result['qualificationId']}")
                if result.get("requestId"):
                    references.append(f"Request ID：{result['requestId']}")
                if result.get("logId"):
                    references.append(f"Log ID：{result['logId']}")
                text = "资质表单状态：{}{}。".format(
                    status,
                    "；" + "；".join(references) if references else "",
                )
            return self._tool_result(text, result)
        if name == "cancel_qualification_application":
            flow_id = arguments.get("flowId")
            if not isinstance(flow_id, str) or not flow_id:
                raise ValueError("flowId is required")
            result = self._flows.cancel(flow_id)
            return self._tool_result("资质表单正在关闭。", result)
        if name == "execute_sms_read_action":
            return self._execute_sms_action(arguments, READ_ACTIONS)
        if name == "execute_sms_write_action":
            return self._execute_sms_action(arguments, WRITE_ACTIONS)
        raise ValueError("unknown tool")

    @staticmethod
    def _batch_form_result(result: Mapping[str, Any]) -> Dict[str, Any]:
        if result.get("status") == "batch_task_confirmed":
            text = "群发任务 {} 已创建并确认启动；短信服务校验通过的号码数 {}，重复号码数 {}。".format(
                result.get("taskId"), result.get("totalCount"), result.get("dupCount"),
            )
        elif result.get("outcomeUnknown") is True:
            text = "群发任务结果未知，请核对原任务，不要重复创建或切换路径重发。"
        elif result.get("displayStatus") == "opened":
            text = "群发表单已加载，请客户在页面选择名单、核对已预填的发送时间并最终确认。"
        elif result.get("displayStatus") == "not_opened":
            text = "群发表单未完成渲染。先关闭当前表单并取得安全结果，再决定是否使用现有创建流程。"
        elif result.get("fallbackAllowed") is True:
            text = "本机表单已关闭且未创建任务，可以回到现有群发流程；脚本直接处理文件，Agent 不读取名单内容。"
        elif result.get("completed") is True:
            text = "群发表单已结束，请按返回状态处理；不要自行重新创建任务。"
        else:
            text = "正在等待客户完成群发表单。"
        return QualificationMcpServer._tool_result(text, result)

    def handle(self, message: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        request_id = message.get("id")
        method = message.get("method")
        if not isinstance(method, str):
            return self._error(request_id, -32600, "Invalid Request")
        if method.startswith("notifications/"):
            return None
        try:
            if method == "initialize":
                params = message.get("params")
                protocol_version = (
                    params.get("protocolVersion")
                    if isinstance(params, Mapping)
                    else "2025-06-18"
                )
                capabilities = (
                    params.get("capabilities")
                    if isinstance(params, Mapping)
                    else None
                )
                extensions = (
                    capabilities.get("extensions")
                    if isinstance(capabilities, Mapping)
                    else None
                )
                _emit_mcp_app_event(
                    "initialize",
                    protocolVersion=protocol_version,
                    uiCapability=bool(
                        isinstance(extensions, Mapping)
                        and "io.modelcontextprotocol/ui" in extensions
                    ),
                )
                result = {
                    "protocolVersion": protocol_version,
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"listChanged": False},
                        "extensions": {
                            "io.modelcontextprotocol/ui": {
                                "mimeTypes": [APP_MIME_TYPE],
                            }
                        },
                    },
                    "serverInfo": {
                        "name": "volcengine-sms-qualification",
                        "version": APP_VERSION,
                    },
                }
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                _emit_mcp_app_event("tools_list")
                result = {"tools": self._tools()}
            elif method == "tools/call":
                params = message.get("params")
                if not isinstance(params, Mapping):
                    raise ValueError("params are required")
                result = self._call_tool(params)
            elif method == "resources/list":
                result = {
                    "resources": [
                        {"uri": uri, "name": name, "mimeType": APP_MIME_TYPE}
                        for uri, (name, document) in FORM_RESOURCES.items()
                    ]
                }
            elif method == "resources/templates/list":
                result = {"resourceTemplates": []}
            elif method == "resources/read":
                params = message.get("params")
                uri = params.get("uri") if isinstance(params, Mapping) else None
                _emit_mcp_app_event(
                    "resource_read",
                    matched=uri in FORM_RESOURCES,
                )
                if uri not in FORM_RESOURCES:
                    return self._error(request_id, -32002, "Resource not found")
                result = {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": APP_MIME_TYPE,
                            "text": FORM_RESOURCES[uri][1],
                            "_meta": {
                                "ui": {
                                    "csp": {
                                        "frameDomains": ["http://127.0.0.1:*"]
                                    }
                                }
                            },
                        }
                    ]
                }
            else:
                return self._error(request_id, -32601, "Method not found")
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except sms_cli.CliError as error:
            return {"jsonrpc": "2.0", "id": request_id, "result": self._tool_result(
                str(error), {
                    "code": error.code, "requestId": error.request_id, "logId": error.log_id,
                    "outcomeUnknown": error.outcome_unknown, "completed": True,
                }, is_error=True,
            )}
        except (ValueError, queue.Empty):
            return self._error(request_id, -32602, "Invalid params")
        except QualificationUploadError as error:
            return self._error(request_id, -32000, str(error))
        except Exception:
            return self._error(request_id, -32603, "Internal error")

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

    def run(self, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> None:
        try:
            for line in stdin:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    response = self._error(None, -32700, "Parse error")
                else:
                    response = (
                        self.handle(message)
                        if isinstance(message, Mapping)
                        else self._error(None, -32600, "Invalid Request")
                    )
                if response is None:
                    continue
                stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
                stdout.flush()
        finally:
            self._flows.cancel_all()
            self._batch_flows.cancel_all()


def main() -> int:
    QualificationMcpServer().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
