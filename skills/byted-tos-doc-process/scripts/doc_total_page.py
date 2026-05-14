# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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

#!/usr/bin/env python3
"""Example script: query x-tos-total-page from TOS doc-preview response headers.

This script now uses a **pre-signed URL** to call `doc-preview` and prints
the `x-tos-total-page` header, which indicates the total page count of the
source document for the given preview configuration (DocDestType/DocPage,
etc.).

Instead of passing doc-specific parameters directly to `get_object`, we
build the corresponding `x-tos-*` query parameters and generate a
pre-signed URL via `TosClientV2.pre_signed_url`, then perform the HTTP
request with the standard library.

Environment variables:
  - TOS_ACCESS_KEY, TOS_SECRET_KEY, TOS_SECURITY_TOKEN(optional)
  - TOS_ENDPOINT, TOS_REGION
  - TOS_BUCKET, TOS_OBJECT_KEY

CLI parameters:
  --bucket        Override TOS_BUCKET
  --key           Override TOS_OBJECT_KEY
  --dest-type     DocDestType: pdf/png/jpg (required)
  --src-type      Optional DocSrcType, e.g. docx/pptx/xlsx
  --page          Optional DocPage for single-page preview

The script is intentionally lightweight: it focuses on header inspection
rather than saving the preview body. See WORKFLOWS.md for how caching
affects `x-tos-total-page` when calling doc-preview multiple times.
"""

import argparse
import json
import os
import sys
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import tos
from tos.enum import HttpMethodType
from tos.exceptions import TosClientError, TosServerError

from doc_preview_params import build_doc_preview_query_params


def get_env(name: str, required: bool = True, default: Optional[str] = None) -> str:
    value = os.getenv(name, default)
    if required and not value:
        print(f"[ERROR] Environment variable {name} is required.", file=sys.stderr)
        sys.exit(1)
    return value  # type: ignore[return-value]


def create_client() -> tos.TosClientV2:
    ak = get_env("TOS_ACCESS_KEY")
    sk = get_env("TOS_SECRET_KEY")
    endpoint = get_env("TOS_ENDPOINT")
    region = get_env("TOS_REGION")
    security_token = os.getenv("TOS_SECURITY_TOKEN")

    print(
        f"[INFO] Initializing TOS client for endpoint={endpoint}, region={region} ..."
    )
    return tos.TosClientV2(
        ak=ak,
        sk=sk,
        endpoint=endpoint,
        region=region,
        security_token=security_token,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read x-tos-total-page from doc-preview response headers",
    )
    parser.add_argument("--bucket", type=str, default=None, help="Override TOS_BUCKET")
    parser.add_argument("--key", type=str, default=None, help="Override TOS_OBJECT_KEY")
    parser.add_argument(
        "--dest-type",
        dest="dest_type",
        type=str,
        choices=["pdf", "png", "jpg"],
        required=True,
        help="DocDestType used for preview (pdf/png/jpg)",
    )
    parser.add_argument(
        "--src-type",
        dest="src_type",
        type=str,
        default=None,
        help="Optional DocSrcType, e.g. docx/pptx/xlsx",
    )
    parser.add_argument(
        "--page",
        type=int,
        default=None,
        help="Optional DocPage (1-based) for page-specific preview",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved request and exit")
    args = parser.parse_args()

    if args.page is not None and args.page <= 0:
        print("[ERROR] --page must be >= 1 when specified", file=sys.stderr)
        sys.exit(1)

    client = create_client()
    bucket = args.bucket or get_env("TOS_BUCKET")
    key = args.key or get_env("TOS_OBJECT_KEY")

    params = build_doc_preview_query_params(
        dest_type=args.dest_type,
        src_type=args.src_type,
        page=args.page,
    )
    plan = {
        "ok": True,
        "operation": "doc_total_page",
        "bucket": bucket,
        "key": key,
        "dest_type": args.dest_type,
        "src_type": args.src_type,
        "page": args.page,
        "params": params,
    }

    if args.dry_run:
        if args.json:
            print(json.dumps(plan, ensure_ascii=False))
        else:
            print(json.dumps(plan, indent=2, ensure_ascii=False))
        return

    if not args.json:
        print(
            f"[INFO] Requesting doc-preview headers for {bucket}/{key}, "
            f"DocDestType={args.dest_type}, DocPage={args.page}",
        )

    # Generate pre-signed URL and perform a HEAD-equivalent GET (we only care about headers).
    try:
        presigned = client.pre_signed_url(
            HttpMethodType.Http_Method_Get,
            bucket=bucket,
            key=key,
            query=params,
        )
    except TosServerError as e:
        print(
            f"[ERROR] Failed to generate pre-signed URL: "
            f"code={e.code}, status={e.status_code}, request_id={e.request_id}, message={e.message}",
            file=sys.stderr,
        )
        sys.exit(1)
    except TosClientError as e:
        print(
            f"[ERROR] TOS client error when generating pre-signed URL: {e}",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(
            f"[ERROR] Unexpected error when generating pre-signed URL: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    req = Request(presigned.signed_url, headers=presigned.signed_header)
    try:
        # We are interested in headers. Reading zero bytes is enough to ensure the request is issued.
        with urlopen(req) as resp:
            # Simply capture headers; body is ignored.
            headers = resp.headers
    except HTTPError as e:
        print(
            f"[ERROR] HTTP error when calling doc-preview for headers: "
            f"status={e.code}, reason={e.reason}",
            file=sys.stderr,
        )
        sys.exit(1)
    except URLError as e:
        print(
            f"[ERROR] Failed to call doc-preview for headers: {e.reason}",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(
            f"[ERROR] Unexpected error when calling doc-preview for headers: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    total_page = None
    try:
        if headers is not None:
            total_page = headers.get("x-tos-total-page")
    except Exception:
        total_page = None

    if total_page is None:
        payload = {
            **plan,
            "ok": False,
            "warning": "x-tos-total-page header not found on response.",
            "total_page": None,
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print("[WARN] x-tos-total-page header not found on response.")
        return

    payload = {
        **plan,
        "total_page": total_page,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"[OK] x-tos-total-page = {total_page}")


if __name__ == "__main__":
    main()
