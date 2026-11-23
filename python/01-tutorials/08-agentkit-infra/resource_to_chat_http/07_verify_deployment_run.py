#!/usr/bin/env python3
"""验证已派发 DeploymentRun 的 Session 事件，不触发第二次执行。"""

from __future__ import annotations

import time
from typing import Any

from _clients import DataPlaneClient
from _common import emit, load_state, parser, positive_int_env, run, wait_progress
from _config import validated_config
from _deployment import verify_run_session_events


def _session_id(state: dict[str, Any], explicit: str) -> str:
    """优先使用命令行 SessionId，缺省读取 05 保存的最近一次 Run。"""

    value = (
        explicit.strip()
        or str(
            (state.get("resources", {}).get("deployment_run") or {}).get("session_id")
            or ""
        ).strip()
    )
    if not value:
        raise RuntimeError(
            "session id is missing; run 05_run_deployment.py first or pass --session-id"
        )
    return value


def _events(client: DataPlaneClient, session_id: str) -> list[dict[str, Any]]:
    """按 sequence 读取当前持久化事件快照，拒绝不完整响应。"""

    response = client.call(
        "GET",
        f"/v1/sessions/{session_id}/events",
        params={"limit": 1000, "order": "asc"},
    )
    events = response.get("data")
    if not isinstance(events, list) or not all(
        isinstance(item, dict) for item in events
    ):
        raise RuntimeError("List Events response is missing data[]")
    return events


def main() -> None:
    """轮询已有 Session，直至完成事件满足 Deployment 执行验收。"""

    cli = parser(__doc__)
    cli.add_argument(
        "--session-id", default="", help="待验证的 DeploymentRun SessionId"
    )
    cli.add_argument(
        "--expected-substring",
        default="",
        help="最终 agent.message 必须包含的文本",
    )
    cli.add_argument(
        "--require-tool",
        action="append",
        default=[],
        help="要求出现成功工具结果；可重复传入，例如 --require-tool bash",
    )
    args = cli.parse_args()
    config = validated_config(require_model_key_name=False, require_credentials=False)
    state = load_state()
    session_id = _session_id(state, args.session_id)
    required_tools = tuple(
        sorted({name.strip().lower() for name in args.require_tool if name.strip()})
    )
    if args.dry_run:
        emit(
            "dry_run",
            "验证已派发 DeploymentRun",
            json_output=args.json_output,
            session_id=session_id,
            actions=[
                "仅 GET /v1/sessions/{id}/events",
                "检查 agent.message、工具结果和 session.status_idle/end_turn",
                "不调用 Runtime /run_sse，不发送 user.message",
            ],
            status="dry_run（未访问数据面）",
        )
        return

    client = DataPlaneClient(
        config.session.endpoint_base_url,
        config.environment.env_api_key_value,
    )
    deadline = time.monotonic() + positive_int_env(
        "HARNESS_INFRA_WAIT_TIMEOUT_SECONDS", 15 * 60
    )
    latest_error = ""
    with wait_progress("验证 Deployment Session", json_output=args.json_output):
        while True:
            events = _events(client, session_id)
            try:
                verification = verify_run_session_events(
                    events,
                    expected_substring=args.expected_substring,
                    required_tools=required_tools,
                )
                break
            except RuntimeError as exc:
                latest_error = str(exc)
                if (
                    "failed" in latest_error
                    or "final answer did not contain" in latest_error
                    or "tool " in latest_error
                ):
                    raise
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "timed out waiting for Deployment Session verification: "
                        + latest_error
                    ) from None
                time.sleep(2)

    emit(
        "verified",
        "DeploymentRun Session 验证通过",
        json_output=args.json_output,
        id=session_id,
        status="completed",
        answer=verification["answer"],
        tool_names=verification["tool_names"],
        verification={
            "event_count": verification["event_count"],
            "answer_sequence": verification["answer_sequence"],
            "end_turn_sequence": verification["end_turn_sequence"],
            "expected_substring": args.expected_substring,
            "required_tools": list(required_tools),
            "read_only": True,
        },
    )


if __name__ == "__main__":
    run(main)
