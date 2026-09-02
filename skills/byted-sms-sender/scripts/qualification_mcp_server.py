# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
"""Small stdio MCP server that exposes the qualification wizard as an MCP App."""

from __future__ import annotations

import json
import queue
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, TextIO

from api_client import SmsApiClient
from qualification_display import callback_display_adapter
from qualification_upload import QualificationUploadError
from qualification_wizard import run_qualification_wizard


APP_VERSION = "1.3.0"
APP_RESOURCE_URI = "ui://volcengine-sms/qualification-v3.html"
APP_MIME_TYPE = "text/html;profile=mcp-app"
APP_TOOL_META = {
    "ui": {"resourceUri": APP_RESOURCE_URI},
    "workbuddy": {"ui": {"launchSurface": "panel"}},
}
APP_HTML = (
    Path(__file__).resolve().parents[1] / "assets" / "qualification_mcp_app.html"
).read_text(encoding="utf-8")
FLOW_RESULT_TTL_SECONDS = 30 * 60
FLOW_SHUTDOWN_WAIT_SECONDS = 2
DISPLAY_READY_WAIT_SECONDS = 8


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
    finished_at: Optional[float] = None


class QualificationFlowManager:
    def __init__(self, client_factory: ClientFactory = SmsApiClient) -> None:
        self._client_factory = client_factory
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

    def start(self) -> QualificationFlow:
        self._prune_finished()
        with self._lock:
            active = self._active_flow()
            if active is not None:
                _emit_mcp_app_event("flow_reused", flowId=active.flow_id)
                return active
            flow = QualificationFlow(uuid.uuid4().hex)
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
                mode="mcp-app",
            )

        def run() -> None:
            try:
                result = run_qualification_wizard(
                    self._client_factory(),
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
            except QualificationUploadError as error:
                with self._lock:
                    flow.error = {
                        "status": "qualification_application_failed",
                        "code": error.code,
                        "requestId": error.request_id,
                        "logId": error.log_id,
                        "outcomeUnknown": error.outcome_unknown,
                    }
                if flow.url is None:
                    flow.ready.put(error)
            except Exception:
                with self._lock:
                    flow.error = {
                        "status": "qualification_application_failed",
                        "code": "internal_error",
                        "outcomeUnknown": False,
                    }
                if flow.url is None:
                    flow.ready.put(RuntimeError("qualification wizard failed"))
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
            return {
                "status": "qualification_application_not_found",
                "code": "qualification_flow_not_found",
            }
        if wait_for_display_seconds > 0 and not flow.display_ready.is_set():
            flow.display_ready.wait(timeout=wait_for_display_seconds)
        with self._lock:
            if flow.result is not None:
                return dict(flow.result)
            if flow.error is not None:
                return dict(flow.error)
            return {
                "status": (
                    "waiting_for_customer"
                    if flow.display_ready.is_set()
                    else "waiting_for_display"
                ),
                "displayStatus": (
                    "opened" if flow.display_ready.is_set() else "waiting_for_host"
                ),
                "displayMode": "mcp-app",
            }

    def ensure_visible(self, flow_id: str) -> Dict[str, Any]:
        result = self.result(
            flow_id,
            wait_for_display_seconds=DISPLAY_READY_WAIT_SECONDS,
        )
        if result.get("status") != "waiting_for_display":
            return result
        return {
            "status": "qualification_panel_not_visible",
            "displayStatus": "not_opened",
            "displayMode": "mcp-app",
            "code": "qualification_panel_not_visible",
        }

    def cancel(self, flow_id: str) -> Dict[str, Any]:
        with self._lock:
            flow = self._flows.get(flow_id)
            if flow is None:
                return {
                    "status": "qualification_application_not_found",
                    "code": "qualification_flow_not_found",
                }
            if flow.finished_at is not None:
                if flow.result is not None:
                    return dict(flow.result)
                if flow.error is not None:
                    return dict(flow.error)
            flow.cancel_event.set()
            return {"status": "qualification_application_cancelling"}

    def cancel_all(self) -> None:
        with self._lock:
            flows = list(self._flows.values())
            for flow in flows:
                flow.cancel_event.set()
        for flow in flows:
            if flow.thread is not None and flow.thread.is_alive():
                flow.thread.join(timeout=FLOW_SHUTDOWN_WAIT_SECONDS)


class QualificationMcpServer:
    def __init__(self, flow_manager: Optional[QualificationFlowManager] = None) -> None:
        self._flows = flow_manager or QualificationFlowManager()

    @staticmethod
    def _tool_result(
        text: str,
        structured: Mapping[str, Any],
        *,
        private_meta: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "content": [{"type": "text", "text": text}],
            "structuredContent": dict(structured),
        }
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
        ]

    def _call_tool(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        name = str(params.get("name") or "")
        arguments = params.get("arguments")
        if not isinstance(arguments, Mapping):
            arguments = {}
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
                    "右侧面板未加载。请取消此流程，改用宿主内置浏览器展示本机表单；"
                    "宿主不支持时再使用系统浏览器。"
                )
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
        raise ValueError("unknown tool")

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
                        {
                            "uri": APP_RESOURCE_URI,
                            "name": "火山引擎短信资质表单",
                            "mimeType": APP_MIME_TYPE,
                        }
                    ]
                }
            elif method == "resources/templates/list":
                result = {"resourceTemplates": []}
            elif method == "resources/read":
                params = message.get("params")
                uri = params.get("uri") if isinstance(params, Mapping) else None
                _emit_mcp_app_event(
                    "resource_read",
                    matched=uri == APP_RESOURCE_URI,
                )
                if uri != APP_RESOURCE_URI:
                    return self._error(request_id, -32002, "Resource not found")
                result = {
                    "contents": [
                        {
                            "uri": APP_RESOURCE_URI,
                            "mimeType": APP_MIME_TYPE,
                            "text": APP_HTML,
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


def main() -> int:
    QualificationMcpServer().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
