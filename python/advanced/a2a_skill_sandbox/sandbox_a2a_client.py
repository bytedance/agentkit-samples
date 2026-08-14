#!/usr/bin/env python3
#
# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Create/reuse an AgentKit Skills Sandbox session and invoke it through A2A."""

from __future__ import annotations

import argparse
import json

from agentkit.toolkit.cli.sandbox.a2a_client import (
    DEFAULT_A2A_HISTORY_LENGTH,
    DEFAULT_A2A_PATH,
    DEFAULT_A2A_POLL_INTERVAL_SECONDS,
    DEFAULT_A2A_TIMEOUT_SECONDS,
    poll_task_until_terminal,
    send_message_nonblocking,
)
from agentkit.toolkit.cli.sandbox.cli_invoke import (
    _error_payload,
    _task_output,
)
from agentkit.toolkit.cli.sandbox.config_store import (
    config_default_str,
    configured_sandbox_config,
)
from agentkit.toolkit.cli.sandbox.env_config import build_invoke_session_envs
from agentkit.toolkit.cli.sandbox.session_create import ensure_sandbox_session
from agentkit.toolkit.cli.sandbox.tool_resolve import SandboxToolType

SOURCE = "a2a-skill-sandbox-sample"
DEFAULT_REQUEST_USER_ID = "agentkit-a2a-skill-sandbox"
SKILL_SANDBOX_PROFILE = "skill"
SKILL_ENV_SANDBOX_PROFILE = "skill-env"
SANDBOX_PROFILES = (SKILL_SANDBOX_PROFILE, SKILL_ENV_SANDBOX_PROFILE)
MODEL_ARGUMENTS = (
    ("model_name", "--model-name"),
    ("model_provider", "--model-provider"),
    ("model_base_url", "--model-base-url"),
    ("model_api_key", "--model-api-key"),
)


def invoke_sandbox_a2a(
    *,
    sandbox_profile: str,
    tool_id: str,
    session_id: str,
    prompt: str,
    model_name: str | None = None,
    model_provider: str | None = None,
    model_base_url: str | None = None,
    model_api_key: str | None = None,
    source: str = SOURCE,
    request_user_id: str = DEFAULT_REQUEST_USER_ID,
):
    """Create/reuse a sandbox session, send an A2A message, and return output."""
    resolved_prompt = prompt.strip()
    if not resolved_prompt:
        raise ValueError("--prompt is required")

    args = argparse.Namespace(
        sandbox_profile=sandbox_profile,
        model_name=model_name,
        model_provider=model_provider,
        model_base_url=model_base_url,
        model_api_key=model_api_key,
    )
    session = ensure_sandbox_session(
        session_id=session_id,
        tool_id=tool_id,
        tool_type=SandboxToolType.SKILL_ENV.value,
        envs=_session_envs_from_args(args),
        resolve_tool=False,
        include_tos_mount_points=False,
    )

    task_start = send_message_nonblocking(
        endpoint=session.get("endpoint"),
        prompt=resolved_prompt,
        a2a_path=DEFAULT_A2A_PATH,
        request_metadata={
            "session_id": str(session.get("session_id") or ""),
            "user_id": request_user_id,
        },
        history_length=DEFAULT_A2A_HISTORY_LENGTH,
        timeout=min(60, DEFAULT_A2A_TIMEOUT_SECONDS),
    )

    task = poll_task_until_terminal(
        endpoint=session.get("endpoint"),
        task_id=task_start.task_id,
        a2a_path=DEFAULT_A2A_PATH,
        history_length=DEFAULT_A2A_HISTORY_LENGTH,
        timeout=DEFAULT_A2A_TIMEOUT_SECONDS,
        interval=DEFAULT_A2A_POLL_INTERVAL_SECONDS,
    )
    return _task_output(
        task=task,
        session=session,
        source=source,
    )


def _session_envs_from_args(args: argparse.Namespace):
    if args.sandbox_profile == SKILL_ENV_SANDBOX_PROFILE:
        return _model_envs_from_args(args)
    if args.sandbox_profile != SKILL_SANDBOX_PROFILE:
        raise ValueError(
            f"--sandbox-profile must be one of {', '.join(SANDBOX_PROFILES)}"
        )

    model_arguments = [
        option
        for attribute, option in MODEL_ARGUMENTS
        if getattr(args, attribute, None) is not None
    ]
    if model_arguments:
        raise ValueError(
            f"{', '.join(model_arguments)} can only be used with "
            f"--sandbox-profile {SKILL_ENV_SANDBOX_PROFILE}"
        )

    # Skill profile owns its runtime model configuration. Do not inject
    # session-level environment variables through CreateSession.
    return None


def _model_envs_from_args(args: argparse.Namespace):
    config_defaults = configured_sandbox_config()
    return build_invoke_session_envs(
        model_name=args.model_name
        or config_default_str("model-name", data=config_defaults),
        model_provider=args.model_provider
        or config_default_str("model-provider", data=config_defaults),
        model_base_url=args.model_base_url
        or config_default_str("model-base-url", data=config_defaults),
        model_api_key=args.model_api_key
        or config_default_str("model-api-key", data=config_defaults),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create/reuse an AgentKit Skills Sandbox session and invoke its A2A "
            "endpoint synchronously."
        )
    )
    parser.add_argument(
        "--sandbox-profile",
        choices=SANDBOX_PROFILES,
        default=SKILL_SANDBOX_PROFILE,
        help=(
            "'skill' (default) injects no CreateSession envs; 'skill-env' "
            "injects MODEL_AGENT_* envs."
        ),
    )
    parser.add_argument("--tool-id", required=True, help="Skills Sandbox Tool ID.")
    parser.add_argument(
        "--session-id",
        required=True,
        help="User session ID used to create or reuse the sandbox instance.",
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="Prompt to send to the sandbox A2A agent.",
    )
    parser.add_argument(
        "--model-name",
        help="Model name to inject as MODEL_AGENT_NAME for skill-env sessions.",
    )
    parser.add_argument(
        "--model-provider",
        help="Model provider to inject as MODEL_AGENT_PROVIDER.",
    )
    parser.add_argument(
        "--model-base-url",
        help="Model API base URL to inject as MODEL_AGENT_API_BASE.",
    )
    parser.add_argument(
        "--model-api-key",
        help="Model API key to inject as MODEL_AGENT_API_KEY.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        output = invoke_sandbox_a2a(
            sandbox_profile=args.sandbox_profile,
            tool_id=args.tool_id,
            session_id=args.session_id,
            prompt=args.prompt,
            model_name=args.model_name,
            model_provider=args.model_provider,
            model_base_url=args.model_base_url,
            model_api_key=args.model_api_key,
        )
    except Exception as exc:
        print(json.dumps(_error_payload(exc), ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
