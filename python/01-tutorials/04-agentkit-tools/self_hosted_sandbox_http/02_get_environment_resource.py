#!/usr/bin/env python3
"""Get one resource, or resume polling without resubmitting a mutation."""

from _common import (
    EnvironmentResourceHttpClient,
    emit,
    parser,
    preview,
    resource_id,
    run,
    save_resource,
    state_path,
    wait_for_resource,
)


def main() -> None:
    cli = parser(__doc__, resource=True)
    cli.add_argument(
        "--wait",
        choices=("ready", "deleted"),
        help="Poll until this state and a successful operation",
    )
    args = cli.parse_args()
    body = {"resource_id": resource_id(args)}
    preview("GetEnvironmentResource", body, args.dry_run, json_output=args.json_output)
    if args.dry_run:
        return
    client = EnvironmentResourceHttpClient()
    response = client.get_environment_resource(body)
    save_resource(response)
    emit(
        {
            "phase": "response",
            "response": response,
            "waiting": bool(args.wait),
            "state_file": str(state_path()),
        },
        json_output=args.json_output,
    )
    if args.wait:
        response = wait_for_resource(
            client,
            body["resource_id"],
            args.wait,
            response,
            json_output=args.json_output,
        )
        emit({"phase": "completed", "response": response}, json_output=args.json_output)


if __name__ == "__main__":
    run(main)
