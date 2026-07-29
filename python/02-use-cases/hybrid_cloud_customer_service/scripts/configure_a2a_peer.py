"""Safely configure the registered A2A data-agent peer on the main Runtime."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from collections.abc import Iterable


def merge_runtime_envs(
    existing_envs: Iterable[object] | None,
    overrides: dict[str, str],
) -> list[dict[str, str | None]]:
    """Retain every current Runtime environment value in memory."""
    merged: dict[str, str | None] = {}
    for item in existing_envs or []:
        key = getattr(item, "key", None)
        if key:
            merged[key] = getattr(item, "value", None)
    merged.update(overrides)
    return [{"Key": key, "Value": value} for key, value in merged.items()]


def run_agentkit(*args: str) -> str:
    result = subprocess.run(
        ["agentkit", *args],
        check=False,
        text=True,
        capture_output=True,
        env=os.environ | {"COLUMNS": "500"},
    )
    if result.returncode:
        # CLI diagnostics can contain sensitive control-plane configuration.
        raise SystemExit("AgentKit operation failed; detailed CLI output is intentionally hidden.")
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-id", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--rpc-url", required=True)
    parser.add_argument("--agent-name", required=True)
    parser.add_argument(
        "--capability-id",
        "--skill-id",
        dest="capability_id",
        required=True,
        help="AgentCard skills[].id; unrelated to an AgentKit Skills Center Skill",
    )
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--wait-seconds", type=int, default=180)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,62}", args.capability_id):
        raise SystemExit("AgentCard capability ID format is invalid.")

    peer_key = os.getenv("A2A_DATA_AGENT_API_KEY", "").strip()
    if not peer_key:
        raise SystemExit("A2A_DATA_AGENT_API_KEY is required but was not supplied to this process.")

    from agentkit.sdk.runtime import types as runtime_types
    from agentkit.sdk.runtime.client import AgentkitRuntimeClient

    client = AgentkitRuntimeClient(region=args.region)
    current = client.get_runtime(runtime_types.GetRuntimeRequest(runtime_id=args.runtime_id))
    overrides = {
        "A2A_DATA_AGENT_URL": args.rpc_url,
        "A2A_DATA_AGENT_API_KEY": peer_key,
        "A2A_DATA_AGENT_TIMEOUT_SECONDS": str(args.timeout_seconds),
        "A2A_DATA_AGENT_NAME": args.agent_name,
        # The A2A protocol names this AgentCard field `skills[].id`. Keep the
        # established environment key for compatibility; it is not a Skills
        # Center Skill or SKILL_SPACE_ID.
        "A2A_DATA_AGENT_SKILL_ID": args.capability_id,
    }
    merged = merge_runtime_envs(current.envs, overrides)
    client.update_runtime(
        runtime_types.UpdateRuntimeRequest(
            runtime_id=args.runtime_id,
            envs=[
                runtime_types.EnvsItemForUpdateRuntime(key=item["Key"], value=item["Value"])
                for item in merged
            ],
        )
    )
    print(
        "Main Runtime peer configuration updated with preserved environment values "
        "(changed: selected A2A Agent URL, API Key, name, AgentCard capability ID "
        "and timeout)."
    )

    run_agentkit("runtime", "release", "--runtime-id", args.runtime_id, "--region", args.region)
    deadline = time.monotonic() + args.wait_seconds
    while time.monotonic() < deadline:
        details = json.loads(
            run_agentkit(
                "runtime",
                "get",
                "--runtime-id",
                args.runtime_id,
                "--region",
                args.region,
                "--output",
                "json",
            )
        )
        status = details.get("Status", "Unknown")
        print(f"Main Runtime status: {status}")
        if status == "Ready":
            return
        if status in {"Error", "Failed", "ReleaseFailed"}:
            raise SystemExit(f"Main Runtime release failed with status: {status}")
        time.sleep(5)
    raise SystemExit(f"Main Runtime did not become Ready within {args.wait_seconds} seconds.")


if __name__ == "__main__":
    main()
