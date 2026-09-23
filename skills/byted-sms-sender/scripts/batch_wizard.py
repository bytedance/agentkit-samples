# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License").
"""Private file selection and scheduling UI for an existing batch draft."""

from __future__ import annotations

import secrets
import threading
import time
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional
from urllib.parse import quote, urlsplit

from local_form import LocalFormHandler, LocalFormLifecycle, serve_local_form
from qualification_display import browser_display_adapter
from qualification_upload import QualificationUploadError

if TYPE_CHECKING:
    from sms_cli import BatchFormDraft


ASSETS = Path(__file__).resolve().parents[1] / "assets"
VENDOR_ASSETS = ASSETS / "qualification_wizard_vendor"
CONTEXT_HEADER = "X-Batch-Context"
RENDER_TIMEOUT_SECONDS = 5 * 60
STATIC_ASSETS = {
    "/batch-static/react.production.min.js": (
        VENDOR_ASSETS / "react.production.min.js"
    ),
    "/batch-static/react-dom.production.min.js": (
        VENDOR_ASSETS / "react-dom.production.min.js"
    ),
    "/batch-static/arco.min.js": VENDOR_ASSETS / "arco.min.js",
    "/batch-static/arco-icon.min.js": VENDOR_ASSETS / "arco-icon.min.js",
    "/batch-static/arco.min.css": VENDOR_ASSETS / "arco.min.css",
    "/batch-static/batch_wizard.css": ASSETS / "batch_wizard.css",
    "/batch-static/batch_wizard.js": ASSETS / "batch_wizard.js",
}


def run_batch_wizard(
    draft: BatchFormDraft,
    *,
    display=None,
    cancel_event: Optional[threading.Event] = None,
    on_display_ready: Optional[Callable[[], None]] = None,
    render_timeout_seconds: float = RENDER_TIMEOUT_SECONDS,
    disconnect_timeout_seconds: float = 5 * 60,
    detach_grace_seconds: float = 60,
    idle_timeout_seconds: float = 30 * 60,
) -> dict:
    display = display or browser_display_adapter()
    cancel_event = cancel_event or threading.Event()
    lifecycle = LocalFormLifecycle(
        disconnect_timeout_seconds, detach_grace_seconds, idle_timeout_seconds
    )
    if render_timeout_seconds <= 0:
        raise ValueError("Render timeout must be positive")
    token = secrets.token_urlsafe(24)
    ready = False
    result = None
    started = time.monotonic()
    document = (ASSETS / "batch_wizard.html").read_text(encoding="utf-8")

    class Handler(LocalFormHandler):
        context_header = CONTEXT_HEADER
        context_token = token
        static_assets = STATIC_ASSETS
        allows_embedding = display.allows_embedding

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/":
                self._html(document)
            elif self._asset(path):
                return
            elif not self._authorized():
                self.send_error(HTTPStatus.NOT_FOUND)
            elif path == "/api/template":
                try:
                    file_name, content_type, body = draft.template_file()
                    self._respond(
                        HTTPStatus.OK,
                        body,
                        content_type,
                        headers={
                            "Content-Disposition": (
                                "attachment; filename=recipients.csv; "
                                "filename*=UTF-8''{}".format(quote(file_name))
                            )
                        },
                    )
                except ValueError as exc:
                    self._json(
                        HTTPStatus.BAD_REQUEST,
                        {"success": False, "message": str(exc)},
                    )
            elif path == "/api/state":
                lifecycle.touch(active=True)
                self._json(HTTPStatus.OK, {"success": True, "state": draft.metadata})
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            nonlocal ready, result
            if not self._authorized():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            path = urlsplit(self.path).path
            try:
                if path == "/api/heartbeat":
                    value = self._document()
                    lifecycle.touch(active=value.get("active") is True)
                    if not ready:
                        ready = True
                        if on_display_ready is not None:
                            on_display_ready()
                    self._json(HTTPStatus.OK, {"success": True})
                    return
                if path == "/api/detach":
                    lifecycle.detach()
                    self._json(HTTPStatus.OK, {"success": True})
                    return
                lifecycle.touch(active=True)
                if path == "/api/file":
                    draft.clear_file()
                    if self.headers.get_content_type() != "text/csv":
                        raise ValueError("请选择 CSV 文件")
                    uploaded = draft.set_file(self._body(draft.metadata["maxFileBytes"]))
                    self._json(HTTPStatus.OK, {"success": True, **uploaded})
                elif path == "/api/file/clear":
                    self._document()
                    draft.clear_file()
                    self._json(HTTPStatus.OK, {"success": True})
                elif path == "/api/test-send":
                    value = self._document()
                    test_result = draft.send_test_sms(
                        value.get("phone"),
                        value.get("templateParams"),
                    )
                    self._json(
                        HTTPStatus.OK,
                        {"success": True, "result": test_result},
                    )
                elif path == "/api/test-send/status":
                    value = self._document()
                    test_status = draft.test_sms_status(value.get("messageId"))
                    self._json(
                        HTTPStatus.OK,
                        {"success": True, "status": test_status},
                    )
                elif path == "/api/preview":
                    value = self._document()
                    preview = draft.preview(value.get("scheduled"), value.get("sendTime"))
                    if "terminalResult" in preview:
                        result = preview["terminalResult"]
                        self._json(
                            HTTPStatus.OK,
                            {"success": True, "result": result},
                        )
                    else:
                        self._json(
                            HTTPStatus.OK,
                            {"success": True, "preview": preview},
                        )
                elif path == "/api/create":
                    value = self._document()
                    result = draft.create(value.get("revision"), value.get("confirmed"))
                    self._json(HTTPStatus.OK, {"success": True, "result": result})
                elif path == "/api/abandon":
                    result = draft.close("abandoned")
                    self._json(HTTPStatus.OK, {"success": True, "result": result})
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)
            except ValueError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"success": False, "message": str(exc)})
            except Exception:
                # Keep raw bodies, filenames and provider errors inside this process.
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"success": False, "message": "本机表单处理失败，请重试当前步骤"})

    def completed() -> bool:
        nonlocal result
        if result is None and not ready and time.monotonic() - started >= render_timeout_seconds:
            result = draft.close("not_displayed")
        return result is not None

    try:
        try:
            reason = serve_local_form(
                Handler, display, token, lifecycle,
                completed=completed, cancel_event=cancel_event,
            )
        except QualificationUploadError:
            result = draft.close("not_displayed")
        else:
            if reason is not None:
                result = draft.close(reason)
    finally:
        draft.close("closed")
    if result is None:
        raise RuntimeError("Batch form ended without a result")
    return result
