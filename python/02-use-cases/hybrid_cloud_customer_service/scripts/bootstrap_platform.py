"""Create/attach AgentKit resources without writing credentials to the repo."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections.abc import Iterable


def merge_runtime_envs(
    existing_envs: Iterable[object] | None,
    overrides: dict[str, str],
) -> list[dict[str, str | None]]:
    """Merge Runtime envs without logging their values.

    UpdateRuntime treats its Envs array as a full replacement.  Retain model
    and platform configuration in memory while changing only requested keys.
    """
    merged: dict[str, str | None] = {}
    for item in existing_envs or []:
        key = getattr(item, "key", None)
        if key:
            merged[key] = getattr(item, "value", None)
    merged.update(overrides)
    return [{"Key": key, "Value": value} for key, value in merged.items()]


def update_runtime_with_preserved_envs(
    *,
    runtime_id: str,
    region: str,
    memory_id: str | None,
    knowledge_id: str | None,
    tool_id: str | None,
    mcp_toolset_id: str | None,
    env_overrides: dict[str, str],
) -> None:
    """Apply an association update without exposing or dropping Runtime envs.

    This intentionally avoids the CLI's argv-based ``--envs-json``. Existing
    values are handled only as an opaque in-memory payload and are never
    printed, persisted, or passed through shell arguments.
    """
    from agentkit.sdk.runtime import types as runtime_types
    from agentkit.sdk.runtime.client import AgentkitRuntimeClient

    client = AgentkitRuntimeClient(region=region)
    current = client.get_runtime(runtime_types.GetRuntimeRequest(runtime_id=runtime_id))
    merged = merge_runtime_envs(current.envs, env_overrides)
    client.update_runtime(
        runtime_types.UpdateRuntimeRequest(
            runtime_id=runtime_id,
            memory_id=memory_id,
            knowledge_id=knowledge_id,
            tool_id=tool_id,
            mcp_toolset_id=mcp_toolset_id,
            envs=[
                runtime_types.EnvsItemForUpdateRuntime(
                    key=item["Key"], value=item["Value"]
                )
                for item in merged
            ],
        )
    )
    print(
        "Runtime updated with preserved environment configuration "
        f"({len(merged)} variables; changed: {', '.join(sorted(env_overrides))})."
    )


def command_env() -> dict[str, str]:
    env = os.environ.copy()
    # AgentKit 0.5.5 renders even json/yaml through Rich. A wide console keeps
    # long image URLs from being wrapped into invalid machine-readable output.
    env["COLUMNS"] = "500"
    return env


def run(*args: str) -> str:
    command = ["agentkit", *args]
    print("+", " ".join(command))
    return subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=True,
        env=command_env(),
    ).stdout.strip()


def run_json(*args: str) -> dict:
    return json.loads(run(*args, "--output", "json"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-id", required=True)
    parser.add_argument("--region", default="cn-sh")
    parser.add_argument("--memory-name", default="hybrid_customer_service_memory")
    parser.add_argument("--memory-id", help="Existing/console-created AgentKit MemoryId")
    parser.add_argument(
        "--knowledge-id",
        help="Existing published AgentKit KnowledgeId backed by hybrid-cloud Cloud Search",
    )
    parser.add_argument("--tool-id", help="Existing Ready AIO/Skills Sandbox ToolId")
    parser.add_argument("--mcp-toolset-id", help="Existing Ready MCP ToolsetId")
    parser.add_argument(
        "--skill-space-id",
        help="Skills Space ID; safely adds or updates Runtime SKILL_SPACE_ID",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=180,
        help="Maximum seconds to wait for the released Runtime to become Ready",
    )
    args = parser.parse_args()

    memory_id = args.memory_id
    if not memory_id:
        existing_memory = run(
            "memory",
            "list",
            "--name",
            args.memory_name,
            "--status",
            "Ready",
            "--provider-type",
            "MEM0",
            "--region",
            args.region,
            "--quiet",
        )
        if existing_memory:
            memory_id = existing_memory.splitlines()[-1].strip()
        else:
            try:
                run(
                    "memory",
                    "create",
                    "--name",
                    args.memory_name,
                    "--description",
                    "Hybrid customer-service preferences and summaries",
                    "--provider-type",
                    "MEM0",
                    "--strategy",
                    "Summary:conversation_summary",
                    "--strategy",
                    "Semantic:customer_facts",
                    "--strategy",
                    "UserPreference:customer_preferences",
                    "--region",
                    args.region,
                )
            except subprocess.CalledProcessError as exc:
                print(exc.stderr or exc.stdout, file=sys.stderr)
                raise SystemExit(
                    "Memory creation failed. Create a managed MEM0 memory in the console, "
                    "select its embedding/LLM models, then rerun with --memory-id <id>."
                ) from exc
            memory_id = (
                run(
                    "memory",
                    "list",
                    "--name",
                    args.memory_name,
                    "--status",
                    "Ready",
                    "--provider-type",
                    "MEM0",
                    "--region",
                    args.region,
                    "--quiet",
                )
                .splitlines()[-1]
                .strip()
            )

    knowledge_id = args.knowledge_id

    update = [
        "runtime",
        "update",
        "--runtime-id",
        args.runtime_id,
        "--memory-id",
        memory_id,
        "--region",
        args.region,
    ]
    if knowledge_id:
        update.extend(["--knowledge-id", knowledge_id])
    if args.tool_id:
        update.extend(["--tool-id", args.tool_id])
    if args.mcp_toolset_id:
        update.extend(["--mcp-toolset-id", args.mcp_toolset_id])
    if args.skill_space_id:
        update_runtime_with_preserved_envs(
            runtime_id=args.runtime_id,
            region=args.region,
            memory_id=memory_id,
            knowledge_id=knowledge_id,
            tool_id=args.tool_id,
            mcp_toolset_id=args.mcp_toolset_id,
            env_overrides={"SKILL_SPACE_ID": args.skill_space_id},
        )
    else:
        run(*update)

    run(
        "runtime",
        "release",
        "--runtime-id",
        args.runtime_id,
        "--region",
        args.region,
    )

    deadline = time.monotonic() + args.wait_seconds
    while time.monotonic() < deadline:
        details = run_json(
            "runtime",
            "get",
            "--runtime-id",
            args.runtime_id,
            "--region",
            args.region,
        )
        status = details.get("Status", "Unknown")
        print(f"Runtime status: {status}")
        if status == "Ready":
            break
        if status in {"Error", "Failed", "ReleaseFailed"}:
            raise SystemExit(f"Runtime release failed with status: {status}")
        time.sleep(5)
    else:
        raise SystemExit(
            f"Runtime did not become Ready within {args.wait_seconds} seconds."
        )

    print(f"Memory attached: {memory_id}")
    print(f"Knowledge attached: {knowledge_id or 'not configured'}")
    print(f"Tool attached: {args.tool_id or 'not configured'}")
    print(f"MCP Toolset attached: {args.mcp_toolset_id or 'not configured'}")
    print(f"Skill space configured: {args.skill_space_id or 'not configured'}")


if __name__ == "__main__":
    main()
