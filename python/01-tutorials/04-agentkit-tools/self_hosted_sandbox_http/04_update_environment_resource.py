#!/usr/bin/env python3
"""Update selected fields using the cached resource ID and revision by default."""

from _common import (
    add_target_argument,
    json_object,
    mutation_resource,
    parser,
    positive_int,
    required_env,
    run,
    submit,
    validate_env_vars,
)


def main() -> None:
    cli = parser(__doc__, resource=True, mutation=True)
    add_target_argument(cli)
    cli.add_argument(
        "--expected-revision",
        type=positive_int,
        help="Override the revision in the state JSON; keep unchanged on an identical retry",
    )
    cli.add_argument("--name")
    description = cli.add_mutually_exclusive_group()
    description.add_argument("--description")
    description.add_argument("--clear-description", action="store_true")
    cli.add_argument("--sandbox-image")
    cli.add_argument(
        "--sandbox-env-vars",
        type=json_object,
        help="Replace custom env vars (JSON or @file); {} clears them",
    )
    cli.add_argument(
        "--sandbox-resources", type=json_object, help="JSON object or @file.json"
    )
    cli.add_argument(
        "--sandbox-networking",
        type=json_object,
        help="JSON object or @file.json; existing environment policies still apply",
    )
    args = cli.parse_args()
    if args.target_type not in {"ark", "agentkit"}:
        cli.error("AGENTKIT_RESOURCE_TARGET must be ark or agentkit")
    body = {
        **mutation_resource(args),
        "client_token": args.client_token,
        "update_mask": [],
    }
    for key in ("name", "description"):
        if getattr(args, key) is not None or (
            key == "description" and args.clear_description
        ):
            body[key] = getattr(args, key)
            body["update_mask"].append(key)
    sandbox = {}
    for argument, field in (
        ("sandbox_image", "image_url"),
        ("sandbox_env_vars", "env_vars"),
        ("sandbox_resources", "resources"),
        ("sandbox_networking", "networking"),
    ):
        value = getattr(args, argument)
        if value is not None:
            sandbox[field] = validate_env_vars(value) if field == "env_vars" else value
            body["update_mask"].append(f"sandbox.{field}")
    if sandbox:
        body["sandbox"] = sandbox
        if args.target_type == "ark":
            body["target"] = {
                "environment_key": required_env(
                    "AGENTKIT_ENVIRONMENT_KEY", dry_run=args.dry_run
                )
            }
    if not body["update_mask"]:
        cli.error("provide at least one field to update")
    submit("UpdateEnvironmentResource", body, args)


if __name__ == "__main__":
    run(main)
