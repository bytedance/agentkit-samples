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

"""Create/reuse a sandbox session and invoke its A2A endpoint directly.

Skill example (CreateSession does not inject environment variables):
    python3 advanced/a2a/direct_sandbox_a2a_invoke.py \
    --sandbox-profile skill \
    --tool-id t-yes0m2osg0k6ee1en4ke \
    --session-id demo-session \
    --prompt "你有哪些技能"

SkillEnv example (CreateSession injects MODEL_AGENT_* variables):
    python3 advanced/a2a/direct_sandbox_a2a_invoke.py \
    --sandbox-profile skill-env \
    --tool-id t-yes0m2osg0k6ee1en4ke \
    --session-id demo-session \
    --prompt "你有哪些技能" \
    --model-api-key "$MODEL_API_KEY" \
    --model-provider openai \
    --model-name dola-seed-2-1-turbo-260628 \
    --model-base-url https://ark.ap-southeast.bytepluses.com/api/v3
"""

from __future__ import annotations

import argparse
import json
import sys

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

SOURCE = "direct-sandbox-a2a-invoke"
SKILL_SANDBOX_PROFILE = "skill"
SKILL_ENV_SANDBOX_PROFILE = "skill-env"
SANDBOX_PROFILES = (SKILL_SANDBOX_PROFILE, SKILL_ENV_SANDBOX_PROFILE)
MODEL_ARGUMENTS = (
    ("model_name", "--model-name"),
    ("model_provider", "--model-provider"),
    ("model_base_url", "--model-base-url"),
    ("model_api_key", "--model-api-key"),
)


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


def _session_envs_from_args(args: argparse.Namespace):
    if args.sandbox_profile == SKILL_ENV_SANDBOX_PROFILE:
        return _model_envs_from_args(args)

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

    # The Skill image owns its model configuration. Passing None ensures the
    # CreateSession request does not contain session-level environment variables.
    return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create/reuse an AgentKit sandbox session and invoke A2A synchronously."
    )
    parser.add_argument(
        "--sandbox-profile",
        choices=SANDBOX_PROFILES,
        default=SKILL_SANDBOX_PROFILE,
        help=(
            "Sandbox runtime profile. 'skill' (default) injects no CreateSession "
            "environment variables; 'skill-env' injects MODEL_AGENT_* variables."
        ),
    )
    parser.add_argument("--tool-id", required=True, help="Sandbox tool ID.")
    parser.add_argument(
        "--session-id",
        required=True,
        help="User session ID used to create or find the sandbox instance.",
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="Prompt to send to the sandbox A2A agent.",
    )
    parser.add_argument(
        "--model-name",
        help="Model name to inject as MODEL_AGENT_NAME when creating a session.",
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
    resolved_prompt = args.prompt.strip()
    if not resolved_prompt:
        print(json.dumps(_error_payload(ValueError("--prompt is required"))))
        return 1

    try:
        session = ensure_sandbox_session(
            session_id=args.session_id,
            tool_id=args.tool_id,
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
                "user_id": "agentkit-sandbox-invoke",
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
        output = _task_output(
            task=task,
            session=session,
            source=SOURCE,
        )

        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0 if output.get("ok") else 1
    except Exception as exc:
        print(
            json.dumps(_error_payload(exc), ensure_ascii=False, indent=2),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
