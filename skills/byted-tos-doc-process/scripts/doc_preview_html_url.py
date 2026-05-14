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
"""Example script: fetch HTML doc-preview and extract the real preview URL.

This script uses the TOS Python SDK's **pre-signed URL** capability to call
`doc-preview` with `DocDestType=html`. It then:

1. Generates a signed URL with all doc-preview parameters encoded as
   `x-tos-*` query parameters (including `x-tos-doc-dst-type=html`, optional
   `x-tos-doc-src-type`, `x-tos-doc-page`, etc.).
2. Performs an HTTP GET against that URL to retrieve the temporary HTML
   page.
3. Uses a regular expression to extract the embedded
   `window.open("<LINK>","_self")` HTML preview link.
4. Parses the `token` query parameter from that link and decodes it
   (Base64 URL-safe) to obtain the actual preview URL.

It also supports a **direct URL** mode where you can pass the HTML URL
(e.g. an example link provided by TOS) and skip the pre-signed step.

Environment variables:
  - TOS_ACCESS_KEY        Access key ID (AK) or STS AccessKeyId
  - TOS_SECRET_KEY        Secret access key (SK) or STS SecretAccessKey
  - TOS_SECURITY_TOKEN    (optional) STS session token
  - TOS_ENDPOINT          TOS endpoint, e.g. https://tos-cn-beijing.volces.com
  - TOS_REGION            TOS region, e.g. cn-beijing
  - TOS_BUCKET            Bucket name that stores the source document
  - TOS_OBJECT_KEY        Object key of the document in the bucket

CLI parameters:
  --bucket        Override TOS_BUCKET
  --key           Override TOS_OBJECT_KEY
  --src-type      Optional DocSrcType, e.g. docx/pptx/xlsx (see official docs)
  --page          Optional DocPage (1-based) for HTML preview
  --direct-url    If provided, skip SDK and fetch this HTML URL directly

The script prints:
  - The HTML preview link extracted from the HTML page
  - The raw token found in the link
  - The decoded preview URL (which can be accessed directly by browser/HTTP).

Notes:
  - This implementation is compatible with the internal
    test case `tc_func_doc_html_url.py`, but it now uses a more robust
    regex-based extraction of the preview link and parses the `token`
    from the link's query string.
  - For buckets created after the domain restriction change (2024-01-03),
    you must use a custom domain for the preview URL; otherwise the preview
    might fall back to downloading the original file. See README/REFERENCE
    for details.
  - We do **not** pass doc-related parameters as explicit `get_object`
    keyword arguments. Instead, we always encode them into the query string
    of a pre-signed URL via `TosClientV2.pre_signed_url`.
"""

import argparse
import base64
import os
import re
import sys
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
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


def extract_preview_link(html: str) -> str:
    """Extract the full HTML preview link from a window.open call.

    Expected pattern (whitespace around comma is allowed):

        window.open("<LINK>","_self");

    or

        window.open("<LINK>",  "_self");

    The regex is DOTALL-enabled so that the call can safely span multiple lines.
    """

    pattern = r'window\.open\("([^\"]+)",\s*"_self"\)'
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        raise ValueError(
            'Could not find preview link via window.open("...","_self") in HTML content',
        )
    return match.group(1)


def extract_token_from_html(html: str) -> str:
    """Extract the Base64 URL-safe token from the HTML doc-preview page.

    For backward compatibility, this helper remains available, but it now
    works by:

    1. Extracting the preview link via :func:`extract_preview_link`.
    2. Parsing the `token` query parameter from that link using
       ``urllib.parse.urlparse`` / ``parse_qs``.

    This is more robust than directly slicing the raw HTML and avoids
    accidentally including trailing characters such as `","_self")` in
    the token.
    """

    preview_link = extract_preview_link(html)

    parsed = urlparse(preview_link)
    if not parsed.query:
        raise ValueError(f"No query string found in preview link: {preview_link!r}")

    qs = parse_qs(parsed.query)
    token_list = qs.get("token")
    if not token_list:
        raise ValueError(
            f"No 'token' parameter found in preview link: {preview_link!r}"
        )

    token = token_list[0]
    if not token:
        raise ValueError("Token parameter in preview link is empty")
    return token


