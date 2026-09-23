# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License").
"""Bounded loopback HTTP transport and lifecycle for private customer forms."""

from __future__ import annotations

import hmac
import json
import mimetypes
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable, Mapping, Optional


class LocalFormLifecycle:
    def __init__(self, disconnect_seconds: float, detach_seconds: float, idle_seconds: float):
        if min(disconnect_seconds, detach_seconds, idle_seconds) <= 0:
            raise ValueError("Form lifecycle timeouts must be positive")
        self.disconnect_seconds = disconnect_seconds
        self.detach_seconds = detach_seconds
        self.idle_seconds = idle_seconds
        self.last_activity = self.last_heartbeat = time.monotonic()
        self.detached_at: Optional[float] = None
        self._lock = threading.Lock()

    def touch(self, *, active: bool) -> None:
        with self._lock:
            self.last_heartbeat = time.monotonic()
            self.detached_at = None
            if active:
                self.last_activity = self.last_heartbeat

    def detach(self) -> None:
        with self._lock:
            self.detached_at = time.monotonic()

    def expiry_reason(self) -> Optional[str]:
        now = time.monotonic()
        with self._lock:
            if self.detached_at is not None and now - self.detached_at >= self.detach_seconds:
                return "detached"
            if now - self.last_heartbeat >= self.disconnect_seconds:
                return "disconnected"
            if now - self.last_activity >= self.idle_seconds:
                return "idle"
        return None


class LocalFormHandler(BaseHTTPRequestHandler):
    context_header: str
    context_token: str
    static_assets: Mapping[str, Path] = {}
    allows_embedding = False

    def log_message(self, format: str, *args: object) -> None:
        # Request paths, headers and bodies may carry private form data.
        return

    def _authorized(self) -> bool:
        origin = "http://127.0.0.1:{}".format(self.server.server_port)
        return (
            self.headers.get("Host") == "127.0.0.1:{}".format(self.server.server_port)
            and self.headers.get("Origin", origin) == origin
            and hmac.compare_digest(
                self.headers.get(self.context_header, "").encode("utf-8"),
                self.context_token.encode("utf-8"),
            )
        )

    def _respond(self, status: int, body: bytes, content_type: str, *, headers: Optional[Mapping[str, str]] = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # A lost page cannot change a completed business operation.

    def _json(self, status: int, payload: Mapping) -> None:
        self._respond(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _html(self, document: str) -> None:
        headers = {
            "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' blob: data:; font-src 'self'; form-action 'none'; base-uri 'none'; object-src 'none'",
        }
        if not self.allows_embedding:
            headers["X-Frame-Options"] = "DENY"
        self._respond(HTTPStatus.OK, document.encode("utf-8"), "text/html; charset=utf-8", headers=headers)

    def _asset(self, path: str) -> bool:
        asset = self.static_assets.get(path)
        if asset is None:
            return False
        variants = (asset, asset.with_name(asset.name + ".br"))
        selected = next((candidate for candidate in variants if candidate.is_file()), None)
        if selected is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return True
        try:
            body = selected.read_bytes()
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return True
        content_type, encoding = mimetypes.guess_type(selected.name)
        headers = {"Content-Encoding": encoding} if encoding else {}
        self._respond(HTTPStatus.OK, body, content_type or "application/octet-stream", headers=headers)
        return True

    def _body(self, maximum: int = 64 * 1024) -> bytes:
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("Unsupported transfer encoding")
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > maximum:
            raise ValueError("Request body is empty or too large")
        body = self.rfile.read(length)
        if len(body) != length:
            raise ValueError("Request body is incomplete")
        return body

    def _document(self) -> dict:
        document = json.loads(self._body().decode("utf-8"))
        if not isinstance(document, dict):
            raise ValueError("Request must contain a JSON object")
        return document


class LocalFormServer(HTTPServer):
    request_queue_size = 8

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(10)
        return connection, address

    def handle_error(self, request, client_address) -> None:
        # Never dump private request data through an HTTP handler traceback.
        return


def serve_local_form(handler, display, token: str, lifecycle: LocalFormLifecycle, *, completed: Callable[[], bool], cancel_event: threading.Event) -> Optional[str]:
    """Serve one form; return a cancellation reason only before completion."""
    server = LocalFormServer(("127.0.0.1", 0), handler)
    server.timeout = 0.25
    try:
        display.present("http://127.0.0.1:{}/#{}".format(server.server_port, token))
        while not completed():
            if cancel_event.is_set():
                return "cancelled"
            reason = lifecycle.expiry_reason()
            if reason is not None:
                return reason
            server.handle_request()
    finally:
        server.server_close()
    return None
