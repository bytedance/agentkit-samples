#!/usr/bin/env python3
"""Delete owned resource components, then optionally wait for the tombstone."""

from _common import mutation_resource, parser, positive_int, run, submit


def main() -> None:
    cli = parser(__doc__, resource=True, mutation=True)
    cli.add_argument(
        "--expected-revision",
        type=positive_int,
        help="Override the revision in the state JSON",
    )
    args = cli.parse_args()
    body = {
        **mutation_resource(args),
        "client_token": args.client_token,
    }
    submit("DeleteEnvironmentResource", body, args, wanted="deleted")


if __name__ == "__main__":
    run(main)
