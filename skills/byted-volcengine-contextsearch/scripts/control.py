#!/usr/bin/env python3
# Copyright (c) 2026 Beijing Volcano Engine Technology Ltd.
# SPDX-License-Identifier: Apache-2.0

from __future__ import print_function

import argparse
import json
import os
import subprocess
import sys

from modules.console import CONSOLE_ACTIONS


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(BASE_DIR, "scripts", "contextsearch_cli.py")


def emit(payload, exit_code=0):
    print(json.dumps(payload, ensure_ascii=False, default=str))
    sys.exit(exit_code)


def _json_from_stdout(stdout):
    text = (stdout or "").strip()
    if not text:
        return None
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except ValueError:
            continue
    return None


def run_cli(goal, cli_args, steps_completed=None):
    steps = list(steps_completed or [])
    proc = subprocess.run(
        [sys.executable, CLI] + cli_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if proc.stderr:
        sys.stderr.write(proc.stderr)

    payload = _json_from_stdout(proc.stdout)
    if payload is None:
        emit(
            {
                "status": "error",
                "goal": goal,
                "error": "Invalid CLI Output",
                "details": proc.stdout.strip(),
                "steps_completed": steps,
            },
            proc.returncode or 1,
        )

    if isinstance(payload, dict) and payload.get("status") == "success":
        emit(
            {
                "status": "success",
                "goal": goal,
                "data": payload.get("data"),
                "steps_completed": steps,
            },
            0,
        )

    if isinstance(payload, dict):
        emit(
            {
                "status": payload.get("status", "error"),
                "goal": goal,
                "error": payload.get("error", "CLI Error"),
                "details": payload.get("details", ""),
                "data": payload.get("data", {}),
                "steps_completed": steps,
            },
            proc.returncode or 1,
        )

    emit(
        {
            "status": "success" if proc.returncode == 0 else "error",
            "goal": goal,
            "data": payload,
            "steps_completed": steps,
        },
        proc.returncode,
    )


def add_common_scene_args(parser, require_scene_type=True):
    parser.add_argument("--id", required=True, help="ContextSearch scene ID")
    parser.add_argument("--project", default="default", help="Project name")
    if require_scene_type:
        parser.add_argument(
            "--scene-type",
            required=True,
            help="RAG, IMAGE_SEARCH, VIDEO_SEARCH, or AGENTIC_SEARCH",
        )


def build_parser():
    parser = argparse.ArgumentParser(
        description="Volcano Engine ContextSearch goal-based control plane CLI"
    )
    sub = parser.add_subparsers(dest="goal", required=True)

    p = sub.add_parser("list-actions", help="List console control-plane actions")
    p.set_defaults(list_actions=True)

    p = sub.add_parser("call-action", help="Forward to a console control-plane action")
    p.add_argument(
        "console_command", help="Action command from `control.py list-actions`"
    )

    p = sub.add_parser(
        "create-agentic-search",
        help="Create an AgenticSearch scene using the console workflow",
    )
    p.add_argument("--name", required=True, help="Scene name")
    p.add_argument("--project", default="default", help="Project name")
    p.add_argument("--description", default="", help="Scene description")
    p.add_argument("--resource-tags", default="", help="Resource tags JSON array")
    p.add_argument(
        "--max-attempts",
        type=int,
        default=30,
        help="Builtin deployment polling attempts",
    )
    p.add_argument(
        "--poll-interval-ms",
        type=int,
        default=1000,
        help="Builtin deployment polling interval",
    )

    p = sub.add_parser(
        "create-scene", help="Create a regular scene or AgenticSearch scene"
    )
    p.add_argument(
        "--scene-type",
        required=True,
        help="RAG, IMAGE_SEARCH, VIDEO_SEARCH, or AGENTIC_SEARCH",
    )
    p.add_argument("--name", required=True, help="Scene name")
    p.add_argument("--project", default="default", help="Project name")
    p.add_argument("--description", default="", help="Scene description")
    p.add_argument("--resource-tags", default="", help="Resource tags JSON array")
    p.add_argument(
        "--max-attempts",
        type=int,
        default=30,
        help="Builtin deployment polling attempts",
    )
    p.add_argument(
        "--poll-interval-ms",
        type=int,
        default=1000,
        help="Builtin deployment polling interval",
    )

    p = sub.add_parser("list-scenes", help="List ContextSearch scenes")
    p.add_argument("--page-number", type=int, default=1, help="Page number")
    p.add_argument("--page-size", type=int, default=12, help="Page size")

    p = sub.add_parser("get-scene", help="Get regular scene detail")
    add_common_scene_args(p)
    p.add_argument(
        "--is-demo", action="store_true", default=False, help="Read demo scene"
    )

    p = sub.add_parser("publish-scene", help="Publish a regular scene version")
    add_common_scene_args(p)
    p.add_argument("--version", required=True, help="Version string, for example 1.0.0")
    p.add_argument("--resource-spec", default="vci.n3i.2c-4gi", help="Resource spec")
    p.add_argument("--replicas", type=int, default=2, help="Replica count")

    p = sub.add_parser("start-scene", help="Start a regular scene instance")
    add_common_scene_args(p)

    p = sub.add_parser("stop-scene", help="Stop a regular scene instance")
    add_common_scene_args(p)

    p = sub.add_parser(
        "delete-scene", help="Delete a regular scene; --confirm must equal --id"
    )
    add_common_scene_args(p)
    p.add_argument("--confirm", required=True, help="Must exactly match --id")

    p = sub.add_parser("specs", help="List available CPU resource specs")
    p.add_argument(
        "--show-all", action="store_true", default=False, help="Show GPU specs too"
    )

    p = sub.add_parser("list-models", help="List public or user models")
    p.add_argument(
        "--user",
        action="store_true",
        default=False,
        help="List user models instead of public models",
    )
    p.add_argument("--project", default="default", help="Project name")
    p.add_argument("--name", default="", help="Name filter")
    p.add_argument("--page-number", type=int, default=1, help="Page number")
    p.add_argument("--page-size", type=int, default=10, help="Page size")

    p = sub.add_parser("get-model", help="Get model detail")
    p.add_argument("--id", required=True, help="Model ID")
    p.add_argument("--project", default="default", help="Project name")

    p = sub.add_parser("list-deployments", help="List builtin or user deployments")
    p.add_argument(
        "--user",
        action="store_true",
        default=False,
        help="List user deployments instead of builtin deployments",
    )
    p.add_argument("--project", default="default", help="Project name")
    p.add_argument("--name", default="", help="Name filter")
    p.add_argument("--page-number", type=int, default=1, help="Page number")
    p.add_argument("--page-size", type=int, default=10, help="Page size")

    p = sub.add_parser("get-deployment", help="Get deployment detail")
    p.add_argument("--id", required=True, help="Deployment ID")
    p.add_argument("--project", default="default", help="Project name")

    p = sub.add_parser("deployment-usage", help="Get deployment usage")
    p.add_argument("--id", required=True, help="Deployment ID")
    p.add_argument("--start-time", default=None, help="Unix seconds")
    p.add_argument("--end-time", default=None, help="Unix seconds")
    p.add_argument(
        "--interval", type=int, default=86400, help="Usage interval in seconds"
    )

    p = sub.add_parser("list-api-keys", help="List ContextSearch API keys")
    p.add_argument("--project", default="default", help="Project name")
    p.add_argument("--name", default="", help="Name filter")
    p.add_argument("--page-number", type=int, default=1, help="Page number")
    p.add_argument("--page-size", type=int, default=10, help="Page size")

    p = sub.add_parser("create-api-key", help="Create a ContextSearch API key")
    p.add_argument("--name", required=True, help="API key name")
    p.add_argument("--project", default="default", help="Project name")

    p = sub.add_parser(
        "delete-api-key",
        help="Delete a ContextSearch API key; --confirm must equal --id",
    )
    p.add_argument("--id", required=True, help="API key ID")
    p.add_argument("--project", default="default", help="Project name")
    p.add_argument("--confirm", required=True, help="Must exactly match --id")

    for spec in CONSOLE_ACTIONS:
        if spec.command in {"list"}:
            continue
        p = sub.add_parser(
            spec.command,
            help="Forward to console action %s" % spec.action,
            description=(
                "Forward to contextsearch_cli.py console %s (%s, %s). "
                "Common forwarded flags include --body-json, --body-file, --project, --id, "
                "--scene-id, --page-number, --page-size, --dry-run, and --confirm."
            )
            % (spec.command, spec.action, spec.method),
        )
        p.set_defaults(console_command=spec.command, console_action=spec.action)

    return parser


def dispatch(args, passthrough=None):
    goal = args.goal
    passthrough = list(passthrough or [])

    if getattr(args, "list_actions", False):
        return run_cli(goal, ["console", "list"], ["list_console_actions"])

    console_command = getattr(args, "console_command", None)
    if console_command and goal == "call-action":
        return run_cli(
            goal, ["console", console_command] + passthrough, [console_command]
        )

    if console_command:
        return run_cli(
            goal, ["console", console_command] + passthrough, [console_command]
        )

    if goal == "create-agentic-search":
        return run_cli(
            goal,
            [
                "scene",
                "create",
                "--scene-type",
                "AGENTIC_SEARCH",
                "--project",
                args.project,
                "--name",
                args.name,
                "--description",
                args.description,
                "--max-attempts",
                str(args.max_attempts),
                "--poll-interval-ms",
                str(args.poll_interval_ms),
            ]
            + (["--resource-tags", args.resource_tags] if args.resource_tags else []),
            [
                "list_agentic_scene_template",
                "ensure_builtin_deployment",
                "create_agentic_scene",
            ],
        )

    if goal == "create-scene":
        return run_cli(
            goal,
            [
                "scene",
                "create",
                "--scene-type",
                args.scene_type,
                "--project",
                args.project,
                "--name",
                args.name,
                "--description",
                args.description,
                "--max-attempts",
                str(args.max_attempts),
                "--poll-interval-ms",
                str(args.poll_interval_ms),
            ]
            + (["--resource-tags", args.resource_tags] if args.resource_tags else []),
            ["create_scene"],
        )

    if goal == "list-scenes":
        return run_cli(
            goal,
            [
                "scene",
                "list",
                "--page-number",
                str(args.page_number),
                "--page-size",
                str(args.page_size),
            ],
            ["list_scene"],
        )

    if goal == "get-scene":
        cli_args = [
            "scene",
            "get",
            "--id",
            args.id,
            "--scene-type",
            args.scene_type,
            "--project",
            args.project,
        ]
        if args.is_demo:
            cli_args.append("--is-demo")
        return run_cli(goal, cli_args, ["get_scene"])

    if goal == "publish-scene":
        return run_cli(
            goal,
            [
                "scene",
                "publish",
                "--id",
                args.id,
                "--scene-type",
                args.scene_type,
                "--project",
                args.project,
                "--version",
                args.version,
                "--resource-spec",
                args.resource_spec,
                "--replicas",
                str(args.replicas),
            ],
            ["create_scene_version"],
        )

    if goal == "start-scene":
        return run_cli(
            goal,
            [
                "scene",
                "start",
                "--id",
                args.id,
                "--scene-type",
                args.scene_type,
                "--project",
                args.project,
            ],
            ["start_scene_instance"],
        )

    if goal == "stop-scene":
        return run_cli(
            goal,
            [
                "scene",
                "stop",
                "--id",
                args.id,
                "--scene-type",
                args.scene_type,
                "--project",
                args.project,
            ],
            ["stop_scene_instance"],
        )

    if goal == "delete-scene":
        if args.confirm != args.id:
            emit(
                {
                    "status": "error",
                    "goal": goal,
                    "error": "Confirmation mismatch",
                    "details": "--confirm must exactly match --id.",
                },
                1,
            )
        return run_cli(
            goal,
            [
                "scene",
                "delete",
                "--id",
                args.id,
                "--scene-type",
                args.scene_type,
                "--project",
                args.project,
                "--confirm",
            ],
            ["delete_scene"],
        )

    if goal == "specs":
        return run_cli(
            goal,
            ["scene", "specs"] + (["--show-all"] if args.show_all else []),
            ["get_ai_instance_spec"],
        )

    if goal == "list-models":
        command = "list_user" if args.user else "list"
        return run_cli(
            goal,
            [
                "model",
                command,
                "--project",
                args.project,
                "--name",
                args.name,
                "--page-number",
                str(args.page_number),
                "--page-size",
                str(args.page_size),
            ],
            ["list_ai_model"],
        )

    if goal == "get-model":
        return run_cli(
            goal,
            ["model", "get", "--id", args.id, "--project", args.project],
            ["get_ai_model"],
        )

    if goal == "list-deployments":
        command = "list_user" if args.user else "list_builtin"
        return run_cli(
            goal,
            [
                "deployment",
                command,
                "--project",
                args.project,
                "--name",
                args.name,
                "--page-number",
                str(args.page_number),
                "--page-size",
                str(args.page_size),
            ],
            ["list_ai_deployment"],
        )

    if goal == "get-deployment":
        return run_cli(
            goal,
            ["deployment", "get", "--id", args.id, "--project", args.project],
            ["get_ai_deployment"],
        )

    if goal == "deployment-usage":
        cli_args = [
            "deployment",
            "usage",
            "--id",
            args.id,
            "--interval",
            str(args.interval),
        ]
        if args.start_time is not None:
            cli_args.extend(["--start-time", args.start_time])
        if args.end_time is not None:
            cli_args.extend(["--end-time", args.end_time])
        return run_cli(goal, cli_args, ["get_ark_endpoint_usage"])

    if goal == "list-api-keys":
        apikey_namespace = "api" + "key"
        list_ml_api_keys_step = "list_ml_api_" + "keys"
        return run_cli(
            goal,
            [
                apikey_namespace,
                "list",
                "--project",
                args.project,
                "--name",
                args.name,
                "--page-number",
                str(args.page_number),
                "--page-size",
                str(args.page_size),
            ],
            [list_ml_api_keys_step],
        )

    if goal == "create-api-key":
        return run_cli(
            goal,
            ["api" + "key", "create", "--name", args.name, "--project", args.project],
            ["create_ml_api_" + "key"],
        )

    if goal == "delete-api-key":
        if args.confirm != args.id:
            emit(
                {
                    "status": "error",
                    "goal": goal,
                    "error": "Confirmation mismatch",
                    "details": "--confirm must exactly match --id.",
                },
                1,
            )
        return run_cli(
            goal,
            [
                "api" + "key",
                "delete",
                "--id",
                args.id,
                "--project",
                args.project,
                "--confirm",
            ],
            ["delete_ml_api_" + "key"],
        )

    emit({"status": "error", "goal": goal, "error": "Unsupported goal"}, 1)


def main():
    parser = build_parser()
    args, passthrough = parser.parse_known_args()
    if passthrough and not getattr(args, "console_command", None):
        parser.error("unrecognized arguments: %s" % " ".join(passthrough))
    dispatch(args, passthrough)


if __name__ == "__main__":
    main()
