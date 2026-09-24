#!/usr/bin/env python3
"""List resources with filters and optional traversal of next_page cursors."""

from _common import (
    EnvironmentResourceHttpClient,
    emit,
    parser,
    positive_int,
    preview,
    run,
)


def main() -> None:
    cli = parser(__doc__)
    cli.add_argument("--target-type", choices=("ark", "agentkit"))
    cli.add_argument("--environment-id")
    cli.add_argument("--resource-mode", choices=("sandbox_only", "runtime_and_sandbox"))
    cli.add_argument(
        "--status",
        choices=(
            "creating",
            "ready",
            "updating",
            "deleting",
            "failed",
            "delete_failed",
            "deleted",
        ),
    )
    cli.add_argument("--include-deleted", action="store_true")
    cli.add_argument(
        "--limit", type=positive_int, help="Page size, 1-100 (server default: 20)"
    )
    cli.add_argument("--page", help="Opaque next_page value from the previous response")
    cli.add_argument(
        "--all", action="store_true", help="Follow next_page until exhausted"
    )
    args = cli.parse_args()
    if args.limit is not None and args.limit > 100:
        cli.error("--limit must be between 1 and 100")
    body = {
        key: getattr(args, key)
        for key in (
            "target_type",
            "environment_id",
            "resource_mode",
            "status",
            "limit",
            "page",
        )
        if getattr(args, key) is not None
    }
    if args.include_deleted:
        body["include_deleted"] = True
    preview(
        "ListEnvironmentResources", body, args.dry_run, json_output=args.json_output
    )
    if args.dry_run:
        return
    client = EnvironmentResourceHttpClient()
    seen = {args.page} if args.page else set()
    page_number = 0
    total = 0
    while True:
        response = client.list_environment_resources(body)
        if not isinstance(response.get("data"), list):
            raise RuntimeError("ListEnvironmentResources response is missing data[]")
        page_number += 1
        total += len(response["data"])
        emit(
            {
                "phase": "page",
                "response": response,
                "page_number": page_number,
                "total": total,
                "all_pages": args.all,
            },
            json_output=args.json_output,
        )
        page = response.get("next_page")
        if not args.all or not page:
            return
        if not isinstance(page, str) or page in seen:
            raise RuntimeError(
                "ListEnvironmentResources returned an invalid or repeated next_page"
            )
        seen.add(page)
        body["page"] = page


if __name__ == "__main__":
    run(main)
