#!/usr/bin/env python3
"""Create an EnvironmentResource group; optionally wait for its components."""

import os

from _common import (
    add_target_argument,
    json_object,
    parser,
    required_env,
    run,
    submit,
    validate_env_vars,
)


DEFAULT_ARK_SANDBOX_IMAGE = (
    "enterprise-public-cn-beijing.cr.volces.com/vefaas-public/"
    "agentkit-selfhostsandbox:tool-ark-skills-0.0.2"
)
DEFAULT_ARK_RUNTIME_IMAGE = (
    "enterprise-public-cn-beijing.cr.volces.com/vefaas-public/"
    "agentkit-selfhostsandbox:runtime-ark-skills-0.0.2"
)


def main() -> None:
    cli = parser(__doc__, mutation=True)
    add_target_argument(cli)
    cli.add_argument("--name")
    cli.add_argument("--description")
    cli.add_argument(
        "--region", help="Optional; must match the server's configured region"
    )
    cli.add_argument(
        "--sandbox-image",
        help=f"Optional; ark default: {DEFAULT_ARK_SANDBOX_IMAGE}; agentkit uses the server default",
    )
    cli.add_argument(
        "--runtime-image",
        help=f"Optional; ark default: {DEFAULT_ARK_RUNTIME_IMAGE}",
    )
    cli.add_argument(
        "--sandbox-env-vars", type=json_object, help="JSON object or @file.json"
    )
    cli.add_argument(
        "--skill-space-id", default=os.getenv("AGENTKIT_SKILL_SPACE_ID", "")
    )
    args = cli.parse_args()
    if args.target_type not in {"ark", "agentkit"}:
        cli.error("AGENTKIT_RESOURCE_TARGET must be ark or agentkit")
    if args.target_type == "agentkit" and args.runtime_image:
        cli.error("--runtime-image is only supported for ark")

    body = {
        "client_token": args.client_token,
        "resource_mode": "runtime_and_sandbox"
        if args.target_type == "ark"
        else "sandbox_only",
        "target": {
            "type": args.target_type,
            "environment_id": required_env(
                "AGENTKIT_ENVIRONMENT_ID", dry_run=args.dry_run
            ),
        },
        "sandbox": {
            "profile": "ark_skills" if args.target_type == "ark" else "ma_infra"
        },
    }
    if args.name is not None:
        body["name"] = args.name
    if args.description is not None:
        body["description"] = args.description
    if args.region:
        body["region"] = args.region
    sandbox_image = args.sandbox_image
    if sandbox_image is None and args.target_type == "ark":
        sandbox_image = DEFAULT_ARK_SANDBOX_IMAGE
    if sandbox_image:
        body["sandbox"]["image_url"] = sandbox_image
    if args.sandbox_env_vars is not None or args.skill_space_id:
        env_vars = validate_env_vars(args.sandbox_env_vars or {})
        if args.skill_space_id:
            if (
                "SKILL_SPACE_ID" in env_vars
                and env_vars["SKILL_SPACE_ID"] != args.skill_space_id
            ):
                cli.error(
                    "--skill-space-id conflicts with sandbox.env_vars.SKILL_SPACE_ID"
                )
            env_vars["SKILL_SPACE_ID"] = args.skill_space_id
        body["sandbox"]["env_vars"] = env_vars
    if args.target_type == "ark":
        body["target"].update(
            {
                "base_url": required_env(
                    "AGENTKIT_ENVIRONMENT_BASE_URL", dry_run=args.dry_run
                ),
                "environment_key": required_env(
                    "AGENTKIT_ENVIRONMENT_KEY", dry_run=args.dry_run
                ),
            }
        )
        runtime_image = (
            DEFAULT_ARK_RUNTIME_IMAGE
            if args.runtime_image is None
            else args.runtime_image
        )
        body["runtime"] = {"image_url": runtime_image} if runtime_image else {}
    submit("CreateEnvironmentResource", body, args)


if __name__ == "__main__":
    run(main)
