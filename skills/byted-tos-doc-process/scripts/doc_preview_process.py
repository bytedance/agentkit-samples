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
"""Generic entrypoint for TOS document preview (doc-preview).

This script exposes the full set of commonly used doc-preview parameters and
implements them using the TOS SDK's **pre-signed URL** capability. It allows
you to:

  - Preview a document as PDF/PNG/JPG/HTML and save the result locally.
  - Or, ask TOS to save the converted result back into TOS (via
    `x-tos-save-bucket` / `x-tos-save-object`).

Instead of passing doc-specific parameters (DocDestType/DocPage/DocImgMode,
...) as keyword arguments to `get_object` / `get_object_to_file`, this script
builds the corresponding `x-tos-*` query parameters and calls
`TosClientV2.pre_signed_url`, then performs the HTTP request via stdlib.

Supported doc-preview parameters (CLI → doc-preview):
  - DocDestType       -> --dest-type (pdf/png/jpg/html)
  - DocSrcType        -> --src-type
  - DocPage           -> --page
  - DocImgMode        -> --img-mode
  - DocStartPage      -> --start-page
  - DocEndPage        -> --end-page
  - DocImageDpi       -> --dpi
  - DocImageQuality   -> --quality
  - DocImageParams    -> --image-params

Environment variables:
  - TOS_ACCESS_KEY, TOS_SECRET_KEY, TOS_SECURITY_TOKEN(optional)
  - TOS_ENDPOINT, TOS_REGION
  - TOS_BUCKET, TOS_OBJECT_KEY

See REFERENCE.md and WORKFLOWS.md for detailed parameter mapping and examples.
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


def default_output_path(key: str, dest_type: str) -> str:
    base = os.path.basename(key)
    if not base:
        return f"preview.{dest_type}"
    root, _ = os.path.splitext(base)
    return f"{root}.{dest_type}"


def maybe_print_json(raw: bytes) -> bool:
    try:
        text = raw.decode("utf-8")
        data = json.loads(text)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return True
    except Exception:
        return False


def pre_signed_request(
    client: tos.TosClientV2,
    bucket: str,
    key: str,
    params: dict[str, str],
) -> Request:
    """Helper: generate a pre-signed GET request for doc-preview."""

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

    return Request(presigned.signed_url, headers=presigned.signed_header)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generic TOS doc-preview (doc-preview) entrypoint",
    )
    parser.add_argument("--bucket", type=str, default=None, help="Override TOS_BUCKET")
    parser.add_argument("--key", type=str, default=None, help="Override TOS_OBJECT_KEY")
    parser.add_argument(
        "--dest-type",
        dest="dest_type",
        type=str,
        choices=["pdf", "png", "jpg", "html"],
        required=True,
        help="DocDestType: target format (pdf/png/jpg/html)",
    )
    parser.add_argument(
        "--src-type",
        dest="src_type",
        type=str,
        default=None,
        help="DocSrcType, e.g. docx/pptx/xlsx; maps to x-tos-doc-src-type",
    )
    parser.add_argument(
        "--page",
        type=int,
        default=None,
        help="DocPage (1-based). If set, preview a single page.",
    )
    parser.add_argument(
        "--img-mode",
        dest="img_mode",
        type=int,
        default=None,
        help="DocImgMode for batch export (see official docs, e.g. 1 for all pages)",
    )
    parser.add_argument(
        "--start-page",
        dest="start_page",
        type=int,
        default=None,
        help="DocStartPage (1-based). Use together with --img-mode.",
    )
    parser.add_argument(
        "--end-page",
        dest="end_page",
        type=int,
        default=None,
        help="DocEndPage. Use -1 to denote 'last page' where supported.",
    )
    parser.add_argument(
        "--dpi",
        dest="dpi",
        type=int,
        default=None,
        help="DocImageDpi, recommended range [96, 600] for image outputs.",
    )
    parser.add_argument(
        "--quality",
        dest="quality",
        type=int,
        default=None,
        help="DocImageQuality, recommended range [0, 100] for image outputs.",
    )
    parser.add_argument(
        "--image-params",
        dest="image_params",
        type=str,
        default=None,
        help="DocImageParams raw string, forwarded as-is.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help=(
            "Local output file path. For png/jpg/pdf/html this defaults to "
            "<basename>.<dest-type> if not provided. Required when not saving back to TOS."
        ),
    )
    parser.add_argument(
        "--saveas-bucket", type=str, default=None, help="Save result to this bucket"
    )
    parser.add_argument(
        "--saveas-object", type=str, default=None, help="Save result as this object key"
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

    save_bucket = args.saveas_bucket
    save_object = args.saveas_object
    persist_to_tos = bool(save_bucket or save_object)
    output_path = None if persist_to_tos else args.output or default_output_path(key, args.dest_type)
    resolved_save_bucket = save_bucket or bucket if persist_to_tos else None
    resolved_save_object = None
    if persist_to_tos:
        resolved_save_object = save_object or f"doc-preview-{os.path.basename(key) or 'document'}.{args.dest_type}"

    params = build_doc_preview_query_params(
        dest_type=args.dest_type,
        src_type=args.src_type,
        page=args.page,
        image_dpi=args.dpi,
        image_quality=args.quality,
        img_mode=args.img_mode,
        start_page=args.start_page,
        end_page=args.end_page,
        image_params=args.image_params,
        save_bucket=resolved_save_bucket,
        save_object=resolved_save_object,
    )

    if args.dry_run:
        payload = {
            "ok": True,
            "operation": "doc_preview",
            "bucket": bucket,
            "key": key,
            "dest_type": args.dest_type,
            "mode": "save_to_tos" if persist_to_tos else "save_local",
            "output_path": output_path,
            "saveas_bucket": resolved_save_bucket,
            "saveas_object": resolved_save_object,
            "params": params,
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    client = create_client()

    if persist_to_tos:
        if not args.json:
            print(
                f"[INFO] Running doc-preview for {bucket}/{key} -> {resolved_save_bucket}/{resolved_save_object}",
            )
    else:
        if not args.json:
            print(
                f"[INFO] Running doc-preview for {bucket}/{key} -> {output_path}",
            )

    if not args.json:
        print("[INFO] process = doc-preview")
        print(
            f"[INFO] DocDestType={args.dest_type}, DocPage={args.page}, "
            f"DocImgMode={args.img_mode}, DocStartPage={args.start_page}, DocEndPage={args.end_page}",
        )

    req = pre_signed_request(client, bucket, key, params)

    if persist_to_tos:
        # We expect a JSON body describing the save result
        try:
            with urlopen(req) as resp:
                raw = resp.read()
        except HTTPError as e:
            print(
                f"[ERROR] HTTP error when calling doc-preview (save-to-TOS): "
                f"status={e.code}, reason={e.reason}",
                file=sys.stderr,
            )
            sys.exit(1)
        except URLError as e:
            print(
                f"[ERROR] Failed to call doc-preview (save-to-TOS): {e.reason}",
                file=sys.stderr,
            )
            sys.exit(1)
        except Exception as exc:  # noqa: BLE001
            print(
                f"[ERROR] Unexpected error when calling doc-preview (save-to-TOS): {exc}",
                file=sys.stderr,
            )
            sys.exit(1)

        print("[OK] Save result from TOS:")
        if not maybe_print_json(raw):
            # Fallback: print raw text
            print(raw.decode("utf-8", errors="replace"))
        return

    # Local save path branch
    try:
        with urlopen(req) as resp, open(output_path, "wb") as out_f:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                out_f.write(chunk)
    except HTTPError as e:
        print(
            f"[ERROR] HTTP error when downloading preview via pre-signed URL: "
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
            f"[ERROR] Failed to download preview via pre-signed URL: {e.reason}",
            file=sys.stderr,
        )
        try:
            os.remove(output_path)
        except OSError:
            pass
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(
            f"[ERROR] Unexpected error when downloading preview: {exc}", file=sys.stderr
        )
        try:
            os.remove(output_path)
        except OSError:
            pass
        sys.exit(1)

    try:
        size = os.path.getsize(output_path)
    except OSError:
        size = -1

    print(f"[OK] Output saved to {output_path} ({size} bytes)")


if __name__ == "__main__":
    main()
