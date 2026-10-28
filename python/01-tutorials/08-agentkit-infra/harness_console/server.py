#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.31,<3", "PyYAML>=6,<7"]
# ///
"""Run with: uv run server.py [--config /path/to/config.yaml]."""

from __future__ import annotations

import argparse
import json
import secrets
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from backend import CATALOG, Console, HarnessInfraError

from _config import config_path  # isort: skip (backend adds the shared sample import path)

STATIC = Path(__file__).with_name("static")


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, console, csrf, **kwargs):
        self.console, self.csrf = console, csrf
        super().__init__(*args, **kwargs)

    def log_message(self, *_):
        # Do not log URLs, request bodies, prompts, or credentials.
        pass

    def reply(self, status, data, content_type="application/json; charset=utf-8"):
        payload = (
            json.dumps(data, ensure_ascii=False).encode()
            if content_type.startswith("application/json")
            else data
        )
        self.send_response(status)
        for key, value in {
            "Content-Type": content_type,
            "Content-Length": str(len(payload)),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        }.items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def trusted(self):
        port = self.server.server_port
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        return (
            host in allowed
            and (not origin or origin in {f"http://{item}" for item in allowed})
            and self.headers.get("Sec-Fetch-Site") != "cross-site"
        )

    def do_GET(self):
        if not self.trusted():
            return self.reply(403, {"error": "只允许本机同源访问"})
        path = urlsplit(self.path).path
        if path == "/api/bootstrap":
            return self.reply(200, {**self.console.bootstrap(), "csrf": self.csrf})
        files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/cleanup.js": ("cleanup.js", "text/javascript; charset=utf-8"),
            "/cleanup-ui.js": ("cleanup-ui.js", "text/javascript; charset=utf-8"),
            "/style.css": ("style.css", "text/css; charset=utf-8"),
        }
        if path not in files:
            return self.reply(404, {"error": "Not found"})
        name, mime = files[path]
        self.reply(200, (STATIC / name).read_bytes(), mime)

    def do_POST(self):
        if not self.trusted():
            return self.reply(403, {"error": "只允许本机同源访问"})
        if not secrets.compare_digest(
            self.headers.get("X-Console-Token", ""), self.csrf
        ):
            return self.reply(
                403,
                {"error": "页面凭据已过期，请刷新页面", "code": "ConsoleTokenExpired"},
            )
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.reply(415, {"error": "Expected application/json"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 2 * 1024 * 1024:
                return self.reply(413, {"error": "请求体过大或为空"})
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise TypeError("请求必须为 JSON 对象")
            result = self.dispatch(urlsplit(self.path).path, body)
            return self.reply(200, self.console.safe(result))
        except HarnessInfraError as error:
            status = error.status_code if 400 <= error.status_code < 600 else 502
            self.reply(
                status,
                self.console.safe(
                    {
                        "error": str(error),
                        "code": error.code,
                        "request_id": error.request_id,
                    }
                ),
            )
        except (ValueError, TypeError, KeyError) as error:
            message = (
                str(error)
                if isinstance(error, ValueError)
                else "请求字段或数据类型不正确"
            )
            self.reply(400, self.console.safe({"error": message}))
        except Exception:  # noqa: BLE001 - HTTP boundary must not expose secret-bearing exceptions.
            # Unexpected errors may contain credentials; do not return their repr or traceback.
            self.reply(
                500,
                {
                    "error": "本地请求处理失败。请检查配置和本地密钥文件权限；操作可能已受理，重试前先刷新资源。"
                },
            )

    def dispatch(self, path, body):
        if path == "/api/keys/import":
            return self.console.import_key(body)
        kind = body.get("kind", "sessions")
        if kind not in CATALOG:
            raise ValueError("未知资源类型")
        context = body.get("context") or {}
        if path == "/api/list":
            return self.console.list(
                kind, body.get("filters"), body.get("cursor", ""), context
            )
        if path == "/api/get":
            return self.console.get(kind, body.get("id"), context)
        if path == "/api/create":
            return self.console.create(
                kind,
                body.get("body"),
                context,
                body.get("model_key_name", ""),
                body.get("token", ""),
            )
        if path == "/api/archive":
            return self.console.archive(kind, body.get("id"), body.get("token", ""))
        if path == "/api/delete":
            return self.console.delete(
                kind,
                body.get("id"),
                context,
                body.get("token", ""),
                body.get("reason", ""),
            )
        if path == "/api/events":
            return self.console.events(body.get("id"), context, body.get("after", 0))
        if path == "/api/send":
            return self.console.send(
                body.get("id"), context, body.get("prompt"), body.get("event_id")
            )
        raise ValueError("未知操作")


def make_server(console, port=8765):
    return ThreadingHTTPServer(
        ("127.0.0.1", port),
        partial(Handler, console=console, csrf=secrets.token_urlsafe(32)),
    )


def main():
    parser = argparse.ArgumentParser(description="Harness Infra 本地资源管理与聊天")
    local = Path(__file__).with_name("config.yaml")
    parser.add_argument(
        "--config",
        type=Path,
        default=config_path(local),
    )
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        console = Console(args.config.expanduser())
    except (ValueError, RuntimeError, TypeError, KeyError) as error:
        parser.exit(2, f"启动失败：{error}\n")
    with make_server(console, args.port) as server:
        print(f"Harness Console: http://127.0.0.1:{server.server_port}", flush=True)
        print(f"Config: {console.path}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
