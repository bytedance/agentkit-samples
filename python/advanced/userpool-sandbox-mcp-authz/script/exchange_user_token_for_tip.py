#!/usr/bin/env python3
"""Exchange a User Pool access token for an X-Ve-TIP-Token value."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv(Path(__file__).resolve().with_name(".env"))

from veadk.integrations.ve_identity.auth_config import get_default_identity_client


DEFAULT_WORKLOAD_NAME = "userpool_sandbox_mcp_authz"
TIP_HEADER = "X-Ve-TIP-Token"


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _strip_bearer(token: str) -> str:
    token = token.strip()
    if token.lower().startswith("bearer "):
        return token[7:].strip()
    return token


def _stdin_token() -> str:
    if sys.stdin.isatty():
        return ""
    return sys.stdin.read().strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exchange a User Pool access token for a workload/TIP token."
    )
    parser.add_argument(
        "--user-token",
        default=_env("USER_TOKEN") or _env("ACCESS_TOKEN") or _stdin_token(),
        help="User Pool access token. Also supports USER_TOKEN, ACCESS_TOKEN, or stdin.",
    )
    parser.add_argument(
        "--workload-name",
        default=_env("VE_IDENTITY_WORKLOAD_NAME") or DEFAULT_WORKLOAD_NAME,
        help="Workload identity name. Default: VE_IDENTITY_WORKLOAD_NAME or sample agent name.",
    )
    parser.add_argument(
        "--region",
        default=_env("VE_IDENTITY_REGION")
        or _env("VOLCENGINE_REGION")
        or _env("REGION"),
        help="VeIdentity region, for example cn-beijing.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON with header name, token, and expires_at instead of raw token.",
    )
    args = parser.parse_args()

    user_token = _strip_bearer(args.user_token or "")
    if not user_token:
        parser.error(
            "missing user token; pass --user-token, USER_TOKEN, ACCESS_TOKEN, or stdin"
        )

    identity_client = get_default_identity_client(region=args.region)
    workload_token = identity_client.get_workload_access_token(
        workload_name=args.workload_name,
        user_token=user_token,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "header": TIP_HEADER,
                    "workload_name": args.workload_name,
                    "tip_token": workload_token.workload_access_token,
                    "expires_at": workload_token.expires_at,
                },
                ensure_ascii=False,
            )
        )
    else:
        print(workload_token.workload_access_token)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