def decode_preview_url(token: str) -> str:
    """Decode Base64 URL-safe token to get the real preview URL.

    The token is encoded using URL-safe Base64 without padding. We restore
    padding and decode it with ``base64.urlsafe_b64decode``.
    """

    # Restore padding to multiple of 4
    padding = "=" * ((4 - len(token) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(token + padding)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Failed to decode token as URL-safe Base64: {exc}") from exc

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:  # noqa: BLE001
        raise ValueError("Decoded token is not valid UTF-8") from exc


def fetch_html_via_presigned(
    client: tos.TosClientV2,
    bucket: str,
    key: str,
    src_type: Optional[str],
    page: Optional[int],
) -> str:
    """Generate a pre-signed URL for HTML doc-preview and fetch the HTML body."""

    params = build_doc_preview_query_params(
        dest_type="html",
        src_type=src_type,
        page=page,
    )

    print("[INFO] Generating pre-signed URL for doc-preview (html)...")
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
        with urlopen(req) as resp:
            html_bytes = resp.read()
    except HTTPError as e:
        print(
            f"[ERROR] HTTP error when fetching HTML via pre-signed URL: "
            f"status={e.code}, reason={e.reason}",
            file=sys.stderr,
        )
        sys.exit(1)
    except URLError as e:
        print(
            f"[ERROR] Failed to fetch HTML via pre-signed URL: {e.reason}",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Unexpected error when fetching HTML: {exc}", file=sys.stderr)
        sys.exit(1)

    return html_bytes.decode("utf-8", errors="replace")


def fetch_html_from_direct_url(url: str) -> str:
    """Fetch HTML directly from a user-provided URL (no SDK involved)."""

    print(f"[INFO] Fetching HTML from direct URL: {url}")
    req = Request(url)
    try:
        with urlopen(req) as resp:
            html_bytes = resp.read()
    except HTTPError as e:
        print(
            f"[ERROR] HTTP error when fetching direct HTML URL: "
            f"status={e.code}, reason={e.reason}",
            file=sys.stderr,
        )
        sys.exit(1)
    except URLError as e:
        print(f"[ERROR] Failed to fetch direct HTML URL: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(
            f"[ERROR] Unexpected error when fetching direct HTML URL: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    return html_bytes.decode("utf-8", errors="replace")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch HTML doc-preview and extract the real preview URL",
    )
    parser.add_argument("--bucket", type=str, default=None, help="Override TOS_BUCKET")
    parser.add_argument("--key", type=str, default=None, help="Override TOS_OBJECT_KEY")
    parser.add_argument(
        "--src-type",
        dest="src_type",
        type=str,
        default=None,
        help="Optional DocSrcType, e.g. docx/pptx/xlsx; see official docs",
    )
    parser.add_argument(
        "--page",
        type=int,
        default=None,
        help="Optional DocPage (1-based) for HTML preview",
    )
    parser.add_argument(
        "--direct-url",
        dest="direct_url",
        type=str,
        default=None,
        help=(
            "If provided, skip SDK and use this HTML URL directly. "
            "Useful for debugging sample links such as the ones in official docs."
        ),
    )
    args = parser.parse_args()

    if args.page is not None and args.page <= 0:
        print("[ERROR] --page must be >= 1 when specified", file=sys.stderr)
        sys.exit(1)

    if args.direct_url:
        # Direct URL mode: no SDK required.
        html = fetch_html_from_direct_url(args.direct_url)
    else:
        client = create_client()
        bucket = args.bucket or get_env("TOS_BUCKET")
        key = args.key or get_env("TOS_OBJECT_KEY")

        print(f"[INFO] Requesting HTML doc-preview for {bucket}/{key} ...")
        print("[INFO] Using pre-signed URL with doc_dest_type=html")
        html = fetch_html_via_presigned(client, bucket, key, args.src_type, args.page)

    try:
        preview_link = extract_preview_link(html)
    except ValueError as exc:
        print(
            f"[ERROR] Failed to extract preview link from HTML: {exc}", file=sys.stderr
        )
        # Optionally dump a small prefix of HTML to help debugging
        print(html[:400], file=sys.stderr)
        sys.exit(1)

    try:
        token = extract_token_from_html(html)
    except ValueError as exc:
        print(f"[ERROR] Failed to extract token from HTML: {exc}", file=sys.stderr)
        # Optionally dump a small prefix of HTML to help debugging
        print(html[:400], file=sys.stderr)
        sys.exit(1)

    try:
        preview_url = decode_preview_url(token)
    except ValueError as exc:
        print(
            f"[ERROR] Failed to decode preview URL from token: {exc}", file=sys.stderr
        )
        sys.exit(1)

    print("[OK] Extracted preview information:")
    print(f"  HTML Link   : {preview_link}")
    print(f"  Token       : {token}")
    print(f"  Preview URL : {preview_url}")


if __name__ == "__main__":
    main()
