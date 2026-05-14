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
"""Example script: preview a document page as JPG using TOS doc-preview.

This script calls the TOS `doc-preview` feature via a **pre-signed URL**
with `x-tos-doc-dst-type=jpg` and related parameters, then saves the
converted page image locally.

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
  --page          DocPage (1-based page index), default: 1
  --dpi           DocImageDpi (96-600 recommended; see official docs)
  --quality       DocImageQuality (0-100; see official docs)
  --image-params  DocImageParams raw string, forwarded as-is
  --output        Local output JPG path (default: <basename>_p<page>.jpg)

For batch export of page ranges (DocImgMode + DocStartPage/DocEndPage),
prefer using `doc_preview_process.py`, which exposes the full parameter set.
"""

import argparse
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


def default_output_path(key: str, page: int) -> str:
    base = os.path.basename(key)
    if not base:
        return f"preview_p{page}.jpg"
    root, _ = os.path.splitext(base)
    return f"{root}_p{page}.jpg"


def download_via_presigned_to_file(
    client: tos.TosClientV2,
    bucket: str,
    key: str,
    params: dict[str, str],
    output_path: str,
) -> None:
    """Generate a pre-signed URL for doc-preview and download to a local file."""

    print("[INFO] Generating pre-signed URL for doc-preview (jpg)...")
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
        with urlopen(req) as resp, open(output_path, "wb") as out_f:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                out_f.write(chunk)
    except HTTPError as e:
        print(
            f"[ERROR] HTTP error when downloading JPG via pre-signed URL: "
            f"status={e.code}, reason={e.reason}",
            file=sys.stderr,
        )
        try:
            os.remove(output_path)
        except OSError:
            pass
        sys.exit(1)
    except URLError as e:
        print(
            f"[ERROR] Failed to download JPG via pre-signed URL: {e.reason}",
            file=sys.stderr,
        )
        try:
            os.remove(output_path)
        except OSError:
            pass
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Unexpected error when downloading JPG: {exc}", file=sys.stderr)
        try:
            os.remove(output_path)
        except OSError:
            pass
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preview a single document page as JPG via TOS doc-preview",
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
        default=1,
        help="DocPage (1-based), default 1",
    )
    parser.add_argument(
        "--dpi",
        dest="dpi",
        type=int,
        default=None,
        help="DocImageDpi, recommended range [96, 600]",
    )
    parser.add_argument(
        "--quality",
        dest="quality",
        type=int,
        default=None,
        help="DocImageQuality, recommended range [0, 100]",
    )
    parser.add_argument(
        "--image-params",
        dest="image_params",
        type=str,
        default=None,
        help="DocImageParams raw string, forwarded to TOS (see official docs)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Local output JPG path (default: <basename>_p<page>.jpg)",
    )
    args = parser.parse_args()

    if args.page <= 0:
        print("[ERROR] --page must be >= 1", file=sys.stderr)
        sys.exit(1)

    client = create_client()
    bucket = args.bucket or get_env("TOS_BUCKET")
    key = args.key or get_env("TOS_OBJECT_KEY")
    output_path = args.output or default_output_path(key, args.page)

    print(
        f"[INFO] Requesting doc-preview JPG for {bucket}/{key}, page={args.page} -> {output_path}",
    )

    params = build_doc_preview_query_params(
        dest_type="jpg",
        src_type=args.src_type,
        page=args.page,
        image_dpi=args.dpi,
        image_quality=args.quality,
        image_params=args.image_params,
    )

    download_via_presigned_to_file(client, bucket, key, params, output_path)

    try:
        size = os.path.getsize(output_path)
    except OSError:
        size = -1

    print(f"[OK] JPG saved to {output_path} ({size} bytes)")


if __name__ == "__main__":
    main()
