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

"""Draw points and optional lines on an image stored in TOS.

This script wraps the TOS `image/draw` process:
  - p: points, e.g. 50x50-100x100-200x200
  - r: point radius
  - l: whether to connect points with lines
  - lw: line width
  - color: RGB hex without '#'

It can save the result locally or persist the processed image back to TOS.
"""

import argparse
import base64
import json
import os
import re
import sys
from typing import Optional

import tos
from tos.exceptions import TosClientError, TosServerError

POINT_RE = re.compile(r"^\d+x\d+(?:-\d+x\d+)*$")
COLOR_RE = re.compile(r"^[0-9A-Fa-f]{6}$")


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


def maybe_print_json(raw: bytes) -> bool:
    try:
        text = raw.decode("utf-8")
        data = json.loads(text)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return True
    except Exception:
        return False


def build_process_value(
    points: str, radius: int, draw_line: bool, line_width: int, color: str
) -> str:
    parts = [
        f"p_{points}",
        f"r_{radius}",
        f"l_{str(draw_line).lower()}",
        f"lw_{line_width}",
        f"color_{color.upper()}",
    ]
    return "image/draw," + ",".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw points/lines on a TOS image")
    parser.add_argument("--bucket", type=str, default=None, help="Override TOS_BUCKET")
    parser.add_argument("--key", type=str, default=None, help="Override TOS_OBJECT_KEY")
    parser.add_argument(
        "--points",
        type=str,
        required=True,
        help="Point list, e.g. 50x50-100x100-200x200",
    )
    parser.add_argument("--radius", type=int, default=6, help="Point radius in pixels")
    parser.add_argument(
        "--line",
        action="store_true",
        help="Connect points with lines",
    )
    parser.add_argument(
        "--line-width", type=int, default=3, help="Line width in pixels"
    )
    parser.add_argument(
        "--color",
        type=str,
        default="FFFFFF",
        help="RGB hex color without '#', e.g. FF0000",
    )
    parser.add_argument(
        "--output", type=str, default=None, help="Local output file path"
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

    if not POINT_RE.match(args.points):
        print("[ERROR] --points must look like 50x50-100x100-200x200", file=sys.stderr)
        sys.exit(1)
    if args.radius < 0:
        print("[ERROR] --radius must be >= 0", file=sys.stderr)
        sys.exit(1)
    if args.line_width < 0:
        print("[ERROR] --line-width must be >= 0", file=sys.stderr)
        sys.exit(1)
    if not COLOR_RE.match(args.color):
        print(
            "[ERROR] --color must be a 6-digit RGB hex string, e.g. FF0000",
            file=sys.stderr,
        )
        sys.exit(1)

    client = create_client()
    bucket = args.bucket or get_env("TOS_BUCKET")
    key = args.key or get_env("TOS_OBJECT_KEY")
    process_value = build_process_value(
        points=args.points,
        radius=args.radius,
        draw_line=args.line,
        line_width=args.line_width,
        color=args.color,
    )

    save_bucket = args.saveas_bucket
    save_object = args.saveas_object
    persist_to_tos = bool(save_bucket or save_object)

    print(f"[INFO] process = {process_value}")

    if persist_to_tos:
        save_bucket = save_bucket or bucket
        if not save_object:
            save_object = f"draw_{os.path.basename(key)}"
        encoded_bucket = base64.urlsafe_b64encode(save_bucket.encode()).decode()
        encoded_object = base64.urlsafe_b64encode(save_object.encode()).decode()
        print(f"[INFO] Processing {bucket}/{key} -> {save_bucket}/{save_object}")
        try:
            output = client.get_object(
                bucket=bucket,
                key=key,
                process=process_value,
                save_bucket=encoded_bucket,
                save_object=encoded_object,
            )
            raw = output.read()
        except TosServerError as e:
            print(
                f"[ERROR] TOS server error: code={e.code}, status={e.status_code}, "
                f"request_id={e.request_id}, message={e.message}",
                file=sys.stderr,
            )
            sys.exit(1)
        except TosClientError as e:
            print(f"[ERROR] TOS client error: {e}", file=sys.stderr)
            sys.exit(1)

        print("[OK] Save result:")
        if not maybe_print_json(raw):
            print(raw.decode("utf-8", errors="replace"))
        return

    if not args.output:
        print(
            "[ERROR] --output is required when not saving back to TOS.", file=sys.stderr
        )
        sys.exit(1)

    print(f"[INFO] Processing {bucket}/{key} -> {args.output}")
    try:
        client.get_object_to_file(
            bucket=bucket,
            key=key,
            file_path=args.output,
            process=process_value,
        )
    except TosServerError as e:
        print(
            f"[ERROR] TOS server error: code={e.code}, status={e.status_code}, "
            f"request_id={e.request_id}, message={e.message}",
            file=sys.stderr,
        )
        sys.exit(1)
    except TosClientError as e:
        print(f"[ERROR] TOS client error: {e}", file=sys.stderr)
        sys.exit(1)

    size = os.path.getsize(args.output)
    print(f"[OK] Output saved to {args.output} ({size} bytes)")


if __name__ == "__main__":
    main()
