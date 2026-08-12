#!/usr/bin/env python3
"""Chat with Codex or OpenCode running inside an AgentKit sandbox.

This is a ``you>`` / ``codex>`` style terminal client. It does not start the
full-screen agent TUI and does not use Codex app-server or OpenCode serve.
Instead it keeps one sandbox shell WebSocket open and runs the agent's headless
CLI once per turn:

* Codex: ``codex exec --json`` and then ``codex exec resume --json``.
* OpenCode: ``opencode run --format json`` and then ``--session <id>``.

The agent conversation ID is extracted from JSONL output and reused, so turns
share context while the local UI remains a simple interactive chat.

Examples::

    python scripts/run_agent_in_sandbox.py --session-id demo codex
    python scripts/run_agent_in_sandbox.py --session-id demo opencode
    python scripts/run_agent_in_sandbox.py -s demo --message "inspect this repo" codex
    python scripts/run_agent_in_sandbox.py -s demo codex -- --model gpt-5
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shlex
import sys
import threading
import time
import uuid
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit, urlunsplit

AGENTS = ("codex", "opencode")
DEFAULT_WORKDIR = "/home/gem"
DEFAULT_TIMEOUT_SECONDS = 1800
DEFAULT_OPENCODE_FINISH_INTERRUPT_DELAY = 0.5
TERMINAL_PATH = "/v1/shell/ws"


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _parse_header(value: str) -> tuple[str, str]:
    name, separator, header_value = value.partition(":")
    if not separator or not name.strip():
        raise argparse.ArgumentTypeError("header must be in 'Name: Value' format")
    return name.strip(), header_value.strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Chat with Codex or OpenCode in an AgentKit sandbox without an "
            "agent app server."
        ),
    )
    parser.add_argument(
        "--url",
        default=os.getenv("SANDBOX_WS_URL", ""),
        help=(
            "Existing sandbox endpoint or /v1/shell/ws URL. Usually omitted; "
            "--session-id resolves it automatically."
        ),
    )
    parser.add_argument(
        "--session-id",
        "--sid",
        "-s",
        help="Logical AgentKit sandbox session ID.",
    )
    parser.add_argument("--tool-id", help="Sandbox tool ID when not locally cached.")
    parser.add_argument("--tool-name", help="Sandbox tool name when ID is omitted.")
    parser.add_argument(
        "--tool-type",
        choices=("CodeEnv", "SkillEnv"),
        default="CodeEnv",
        help="Tool type used during resolution (default: CodeEnv).",
    )
    parser.add_argument(
        "--ttl",
        type=_positive_int,
        help="Sandbox lifetime in seconds when a session must be created.",
    )
    parser.add_argument(
        "--workdir",
        default=DEFAULT_WORKDIR,
        help=f"Remote agent working directory (default: {DEFAULT_WORKDIR}).",
    )
    parser.add_argument(
        "--thread-id",
        default=os.getenv("AGENT_THREAD_ID", ""),
        help="Resume an existing Codex/OpenCode conversation.",
    )
    parser.add_argument(
        "--message",
        help="Run one turn and exit instead of opening the interactive prompt.",
    )
    parser.add_argument(
        "--multiline",
        action="store_true",
        help="Enable multiline local prompt input.",
    )
    parser.add_argument(
        "--timeout",
        type=_positive_float,
        default=float(os.getenv("AGENT_TURN_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)),
        help=f"Per-turn timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS}).",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("SANDBOX_WS_TOKEN", ""),
        help="Optional bearer token WebSocket header.",
    )
    parser.add_argument(
        "--header",
        action="append",
        type=_parse_header,
        help="Extra WebSocket header in 'Name: Value' form; may be repeated.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print raw agent events and ignored remote output to stderr.",
    )
    parser.add_argument(
        "--opencode-finish-interrupt-delay",
        type=_positive_float,
        default=float(
            os.getenv(
                "OPENCODE_FINISH_INTERRUPT_DELAY",
                DEFAULT_OPENCODE_FINISH_INTERRUPT_DELAY,
            )
        ),
        help=(
            "Seconds to wait after OpenCode step_finish before sending Ctrl-C "
            "to unblock opencode run (default: "
            f"{DEFAULT_OPENCODE_FINISH_INTERRUPT_DELAY})."
        ),
    )
    parser.add_argument("agent", choices=AGENTS, help="Headless agent CLI to use.")
    parser.add_argument(
        "agent_args",
        nargs=argparse.REMAINDER,
        help="Extra agent CLI options; prefix them with -- when needed.",
    )
    return parser


def terminal_websocket_url(input_url: str) -> str:
    """Convert a sandbox endpoint to its shell WebSocket URL."""
    value = input_url.strip()
    if not value:
        raise ValueError("sandbox URL must not be empty")
    split = urlsplit(value)
    if split.scheme not in {"http", "https", "ws", "wss"}:
        raise ValueError("sandbox URL must use http, https, ws, or wss")
    if not split.netloc:
        raise ValueError("sandbox URL must include a host")
    if split.username or split.password:
        raise ValueError("userinfo credentials are not supported")
    if split.fragment:
        raise ValueError("sandbox URL must not include a fragment")

    path = split.path.rstrip("/")
    if "/v1/codex/app-server" in path:
        raise ValueError("provide a sandbox endpoint, not a Codex app-server URL")
    if not path.endswith(TERMINAL_PATH):
        path = f"{path}{TERMINAL_PATH}" if path else TERMINAL_PATH

    # This intentionally matches agentkit sandbox exec URL construction.
    scheme = "ws" if split.scheme in {"http", "https"} else split.scheme
    return urlunsplit((scheme, split.netloc, path, split.query, ""))


def _extra_agent_args(args: Sequence[str]) -> list[str]:
    result = list(args)
    if result[:1] == ["--"]:
        result.pop(0)
    return result


def build_agent_turn_command(
    agent: str,
    prompt: str,
    *,
    conversation_id: str | None,
    workdir: str,
    agent_args: Sequence[str] = (),
) -> str:
    """Build a shell-safe, headless agent command for one chat turn."""
    if agent not in AGENTS:
        raise ValueError(f"unsupported agent: {agent}")
    if not prompt.strip():
        raise ValueError("prompt must not be empty")

    extra = _extra_agent_args(agent_args)
    if agent == "codex":
        if conversation_id:
            argv = [
                "codex",
                "exec",
                "resume",
                "--json",
                "--skip-git-repo-check",
                *extra,
                conversation_id,
            ]
        else:
            argv = [
                "codex",
                "exec",
                "--json",
                "--color",
                "never",
                "--skip-git-repo-check",
                *extra,
            ]
    else:
        argv = ["opencode", "run", "--format", "json", *extra]
        if conversation_id:
            argv.extend(["--session", conversation_id])

    # Avoid putting arbitrary user text directly into shell syntax. The prompt
    # is transported as base64 and decoded into one quoted argv value remotely.
    encoded_prompt = base64.b64encode(prompt.encode("utf-8")).decode("ascii")
    prompt_assignment = (
        f"agentkit_chat_prompt=$(printf %s {shlex.quote(encoded_prompt)} | base64 -d)"
    )
    invocation = f'{shlex.join(argv)} "$agentkit_chat_prompt"'
    return f"cd -- {shlex.quote(workdir)} && {prompt_assignment} && {invocation}"


class AgentEventParser:
    """Parse Codex/OpenCode JSONL and print only assistant text."""

    def __init__(
        self,
        agent: str,
        *,
        conversation_id: str = "",
        verbose: bool = False,
    ) -> None:
        self.agent = agent
        self.conversation_id = conversation_id
        self.verbose = verbose
        self.turn_had_text = False
        self.turn_finished_at: float | None = None
        self.turn_errors: list[str] = []
        self._item_text: dict[str, str] = {}

    def start_turn(self) -> None:
        self.turn_had_text = False
        self.turn_finished_at = None
        self.turn_errors.clear()
        self._item_text.clear()

    def parse_line(self, line: str) -> None:
        value = line.strip()
        if not value.startswith("{"):
            return
        try:
            event = json.loads(value)
        except json.JSONDecodeError:
            return
        if not isinstance(event, dict):
            return
        if self.verbose:
            print(
                f"[agent-event] {json.dumps(event, ensure_ascii=False)}",
                file=sys.stderr,
            )

        if self.agent == "codex":
            self._parse_codex(event)
        else:
            self._parse_opencode(event)

    def _parse_codex(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "thread.started":
            thread_id = event.get("thread_id")
            if isinstance(thread_id, str) and thread_id:
                self.conversation_id = thread_id
            return
        if event_type in {"error", "turn.failed"}:
            error = event.get("error")
            if isinstance(error, dict):
                error = error.get("message")
            message = event.get("message") or error
            if isinstance(message, str):
                self.turn_errors.append(message)
            return
        if event_type not in {"item.updated", "item.completed"}:
            return
        item = event.get("item")
        if not isinstance(item, dict) or item.get("type") != "agent_message":
            return
        text = item.get("text")
        if not isinstance(text, str):
            return
        item_id = str(item.get("id") or "agent-message")
        previous = self._item_text.get(item_id, "")
        delta = text.removeprefix(previous)
        self._item_text[item_id] = text
        self._emit_text(delta)

    def _parse_opencode(self, event: dict[str, Any]) -> None:
        session_id = event.get("sessionID") or event.get("session_id")
        if isinstance(session_id, str) and session_id:
            self.conversation_id = session_id

        event_type = event.get("type")
        if event_type == "step_finish":
            self.turn_finished_at = time.monotonic()
            return
        if event_type in {"error", "session.error"}:
            error = event.get("error") or event.get("message")
            if isinstance(error, dict):
                error = error.get("message")
            if isinstance(error, str):
                self.turn_errors.append(error)
            return

        if event_type in {"message.part.delta", "text_delta", "delta"}:
            delta = event.get("delta")
            if isinstance(delta, str):
                self._emit_text(delta)
            return
        if event_type != "text":
            return
        part = event.get("part")
        text = part.get("text") if isinstance(part, dict) else event.get("text")
        if not isinstance(text, str):
            return
        part_id = str(part.get("id") if isinstance(part, dict) else "text")
        previous = self._item_text.get(part_id, "")
        delta = text.removeprefix(previous)
        self._item_text[part_id] = text
        self._emit_text(delta)

    def _emit_text(self, text: str) -> None:
        if not text:
            return
        print(text, end="", flush=True)
        self.turn_had_text = True


class SandboxAgentChat:
    """One persistent sandbox shell connection used for multiple CLI turns."""

    def __init__(
        self,
        ws_url: str,
        *,
        agent: str,
        headers: Sequence[tuple[str, str]],
        conversation_id: str = "",
        verbose: bool = False,
        opencode_finish_interrupt_delay: float = (
            DEFAULT_OPENCODE_FINISH_INTERRUPT_DELAY
        ),
    ) -> None:
        self.ws_url = ws_url
        self.headers = list(headers)
        self.verbose = verbose
        self.opencode_finish_interrupt_delay = opencode_finish_interrupt_delay
        self.parser = AgentEventParser(
            agent,
            conversation_id=conversation_id,
            verbose=verbose,
        )
        self.ready = threading.Event()
        self.closed = threading.Event()
        self.turn_done = threading.Event()
        self.websocket: Any = None
        self._thread: threading.Thread | None = None
        self._line_buffer = ""
        self._turn_marker = ""
        self._turn_exit_code: int | None = None
        self._finish_interrupt_sent = False
        self._connection_errors: list[str] = []
        self._ignored_output: list[str] = []

    @property
    def conversation_id(self) -> str:
        return self.parser.conversation_id

    def reset_conversation(self) -> None:
        self.parser.conversation_id = ""

    def connect(self, timeout: float = 30) -> None:
        try:
            import websocket
        except ImportError as exc:
            raise RuntimeError(
                "websocket-client is required: pip install websocket-client"
            ) from exc

        websocket_headers = [f"{name}: {value}" for name, value in self.headers]
        self.websocket = websocket.WebSocketApp(
            self.ws_url,
            header=websocket_headers or None,
            on_open=self._on_open,
            on_message=self._on_message,
            on_close=self._on_close,
            on_error=self._on_error,
        )
        self._thread = threading.Thread(
            target=self.websocket.run_forever,
            name="sandbox-agent-chat-websocket",
            daemon=True,
        )
        self._thread.start()
        if not self.ready.wait(timeout):
            detail = (
                self._connection_errors[-1] if self._connection_errors else "timeout"
            )
            raise RuntimeError(f"sandbox terminal did not become ready: {detail}")
        if self.closed.is_set():
            detail = (
                self._connection_errors[-1]
                if self._connection_errors
                else "connection closed"
            )
            raise RuntimeError(f"sandbox terminal connection failed: {detail}")

    def close(self) -> None:
        if self.websocket:
            self.websocket.close()
        self.closed.set()
        if self._thread:
            self._thread.join(timeout=2)

    def run_turn(self, command: str, *, timeout: float) -> int:
        if not self.websocket or not self.ready.is_set():
            raise RuntimeError("sandbox terminal is not connected")
        if self.closed.is_set():
            raise RuntimeError("sandbox terminal connection is closed")

        self.parser.start_turn()
        self._ignored_output.clear()
        self._turn_exit_code = None
        self._turn_marker = f"__AGENTKIT_CHAT_DONE_{uuid.uuid4().hex}__"
        self._finish_interrupt_sent = False
        self.turn_done.clear()
        wrapped = (
            f"{command}; agentkit_chat_rc=$?; "
            f"printf '\\n{self._turn_marker}:%s\\n' \"$agentkit_chat_rc\""
        )
        self._send({"type": "input", "data": f"{wrapped}\n"})

        deadline = time.monotonic() + timeout
        try:
            while not self.turn_done.wait(0.1):
                if self.closed.is_set():
                    raise RuntimeError("sandbox terminal closed during the agent turn")
                self._interrupt_stuck_opencode_after_finish()
                if time.monotonic() >= deadline:
                    self._send({"type": "input", "data": "\x03"})
                    raise TimeoutError(f"agent turn timed out after {timeout:g}s")
        except KeyboardInterrupt:
            self._send({"type": "input", "data": "\x03"})
            self.turn_done.wait(5)
            raise

        exit_code = self._turn_exit_code if self._turn_exit_code is not None else 1
        if (
            exit_code
            and self._finish_interrupt_sent
            and self.parser.turn_finished_at is not None
        ):
            # OpenCode can keep `opencode run` alive after emitting step_finish.
            # The client sends Ctrl-C only after the model turn has completed,
            # so the resulting 130 exit status should not be reported as a turn error.
            exit_code = 0
        if exit_code and not self.parser.turn_errors:
            detail = next(
                (line for line in reversed(self._ignored_output) if line.strip()),
                "agent command failed",
            )
            self.parser.turn_errors.append(detail.strip())
        return exit_code

    def _interrupt_stuck_opencode_after_finish(self) -> None:
        if self.parser.agent != "opencode":
            return
        if self._finish_interrupt_sent:
            return
        finished_at = self.parser.turn_finished_at
        if finished_at is None:
            return
        if time.monotonic() - finished_at < self.opencode_finish_interrupt_delay:
            return
        self._finish_interrupt_sent = True
        if self.verbose:
            print(
                "[client] OpenCode step finished; sending Ctrl-C to unblock shell",
                file=sys.stderr,
            )
        self._send({"type": "input", "data": "\x03"})

    def _send(self, payload: dict[str, Any]) -> None:
        self.websocket.send(json.dumps(payload, ensure_ascii=False))

    def _on_open(self, _websocket: Any) -> None:
        self._send({"type": "resize", "data": {"cols": 160, "rows": 48}})

    def _on_message(self, _websocket: Any, raw_message: str | bytes) -> None:
        if isinstance(raw_message, bytes):
            raw_message = raw_message.decode("utf-8", errors="replace")
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            return
        if not isinstance(message, dict):
            return

        message_type = message.get("type")
        if message_type == "ready":
            self.ready.set()
            return
        if message_type == "output":
            data = message.get("data")
            if data is not None:
                self._consume_output(str(data))
            return
        if message_type == "ping":
            timestamp = message.get("timestamp", message.get("data"))
            self._send({"type": "pong", "data": {"timestamp": timestamp}})
            return
        if message_type == "error":
            self._connection_errors.append(str(message.get("data") or "terminal error"))

    def _on_close(self, _websocket: Any, _code: Any, _message: Any) -> None:
        self.closed.set()
        self.ready.set()
        self.turn_done.set()

    def _on_error(self, _websocket: Any, error: Any) -> None:
        self._connection_errors.append(str(error))
        self.closed.set()
        self.ready.set()
        self.turn_done.set()

    def _consume_output(self, data: str) -> None:
        self._line_buffer += data.replace("\r", "")
        while "\n" in self._line_buffer:
            line, self._line_buffer = self._line_buffer.split("\n", 1)
            marker_prefix = f"{self._turn_marker}:" if self._turn_marker else ""
            if marker_prefix and line.startswith(marker_prefix):
                try:
                    self._turn_exit_code = int(line[len(marker_prefix) :].strip())
                except ValueError:
                    self._turn_exit_code = 1
                self.turn_done.set()
                continue

            self.parser.parse_line(line)
            if not line.lstrip().startswith("{"):
                self._ignored_output.append(line)
                if self.verbose and line.strip():
                    print(f"[remote] {line}", file=sys.stderr)


def _session_websocket_url(args: argparse.Namespace) -> tuple[str, str]:
    if args.url:
        return terminal_websocket_url(args.url), args.session_id or "direct-ws"

    from agentkit.toolkit.cli.sandbox.sandbox_client import (
        find_session_result_any_tool,
    )
    from agentkit.toolkit.cli.sandbox.session_create import ensure_sandbox_session

    tool_id = args.tool_id
    if args.session_id and not tool_id and not args.tool_name:
        cached = find_session_result_any_tool(args.session_id)
        cached_tool_id = cached.get("tool_id") if isinstance(cached, dict) else None
        if isinstance(cached_tool_id, str) and cached_tool_id.strip():
            tool_id = cached_tool_id.strip()

    session = ensure_sandbox_session(
        session_id=args.session_id,
        tool_id=tool_id,
        tool_name=args.tool_name,
        tool_type=args.tool_type,
        ttl=args.ttl,
    )
    session_id = session.get("session_id")
    endpoint = session.get("endpoint")
    if not isinstance(session_id, str) or not session_id:
        raise RuntimeError("sandbox session response is missing session_id")
    if not isinstance(endpoint, str) or not endpoint:
        raise RuntimeError("sandbox session response is missing endpoint")
    return terminal_websocket_url(endpoint), session_id


def _print_turn_result(chat: SandboxAgentChat, exit_code: int) -> None:
    print()
    for error in chat.parser.turn_errors:
        print(f"error: {error}", file=sys.stderr)
    if exit_code and not chat.parser.turn_errors:
        print(f"error: agent exited with status {exit_code}", file=sys.stderr)


def _run_prompt(
    chat: SandboxAgentChat,
    args: argparse.Namespace,
    prompt: str,
) -> int:
    command = build_agent_turn_command(
        args.agent,
        prompt,
        conversation_id=chat.conversation_id or None,
        workdir=args.workdir,
        agent_args=args.agent_args,
    )
    print(f"{args.agent}> ", end="", flush=True)
    exit_code = chat.run_turn(command, timeout=args.timeout)
    _print_turn_result(chat, exit_code)
    return exit_code


def _interactive_chat(chat: SandboxAgentChat, args: argparse.Namespace) -> None:
    try:
        from prompt_toolkit import PromptSession
    except ImportError as exc:
        raise RuntimeError("prompt_toolkit is required") from exc

    prompt_session: Any = PromptSession()
    while True:
        try:
            prompt = prompt_session.prompt("you> ", multiline=args.multiline).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not prompt:
            continue
        if prompt in {"/exit", "/quit"}:
            return
        if prompt == "/help":
            print("/new  /thread  /help  /exit  /quit")
            continue
        if prompt == "/thread":
            print(chat.conversation_id or "no agent thread")
            continue
        if prompt == "/new":
            chat.reset_conversation()
            print("[thread] next message starts a new conversation", file=sys.stderr)
            continue
        try:
            _run_prompt(chat, args, prompt)
        except KeyboardInterrupt:
            print("\n[interrupted]", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 - keep the chat usable after turn errors.
            print(f"error: {exc}", file=sys.stderr)


def run(args: argparse.Namespace) -> int:
    ws_url, sandbox_session_id = _session_websocket_url(args)
    headers = list(args.header or [])
    if args.token:
        headers.append(("Authorization", f"Bearer {args.token}"))

    chat = SandboxAgentChat(
        ws_url,
        agent=args.agent,
        headers=headers,
        conversation_id=args.thread_id,
        verbose=args.verbose,
        opencode_finish_interrupt_delay=args.opencode_finish_interrupt_delay,
    )
    print(f"[sandbox] {sandbox_session_id}", file=sys.stderr)
    chat.connect()
    try:
        if args.message:
            return _run_prompt(chat, args, args.message)
        _interactive_chat(chat, args)
        return 0
    finally:
        chat.close()


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001 - CLI boundary reports SDK/network errors.
        exit_code = getattr(exc, "exit_code", 1)
        if str(exc):
            print(f"Error: {exc}", file=sys.stderr)
        return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
