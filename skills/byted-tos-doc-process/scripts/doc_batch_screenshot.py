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

"""Export multiple PDF pages as images through doc-preview batch mode.

The backend requires batch export to:
1. use a PDF source object;
2. save results back to TOS;
3. include the `{Page}` placeholder in the destination object key.
"""

import argparse
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from doc_preview_params import build_doc_preview_query_params
from doc_preview_process import create_client, get_env, pre_signed_request


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch export document pages as images"
    )
    parser.add_argument("--bucket", type=str, default=None, help="Override TOS_BUCKET")
    parser.add_argument("--key", type=str, default=None, help="Override TOS_OBJECT_KEY")
    parser.add_argument(
        "--format", choices=["png", "jpg"], default="png", help="Image format"
    )
    parser.add_argument(
        "--src-type", type=str, default=None, help="Optional source type override"
    )
    parser.add_argument("--start-page", type=int, default=1, help="Start page, 1-based")
    parser.add_argument(
        "--end-page", type=int, default=-1, help="End page, -1 means last page"
    )
    parser.add_argument("--dpi", type=int, default=200, help="DocImageDpi")
    parser.add_argument("--quality", type=int, default=90, help="DocImageQuality")
    parser.add_argument(
        "--img-mode",
        type=int,
        default=1,
        help="Batch image mode, defaults to 1 for multi-page export",
    )
    parser.add_argument(
        "--saveas-bucket", type=str, default=None, help="Save result to this bucket"
    )
    parser.add_argument(
        "--saveas-object",
        type=str,
        default=None,
        help="Save result object template, must contain {Page}, e.g. previews/test_{Page}.png",
    )
    args = parser.parse_args()

    if args.start_page <= 0:
        print("[ERROR] --start-page must be >= 1", file=sys.stderr)
        sys.exit(1)
    if args.end_page != -1 and args.end_page < args.start_page:
        print("[ERROR] --end-page must be >= --start-page or -1", file=sys.stderr)
        sys.exit(1)

    client = create_client()
    bucket = args.bucket or get_env("TOS_BUCKET")
    key = args.key or get_env("TOS_OBJECT_KEY")
    inferred_src_type = args.src_type or os.path.splitext(key)[1].lstrip(".").lower()
    if inferred_src_type != "pdf":
        print(
            "[ERROR] Batch screenshot currently requires a PDF source object.",
            file=sys.stderr,
        )
        sys.exit(1)

    save_bucket = args.saveas_bucket or bucket
    save_object = args.saveas_object
    if not save_object:
        base = os.path.splitext(os.path.basename(key) or "document")[0]
        save_object = f"doc-batch/{base}_{{Page}}.{args.format}"
    if "{Page}" not in save_object:
        print(
            "[ERROR] --saveas-object must contain the {Page} placeholder.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"[INFO] Running doc batch screenshot for {bucket}/{key} -> {save_bucket}/{save_object}"
    )

    params = build_doc_preview_query_params(
        dest_type=args.format,
        src_type=inferred_src_type,
        image_dpi=args.dpi,
        image_quality=args.quality,
        img_mode=args.img_mode,
        start_page=args.start_page,
        end_page=args.end_page,
        save_bucket=save_bucket,
        save_object=save_object,
    )
    req = pre_signed_request(client, bucket, key, params)
    try:
        with urlopen(req) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        print(
            f"[ERROR] HTTP error: status={exc.code}, reason={exc.reason}",
            file=sys.stderr,
        )
        sys.exit(1)
    except URLError as exc:
        print(f"[ERROR] Request failed: {exc.reason}", file=sys.stderr)
        sys.exit(1)

    print("[OK] Batch export result from TOS:")
    print(body)


if __name__ == "__main__":
    main()
