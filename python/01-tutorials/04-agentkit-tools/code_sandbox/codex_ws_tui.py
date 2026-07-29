#!/usr/bin/env python3
"""Terminal client for talking to Codex app-server through WebSocket."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit


APP_SERVER_PATH = "/v1/codex/app-server/"
CLIENT_NAME = "agentkit_codex_app_server_client"
CLIENT_TITLE = "AgentKit Codex App Server Client"
CLIENT_VERSION = "python-sample"
DEFAULT_TIMEOUT_SECONDS = 300


class CodexAppServerError(Exception):
    """Raised when Codex app-server communication fails."""


class CodexRpcError(CodexAppServerError):
    def __init__(
        self,
        method: str,
        code: int | str,
        message: str,
        data: Any = None,
    ) -> None:
        super().__init__(f"{method} failed ({code}): {message}")
        self.code = code
        self.data = data


@dataclass
class TurnState:
    chunks: list[str] = field(default_factory=list)
    final_text: str | None = None
    completion: dict[str, Any] | None = None
    streamed: bool = False
    waiters: list[asyncio.Future[dict[str, Any]]] = field(default_factory=list)


def app_server_websocket_url(input_url: str) -> str:
    """Convert a sandbox endpoint URL to the Codex app-server WebSocket URL."""
    value = input_url.strip()
    if not value:
        raise ValueError("URL must not be empty")

    split = urlsplit(value)
    if split.scheme not in {"http", "https", "ws", "wss"}:
        raise ValueError("URL must use http, https, ws, or wss")
    if not split.netloc:
        raise ValueError("URL must include a host")
    if split.username or split.password:
        raise ValueError(
            "userinfo credentials are not supported; keep gateway credentials in query"
        )
    if split.fragment:
        raise ValueError("URL must not include a fragment")

    normalized_path = split.path.rstrip("/")
    if normalized_path and normalized_path != APP_SERVER_PATH.rstrip("/"):
        raise ValueError(f"URL path must be / or {APP_SERVER_PATH}; got {split.path!r}")

    scheme = "wss" if split.scheme in {"https", "wss"} else "ws"
    return urlunsplit((scheme, split.netloc, APP_SERVER_PATH, split.query, ""))


def _decode_frame(frame: str | bytes) -> str:
    if isinstance(frame, bytes):
        return frame.decode("utf-8", errors="replace")
    return frame


def _is_record(value: Any) -> bool:
    return isinstance(value, dict)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _parse_header(value: str) -> tuple[str, str]:
    name, sep, header_value = value.partition(":")
    if not sep or not name.strip():
        raise argparse.ArgumentTypeError("header must be in 'Name: Value' format")
    return name.strip(), header_value.strip()


def _build_headers(args: argparse.Namespace) -> list[tuple[str, str]]:
    headers = list(args.header or [])
    if args.token:
        headers.append(("Authorization", f"Bearer {args.token}"))
    return headers


def _websockets_connect_kwargs(
    websockets_module: Any,
    headers: list[tuple[str, str]],
    *,
    ping_interval: float | None,
    ping_timeout: float | None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "ping_interval": ping_interval,
        "ping_timeout": ping_timeout,
    }
    if headers:
        major = int((getattr(websockets_module, "__version__", "15").split(".")[0]))
        if major >= 14:
            kwargs["additional_headers"] = headers
        else:
            kwargs["extra_headers"] = headers
    return kwargs


def _extract_thread_id(result: dict[str, Any], method: str) -> str:
    thread = result.get("thread")
    if not _is_record(thread) or not isinstance(thread.get("id"), str):
        raise CodexAppServerError(f"{method} response did not contain thread.id")
    return thread["id"]


def _approval_kind(method: str) -> str:
    if method == "item/commandExecution/requestApproval":
        return "command execution"
    if method == "item/fileChange/requestApproval":
        return "file change"
    return "permissions"


class CodexAppServerClient:
    def __init__(
        self,
        websocket: Any,
        *,
        request_timeout: float,
        turn_timeout: float,
        prompt_session: Any | None,
        verbose: bool,
    ) -> None:
        self.websocket = websocket
        self.request_timeout = request_timeout
        self.turn_timeout = turn_timeout
        self.prompt_session = prompt_session
        self.verbose = verbose
        self.thread_id: str | None = None
        self._next_request_id = 1
        self._pending: dict[int, tuple[str, asyncio.Future[dict[str, Any]]]] = {}
        self._turn_states: dict[str, TurnState] = {}
        self._finished_turn_ids: set[str] = set()
        self._receive_task: asyncio.Task[None] | None = None
        self._closed = False

    async def start(self) -> None:
        self._receive_task = asyncio.create_task(self._receive_loop())
        await self.request(
            "initialize",
            {
                "clientInfo": {
                    "name": CLIENT_NAME,
                    "title": CLIENT_TITLE,
                    "version": CLIENT_VERSION,
                },
                "capabilities": {"experimentalApi": True},
            },
        )
        await self.notify("initialized")

    async def close(self) -> None:
        self._closed = True
        if self._receive_task:
            self._receive_task.cancel()
            await asyncio.gather(self._receive_task, return_exceptions=True)

    async def start_thread(self, *, cwd: str = "", model: str = "") -> str:
        params: dict[str, Any] = {}
        if cwd:
            params["cwd"] = cwd
        if model:
            params["model"] = model
        result = await self.request("thread/start", params)
        self.thread_id = _extract_thread_id(result, "thread/start")
        return self.thread_id

    async def resume_thread(
        self,
        thread_id: str,
        *,
        cwd: str = "",
        model: str = "",
    ) -> str:
        params: dict[str, Any] = {"threadId": thread_id}
        if cwd:
            params["cwd"] = cwd
        if model:
            params["model"] = model
        result = await self.request("thread/resume", params)
        self.thread_id = _extract_thread_id(result, "thread/resume")
        return self.thread_id

    async def ensure_thread(
        self,
        *,
        thread_id: str = "",
        cwd: str = "",
        model: str = "",
    ) -> str:
        if thread_id:
            return await self.resume_thread(thread_id, cwd=cwd, model=model)
        return await self.start_thread(cwd=cwd, model=model)

    async def run_turn(self, prompt: str, *, stream: bool = True) -> dict[str, Any]:
        if not self.thread_id:
            raise CodexAppServerError("no active thread")
        if not prompt:
            raise ValueError("message must not be empty")

        result = await self.request(
            "turn/start",
            {
                "threadId": self.thread_id,
                "input": [{"type": "text", "text": prompt}],
            },
        )
        turn = result.get("turn")
        if not _is_record(turn) or not isinstance(turn.get("id"), str):
            raise CodexAppServerError("turn/start response did not contain turn.id")

        turn_id = turn["id"]
        state = self._turn_state(turn_id)
        if stream:
            for chunk in state.chunks:
                print(chunk, end="", flush=True)

        completion = state.completion or await self._wait_for_turn(turn_id, state)
        text = (
            state.final_text if state.final_text is not None else "".join(state.chunks)
        )
        streamed = state.streamed
        self._turn_states.pop(turn_id, None)
        self._finished_turn_ids.add(turn_id)
        if completion.get("status") == "failed":
            raise CodexAppServerError(str(completion.get("error") or "turn failed"))
        return {
            "turn_id": turn_id,
            "status": completion.get("status", "completed"),
            "text": text,
            "streamed": streamed,
            **({"error": completion["error"]} if "error" in completion else {}),
        }

    async def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_id = self._next_request_id
        self._next_request_id += 1
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[request_id] = (method, future)
        message = {"id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        await self._send(message)
        try:
            return await asyncio.wait_for(future, timeout=self.request_timeout)
        finally:
            self._pending.pop(request_id, None)

    async def notify(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        message = {"method": method}
        if params is not None:
            message["params"] = params
        await self._send(message)

    async def _send(self, message: dict[str, Any]) -> None:
        if self.verbose:
            name = message.get("method") or "response"
            print(f"[send] {name}", file=sys.stderr)
        await self.websocket.send(_json_dumps(message))

    async def _receive_loop(self) -> None:
        try:
            async for frame in self.websocket:
                await self._handle_frame(frame)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not self._closed:
                self._reject_all(CodexAppServerError(f"receive failed: {exc}"))
        else:
            if not self._closed:
                self._reject_all(CodexAppServerError("app-server WebSocket closed"))

    async def _handle_frame(self, frame: str | bytes) -> None:
        raw = _decode_frame(frame)
        try:
            message = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CodexAppServerError("app-server sent non-JSON message") from exc
        if not _is_record(message):
            raise CodexAppServerError("app-server sent a non-object JSON message")

        method = message.get("method")
        if self.verbose:
            print(f"[receive] {method or 'response'}", file=sys.stderr)

        if isinstance(method, str) and "id" in message:
            await self._handle_server_request(
                message["id"], method, message.get("params")
            )
            return

        if "id" in message:
            self._handle_response(message)
            return

        if isinstance(method, str):
            params = message.get("params") or {}
            if not _is_record(params):
                raise CodexAppServerError(
                    f"app-server sent invalid params for {method}"
                )
            self._handle_notification(method, params)
            return

        raise CodexAppServerError("app-server sent an unrecognized message")

    def _handle_response(self, message: dict[str, Any]) -> None:
        request_id = message.get("id")
        if not isinstance(request_id, int):
            return
        pending = self._pending.get(request_id)
        if not pending:
            return
        method, future = pending
        if future.done():
            return

        if "error" in message:
            error = message["error"]
            if _is_record(error):
                code = error.get("code", "unknown")
                detail = error.get("message", "unknown error")
                future.set_exception(
                    CodexRpcError(method, code, str(detail), error.get("data"))
                )
            else:
                future.set_exception(CodexAppServerError(f"{method} failed: {error}"))
            return

        result = message.get("result")
        if not _is_record(result):
            future.set_exception(
                CodexAppServerError(f"{method} returned a non-object result")
            )
            return
        future.set_result(result)

    async def _handle_server_request(
        self,
        request_id: Any,
        method: str,
        params: Any,
    ) -> None:
        if method not in {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
            "item/permissions/requestApproval",
        }:
            await self._send(
                {
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"unsupported server request: {method}",
                    },
                }
            )
            return

        if not _is_record(params):
            await self._send(
                {
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": f"invalid params for {method}",
                    },
                }
            )
            return

        if method == "item/permissions/requestApproval":
            result: dict[str, Any] = {"permissions": {}, "scope": "turn"}
        else:
            result = {"decision": await self._ask_for_approval(method, params)}
        await self._send({"id": request_id, "result": result})

    async def _ask_for_approval(self, method: str, params: dict[str, Any]) -> str:
        print(f"\n[approval] {_approval_kind(method)}", file=sys.stderr)
        for key, label in (
            ("reason", "reason"),
            ("command", "command"),
            ("cwd", "cwd"),
            ("grantRoot", "write root"),
        ):
            value = params.get(key)
            if isinstance(value, str) and value:
                print(f"{label}: {value}", file=sys.stderr)

        if not self.prompt_session or not sys.stdin.isatty():
            print("[approval] no interactive terminal; declined", file=sys.stderr)
            return "decline"

        answer = (
            (
                await self.prompt_session.prompt_async(
                    "allow? [y] once / [a] session / [n] decline / [c] cancel: "
                )
            )
            .strip()
            .lower()
        )
        if answer in {"y", "yes"}:
            return "accept"
        if answer in {"a", "always"}:
            return "acceptForSession"
        if answer in {"c", "cancel"}:
            return "cancel"
        return "decline"

    def _handle_notification(self, method: str, params: dict[str, Any]) -> None:
        if method == "item/agentMessage/delta":
            turn_id = params.get("turnId")
            delta = params.get("delta")
            if isinstance(turn_id, str) and isinstance(delta, str):
                if turn_id in self._finished_turn_ids:
                    return
                state = self._turn_state(turn_id)
                state.chunks.append(delta)
                state.streamed = True
                print(delta, end="", flush=True)
            return

        if method == "item/completed":
            turn_id = params.get("turnId")
            item = params.get("item")
            if isinstance(turn_id, str) and _is_record(item):
                if item.get("type") == "agentMessage":
                    phase = item.get("phase")
                    text = item.get("text")
                    if isinstance(text, str) and phase in {None, "final_answer"}:
                        self._turn_state(turn_id).final_text = text
            return

        if method == "turn/completed":
            turn = params.get("turn")
            if not _is_record(turn):
                return
            turn_id = turn.get("id")
            if not isinstance(turn_id, str) or turn_id in self._finished_turn_ids:
                return
            status = (
                turn.get("status")
                if isinstance(turn.get("status"), str)
                else "completed"
            )
            error = turn.get("error")
            completion: dict[str, Any] = {"status": status}
            if _is_record(error) and isinstance(error.get("message"), str):
                completion["error"] = error["message"]
            state = self._turn_state(turn_id)
            state.completion = completion
            for waiter in state.waiters:
                if not waiter.done():
                    waiter.set_result(completion)
            state.waiters.clear()

    def _turn_state(self, turn_id: str) -> TurnState:
        state = self._turn_states.get(turn_id)
        if state is None:
            state = TurnState()
            self._turn_states[turn_id] = state
        return state

    async def _wait_for_turn(
        self,
        turn_id: str,
        state: TurnState,
    ) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        state.waiters.append(future)
        try:
            return await asyncio.wait_for(future, timeout=self.turn_timeout)
        finally:
            if future in state.waiters:
                state.waiters.remove(future)

    def _reject_all(self, error: Exception) -> None:
        for _, future in self._pending.values():
            if not future.done():
                future.set_exception(error)
        self._pending.clear()
        for state in self._turn_states.values():
            for waiter in state.waiters:
                if not waiter.done():
                    waiter.set_exception(error)
            state.waiters.clear()


async def _run_turn_and_print(
    client: CodexAppServerClient,
    message: str,
    *,
    prefix: bool,
) -> None:
    if prefix:
        print("codex> ", end="", flush=True)
    result = await client.run_turn(message)
    if result["text"] and not result["streamed"]:
        print(result["text"], end="", flush=True)
    print()


async def _interactive_chat(
    client: CodexAppServerClient,
    prompt_session: Any,
    *,
    multiline: bool,
    cwd: str,
    model: str,
) -> None:
    while True:
        try:
            message = await prompt_session.prompt_async("you> ", multiline=multiline)
        except (EOFError, KeyboardInterrupt):
            print()
            return

        message = message.strip()
        if not message:
            continue
        if message in {"/exit", "/quit"}:
            return
        if message == "/help":
            print("/new  /thread  /help  /exit  /quit")
            continue
        if message == "/thread":
            print(client.thread_id or "no thread")
            continue
        if message == "/new":
            thread_id = await client.start_thread(cwd=cwd, model=model)
            print(f"[thread] {thread_id}", file=sys.stderr)
            continue

        try:
            await _run_turn_and_print(client, message, prefix=True)
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)


async def _run(args: argparse.Namespace) -> None:
    try:
        import websockets
        from websockets.exceptions import InvalidStatus
        from prompt_toolkit import PromptSession
        from prompt_toolkit.patch_stdout import patch_stdout
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency. Run: pip install -r requirements.txt"
        ) from exc

    websocket_url = app_server_websocket_url(args.url)
    headers = _build_headers(args)
    connect_kwargs = _websockets_connect_kwargs(
        websockets,
        headers,
        ping_interval=args.ping_interval,
        ping_timeout=args.ping_timeout,
    )
    prompt_session = PromptSession()

    try:
        websocket_context = websockets.connect(websocket_url, **connect_kwargs)
        websocket = await websocket_context.__aenter__()
    except InvalidStatus as exc:
        raise SystemExit(
            f"WebSocket handshake failed: {exc}\n"
            "Check that the sandbox endpoint is correct and the Authorization query "
            "is still valid."
        ) from exc

    client = CodexAppServerClient(
        websocket,
        request_timeout=args.timeout,
        turn_timeout=args.timeout,
        prompt_session=prompt_session,
        verbose=args.verbose,
    )
    try:
        await client.start()
        thread_id = await client.ensure_thread(
            thread_id=args.thread_id,
            cwd=args.cwd,
            model=args.model,
        )
        print(f"[thread] {thread_id}", file=sys.stderr)

        with patch_stdout():
            if args.message:
                await _run_turn_and_print(client, args.message, prefix=False)
            else:
                await _interactive_chat(
                    client,
                    prompt_session,
                    multiline=args.multiline,
                    cwd=args.cwd,
                    model=args.model,
                )
    finally:
        await client.close()
        await websocket_context.__aexit__(None, None, None)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Talk to Codex app-server through WebSocket from the terminal."
    )
    parser.add_argument(
        "url_positional",
        nargs="?",
        help="Optional sandbox endpoint URL. Same as --url.",
    )
    parser.add_argument(
        "--url",
        default=os.getenv("CODEX_WS_URL", ""),
        help=(
            "Sandbox endpoint or Codex app-server WebSocket URL. "
            "Defaults to CODEX_WS_URL."
        ),
    )
    parser.add_argument(
        "--message",
        help="Send one message to Codex, print the plain-text response, then exit.",
    )
    parser.add_argument(
        "--thread-id",
        default=os.getenv("CODEX_THREAD_ID", ""),
        help="Resume an existing Codex thread. Defaults to CODEX_THREAD_ID.",
    )
    parser.add_argument(
        "--cwd",
        default=os.getenv("CODEX_CWD", ""),
        help="Optional working directory for thread/start or thread/resume.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("CODEX_MODEL", ""),
        help="Optional model for thread/start or thread/resume.",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("CODEX_WS_TOKEN", ""),
        help="Optional bearer token header. Defaults to CODEX_WS_TOKEN.",
    )
    parser.add_argument(
        "--header",
        action="append",
        type=_parse_header,
        help="Extra request header in 'Name: Value' format. Can be repeated.",
    )
    parser.add_argument(
        "--multiline",
        action="store_true",
        help="Enable multiline prompt input in interactive mode.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("CODEX_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)),
        help=f"Request and turn timeout in seconds. Default: {DEFAULT_TIMEOUT_SECONDS}.",
    )
    parser.add_argument(
        "--ping-interval",
        type=float,
        default=20.0,
        help="WebSocket ping interval in seconds. Default: 20.",
    )
    parser.add_argument(
        "--ping-timeout",
        type=float,
        default=20.0,
        help="WebSocket ping timeout in seconds. Default: 20.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print JSON-RPC method send/receive events to stderr.",
    )
    args = parser.parse_args()
    args.url = args.url_positional or args.url
    if not args.url:
        raise SystemExit("--url or CODEX_WS_URL is required")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be greater than zero")
    return args


def main() -> None:
    asyncio.run(_run(_parse_args()))


if __name__ == "__main__":
    main()
